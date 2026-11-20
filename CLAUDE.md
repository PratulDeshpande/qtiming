# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`qtiming` is a static timing checker for dynamic quantum circuits (pre-alpha). Given a program and a hardware timing contract it returns PROVED, PROVED-UNDER (assumptions), REFUTED (replayable counterexample) or UNKNOWN. It is built phase by phase (P0, P1, ...) from `Plans/Implementation Plan v2 (validated).md`, which is the source of truth for architecture, layout and the decision log. Phases P0 to P9 are done (skeleton, core, contracts, front end, personality specs, executor, elaboration and graph, obligations with Tier 0, Tier 1 and Tier 2 (Z3) solvers, replayed counterexamples and the `check` command). reports (text, JSON, SARIF, HTML), `explain`/`lint`/`replay`/`contract show|diff` and the RUS formulas. Not built yet: O5 symbolic encoding, RUS wiring into `check`, windowing (P10), synthesis (P11), Qiskit passes (P12), benchmarks (P13), IBM evidence (P14). `solve/smt_o5.py`, `solve/synth`, `verdict` renderers beyond text and JSON, `evidence`, `repair`, `qiskit_pass` (except `strip`) are stubs; check the plan before assuming they have content.

## Commands

Use the venv (Windows paths: `.venv/Scripts/...`). Setup: `pip install -e ".[dev]"`; extras `qiskit`, `z3`, `synth`, `bench` are needed for the matching features/tests.

The full gate (same as CI; must be green before a PR):

    ruff check . && mypy --strict src/qtiming/core && lint-imports && pytest -q

- Single test: `pytest tests/unit/frontend/test_stretch.py::test_name -q`
- mypy strict only covers `src/qtiming/core` (set in `pyproject.toml`).
- Ruff: line length 100, rules E/F/I/UP/B, target py310. CI tests on Python 3.10, 3.12 and 3.14.
- CLI: `check`, `explain`, `lint`, `replay`, `contract validate|show|diff`; see `Docs/cli.md` (exit 0 proved, 1 refuted, 2 usage error, 3 unknown, 4 internal). Report snapshots: `tests/golden/reports` (`QTIMING_UPDATE_GOLDEN=1` regenerates).
- Workflow rule from CONTRIBUTING: tests first (a test must fail before the fix). Changing a personality's behaviour goes through the decision log in the implementation plan.

## Architecture

Pipeline layering is enforced by `lint-imports` (`.importlinter`), top depends on bottom:

    cli > qiskit_pass | repair > verdict > solve > oblig > dispatch > graph > elab > contract | frontend > core

Import rules that shape where code can go:
- `core` is stdlib-only (no pydantic, qiskit, z3, networkx, numpy, pandas). It holds the data model: AST, exact-time arithmetic (`time.py`, ns <-> dt rounding depends on the role of the number), labels/conditions, provenance, ids, errors.
- Qiskit may only be imported in adapters (`frontend`, `qiskit_pass`, `contract.target_import`), never in `core`, `contract.schema`/`loader`, or the solver-side packages.
- `exec` (executor/personalities) must never import the graph/solver side (`graph`, `dispatch`, `oblig`, `solve`, `elab`, `verdict`), so it stays an independent check.
- The verification solvers (`solve.concrete/interval/smt/smt_o5/dispatcher`) must not import `solve.synth`.

Key flows:
- **Contracts** (`src/qtiming/contract/`): a hardware timing contract is a TOML file validated by `schema.py` (pydantic) and loaded by `loader.py` (`load_contract`, `ContractLoadError`; supports `--assume` overrides). Four instances live in `contract/instances/` (`artiq`, `ibm_heron`, `q1`, `qua`); `ibm_heron_snapshot.json` is a fixture, and `target_import.py` builds a snapshot from a Qiskit Target. `compat.py` is the compatibility table. Unpublished numbers are left absent so dependent obligations come out UNKNOWN rather than guessed.
- **Front end** (`src/qtiming/frontend/`): turns Qiskit circuits (`qiskit_fe.py`, `qiskit_expr.py`) into the core AST via `Program`; parses `timing.*` annotations (`annotations.py`, `payload.py`) with QASM3 and QPY round-trip (`serialise.py`); resolves `stretch` (`stretch.py`); `lint.py` is the IBM front-end lint.

## Tests

Tests under `tests/unit/<package>/` mirror `src/qtiming/<package>/`. Hypothesis is used (`.hypothesis/` is local cache). Other top-level dirs (`benchmarks`, `experiments`, `prereg`, `artifact`, `Docs`) are mostly planning/README material at this stage; `Docs/` has the timed-semantics and timing-rulebook write-ups.

## Verification pipeline (P4 to P7)

`frontend` -> `elab.elaborate` (EQ/SYNC/EXP, unrolling) -> `dispatch.build_graph` (the LTEG, per-personality
rules over `graph.builder`) -> `oblig.generate` -> `solve.dispatcher.verify` (Tier 0 exact, Tier 1 interval)
-> `verdict.run.check_program`. The reference executor (`exec`, four personalities, `Fixed/Random/Extreme`
oracles, `exec.explore.exhaustive`) is written separately from the graph side and checked against it:
`tests/personality` (hand-computed goldens: `<name>/golden/*.json`), `tests/differential` (1000 random
programs per personality and policy), `tests/property` (soundness, cone invariance, Tier 1 containment).
Normative personality rules live in `Docs/personality-spec/`. Rulings made while building are rows 44 to 53 of
the decision log (plan Section 21.2). Tier 1 may only prove. Tier 0 and Tier 2 refute, and every REFUTED is minimised then replayed in the executor (`verdict.replay`); a mismatch is `I-REPLAY-MISMATCH` (exit 4). Tier 2 needs the `z3` extra and is skipped (UNKNOWN) without it; a counterexample that depends on an unbounded latency is UNKNOWN, never REFUTED.
