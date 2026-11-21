# Changelog

All notable changes are listed here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- `tutorials/`: 14 executable Jupyter notebooks (00 to 13) rendered to `Docs/tutorials/` and an
  interactive four-stack comparison page (`compare.md`, data from real `check` runs). Every key result is
  asserted in a cell; `tests/tutorials` executes them. New `tutorials` extra; build with
  `python tutorials/build.py` and `python tutorials/compare.py`.

## [0.1.0] - 2026-11-20 (first public alpha)

Phases P0 to P9 are committed (`git log`). P10 to P14 are present in the working tree but were not
committed when this entry was written; check `git log` before quoting them as released.

### Added
- P0, P1: repository skeleton, tooling (ruff, mypy --strict on `core`, import-linter layering), the
  `core` data model (AST, exact time arithmetic, labels, provenance, errors).
- P2: timing contracts (pydantic schema, TOML loader, `--assume` overrides, compatibility table), four
  shipped instances (`ibm_heron`, `q1`, `artiq`, `qua`), `qtiming contract validate`.
- P3: front end: `timing.*` annotations with QASM 3 and QPY round trip, Qiskit circuit to AST,
  OpenQASM 3 parser, `stretch` resolution, IBM front-end lint.
- P4, P5: normative personality specs with hand-computed goldens; independent reference executor
  for IBM, Q1, ARTIQ and QUA with fixed/random/extreme oracles and exhaustive exploration.
- P6: elaboration (EQ, SYNC, EXP policies, loop unrolling), timed event graph and per-personality
  dispatch rules; graph-versus-executor differential (1000 random programs per personality and policy).
- P7, P8: obligations O1 to O5 and O7; Tier 0 (exact), Tier 1 (interval, proves only) and Tier 2 (Z3,
  optional) solvers; verdict lattice; `qtiming check`; exact rational counterexamples, minimisation
  and replay in the executor (`I-REPLAY-MISMATCH` on disagreement).
- P9: reports (text, JSON, SARIF 2.1.0, static HTML timeline), `explain`, `lint`, `replay`,
  `contract show|diff`, RUS formulas, teleportation benchmark family, report goldens.
- P10 to P14 (uncommitted at time of writing): windowing of long loops (IBM only), controllability
  synthesis modules and `qtiming repair` (O1 only), Qiskit passes (`strip`, equalise, timing check) and the
  `qiskit.transpiler.scheduling` plugin, `qtiming-bench` and 56 benchmark programs in 8 families,
  IBM dry-run evidence tooling (`qtiming evidence ingest|report`).
- P16: README, this changelog, mkdocs site, artifact Dockerfile and `smoke.sh`, release and docs workflows.

### Fixed (packaging, found while preparing the release)
- `tomli` is now a dependency on Python 3.10 (the contract loader imports it there).
- The `qiskit` extra now installs `openqasm3[parser]` and `qiskit-qasm3-import`; without them
  `qtiming check` failed with "Parsing is not available" in a clean install.
- Removed unused `networkx`, `pandas` and `pyyaml` from the `synth` and `bench` extras.

### Fixed (checker, found while building P13 to P15)
- Elaboration: a capped `while` whose body re-measures the bit it tests unrolled into iterations that all
  tested the stale pre-loop measurement (contradictory nested arms, `AssertionError`). Iteration j+1 now
  reads the bit's latest measurement.
- QUA: a join over an empty qubit set (an empty final loop arm) had a label and no in-edge
  (`E-GRAPH-LABEL`). The graph now matches the reference executor on those events.
- Tier 1 soundness: a snapped node downstream of an unbounded latency was dropped from the forms and an
  obligation about it was reported PROVED ("vacuous"). It now stays unproved. No shipped builder emits
  snap nodes, so the pipeline was not exposed, but the solver was unsound on such graphs.

### Known issues
- The DC checker (`solve/synth/stnu_dc.py`) is flagged UNVERIFIED: rules transcribed from memory, not yet
  validated against the paper or the 621-network oracle suite. Not used for verdicts.
- No real IBM hardware evidence exists; the evidence fixtures are synthetic.
- Theory status (`Docs/theory/index.md`): T5 holds only for non-negative weights, bounded latencies and
  Diff obligations; T3 does not hold for QUA; T4 is one-directional and windows IBM only.
- IBM gate durations come from an unofficial snapshot and the IBM feed-forward latency is a vendor
  claim; unpublished numbers are left absent, so dependent obligations are UNKNOWN.
- Not built: O4a, O6, O8, O9, O5 symbolic encoding, RUS wiring into `check`; `repair` handles O1 only.
- There is no `qtiming synth` command yet; the Tier 3 algorithms are library code used by `repair`.
