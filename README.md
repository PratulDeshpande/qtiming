# qtiming

A static timing checker for dynamic quantum circuits. Given a program (OpenQASM 3 or a Qiskit
circuit) and a hardware timing contract, it answers before the program runs:

| Verdict | Meaning |
| --- | --- |
| `PROVED` | every obligation holds, and no assumption is weaker than a cycle-counted bound |
| `PROVED-UNDER` | holds if the listed latency bounds are true (each is printed with its source) |
| `REFUTED` | a counterexample exists; it is minimised and replayed in an independent reference executor |
| `UNKNOWN` | a contract number is missing or no solver tier could decide |

**Status: pre-alpha (`0.1.0.dev0`).** Read "Status and limitations" below before trusting a verdict.

## Install

Not on PyPI yet. From a clone:

    python -m venv .venv
    .venv/Scripts/pip install -e ".[qiskit,z3]"        # Linux/macOS: .venv/bin/pip

| Extra | Adds | Needed for |
| --- | --- | --- |
| (none) | pydantic (+ tomli on 3.10) | contracts, graph, Tier 0 and Tier 1 solvers |
| `qiskit` | qiskit, openqasm3[parser], qiskit-qasm3-import | reading `.qasm` / `.qpy` programs, Qiskit passes |
| `z3` | z3-solver | Tier 2 SMT (counterexamples); without it those queries are UNKNOWN |
| `synth` | nothing today | kept as a placeholder name |
| `bench` | pyarrow, matplotlib | `qtiming-bench` Parquet and figures |
| `dev`, `docs` | test/lint tools, mkdocs-material | contributing, building the docs |

## Five-minute quickstart

Run from the repository root (the benchmark programs are not in the wheel). Output below was
produced by these exact commands.

    $ qtiming contract validate src/qtiming/contract/instances/ibm_heron.toml
    OK ibm_heron sha256=9cf4d27a06ae placeholders=0 missing=0 warnings=0

    $ qtiming check benchmarks/families/teleportation/tp_basic --contract ibm_heron --policy eq
    PROVED-UNDER  (contract ibm_heron, policy eq, sha256 9cf4d27a06ae)
      assumptions (weakest class: vendor):
        ff.default: [0 ns, 600 ns]  vendor: IBM blog, 2025-11-19 (feedforward about 600 ns); vendor claim, not a certified bound
      O2b: 1 obligation(s): proved (tier 1, margin 0 ns)
      O3: 2 obligation(s): proved (tier 1, margin 2400 ns)
      O4: 11 obligation(s): proved (tier 0, margin 0 ns); proved (tier 1, margin 0 ns)
      O7: 1 obligation(s): proved (tier 1, margin 0 ns)
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    (exit 0)

    $ qtiming check benchmarks/families/teleportation/tp_sync --contract ibm_heron --policy eq
    REFUTED  (contract ibm_heron, policy eq, sha256 9cf4d27a06ae)
      why: O4 at node 11: idle gap on q2 must not vary with outcomes or latencies
      O4 failed at benchmarks/families/teleportation/tp_sync.qasm:17 (tier 2)
      ...
      timeline (counterexample):
    (exit 1; the full report also draws the replayed timeline)

    $ qtiming check benchmarks/families/teleportation/tp_basic --contract artiq --policy eq
    error: E-CT-MISSING: contract 'artiq_rtio' has no duration for 'h'
      hint: add it to [durations] or import it from the backend Target
    (exit 2: the ARTIQ contract leaves unpublished numbers absent instead of guessing them)

    $ qtiming repair benchmarks/families/teleportation/tp_sync --contract ibm_heron --policy eq
    repair: unsupported: no automatic patch for O4 (idle gap on q2 must not vary with outcomes or latencies)
    before: REFUTED  after: REFUTED
    (exit 1)

`repair` only patches O1 (commit lead) failures today and re-verifies every patch; for anything
else it says so, as above. Other commands: `explain`, `lint`, `replay`, `evidence`, and
`contract validate|show|diff`; formats `text`, `json`, `sarif` (GitHub code scanning) and `html`.
Full reference: [`Docs/cli.md`](Docs/cli.md).

Exit codes of `check`: `0` PROVED or PROVED-UNDER, `1` REFUTED, `2` usage or contract error,
`3` UNKNOWN, `4` internal error (including `I-REPLAY-MISMATCH`, an executor/checker disagreement).

## How it is checked

`frontend` -> `elab` (equalise / sync / expose policies, unrolling) -> `graph` (per-personality
timed event graph) -> `oblig` (O1 to O9) -> `solve` (Tier 0 exact, Tier 1 interval, Tier 2 Z3) ->
`verdict`. A separate reference executor for the four personalities (IBM, Q1, ARTIQ, QUA) is
written independently of the graph side and is used to replay every counterexample. Import
layering is enforced by `lint-imports`.

## Status and limitations

Be sceptical; this is what is and is not true today.

* **Phases.** P0 to P9 are committed (skeleton, core, contracts, front end, personality specs,
  executor, elaboration and graph, obligations and solvers, replayed counterexamples, reports).
  P10 to P14 (windowing, synthesis and repair, Qiskit passes, benchmarks, IBM evidence tooling)
  exist in the working tree as of this release candidate; see `CHANGELOG.md`.
* **Contract numbers are unpublished or vendor claims.** Where a vendor has not published a number
  it is left absent, so dependent obligations are UNKNOWN or the run stops with `E-CT-MISSING`; it
  is never guessed. IBM gate durations come from an unofficial snapshot and the IBM feed-forward
  latency is a vendor claim, which is why IBM results are PROVED-UNDER and not PROVED.
* **No real IBM evidence.** `experiments/ibm_dryrun/` can collect `scheduler_timing` from dry-run
  jobs but no hardware data is in the repository; `tests/fixtures/evidence/` is synthetic.
* **The DC checker is flagged UNVERIFIED** (`solve/synth/stnu_dc.py`, `Docs/theory/dc-rules.md`):
  rules were transcribed from memory and not yet checked against the paper or the 621-network
  oracle suite. It is used for synthesis, not for verification verdicts.
* **Not covered.** Obligations O4a, O6, O8, O9, and O7 for SYNC with a spread bound are not
  checked and every report says so. RUS formulas are not wired into `check`. Hardware-backed and
  oracle-backed claims (CSTNU Tool, IBM jobs) cannot be reproduced offline.
* `benchmarks/expected.json` is a regression snapshot, not ground truth.

## Develop

    pip install -e ".[dev,qiskit,z3]"
    ruff check . && mypy --strict src/qtiming/core && lint-imports && pytest -q

See `CONTRIBUTING.md`. Docs: `pip install -e ".[docs]" && mkdocs build --strict`.
Reproduction artifact: `artifact/README.md`. Licence: Apache-2.0.
