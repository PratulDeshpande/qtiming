# qtiming

[![test](https://github.com/PratulDeshpande/QTiming/actions/workflows/test.yml/badge.svg)](https://github.com/PratulDeshpande/QTiming/actions/workflows/test.yml)
[![lint](https://github.com/PratulDeshpande/QTiming/actions/workflows/lint.yml/badge.svg)](https://github.com/PratulDeshpande/QTiming/actions/workflows/lint.yml)
[![docs](https://github.com/PratulDeshpande/QTiming/actions/workflows/docs.yml/badge.svg)](https://github.com/PratulDeshpande/QTiming/actions/workflows/docs.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
![Python 3.10+](https://img.shields.io/badge/python-3.10%20%7C%203.12%20%7C%203.14-blue)
![Status: alpha](https://img.shields.io/badge/status-alpha%200.1.0-orange)

**A static timing checker for dynamic quantum circuits.** Give it a program (OpenQASM 3 or a
Qiskit circuit) and a hardware timing contract. Before anything runs, it tells you whether the
program's timing is correct, and if not, shows you a counterexample.

[**CLI reference**](https://pratuldeshpande.github.io/qtiming/cli/) |
[**Quickstart**](https://pratuldeshpande.github.io/qtiming/quickstart/) |
[**Status**](https://pratuldeshpande.github.io/qtiming/status/) |
[**Changelog**](CHANGELOG.md) |
[**Contributing**](CONTRIBUTING.md)

> **Alpha software.** qtiming is pre-1.0 and its verdicts depend on contract numbers that are
> often vendor claims. Read [Status and limitations](#status-and-limitations) before trusting one.

## Why

Dynamic circuits branch on mid-circuit measurements, and the classical feed-forward that follows
has a latency that varies by hardware and by outcome. A branch that idles one qubit for a
different time than its sibling branch, or a feed-forward that arrives too late, is a timing bug
that only shows up on real hardware, if at all. qtiming checks these properties statically,
against an explicit and versioned description of the hardware, so a missing or unpublished number
is reported as `UNKNOWN` instead of being quietly guessed.

## What you get

Every run ends in exactly one of four verdicts:

| Verdict | Meaning |
| --- | --- |
| `PROVED` | every obligation holds, and no assumption is weaker than a cycle-counted bound |
| `PROVED-UNDER` | holds if the listed latency bounds are true (each is printed with its source) |
| `REFUTED` | a counterexample exists; it is minimised and replayed in an independent reference executor |
| `UNKNOWN` | a contract number is missing or no solver tier could decide |

- **Contracts, not guesses.** Hardware timing lives in a validated TOML contract. Four are
  included: `ibm_heron`, `q1`, `artiq`, `qua`. Unpublished numbers stay absent.
- **Replayed counterexamples.** A `REFUTED` result is minimised and re-executed by a reference
  executor written separately from the checker. A disagreement is a hard internal error, never a
  silent pass.
- **Layered solvers.** Exact arithmetic (Tier 0), interval analysis (Tier 1) and Z3 SMT (Tier 2).
  Interval analysis can only prove; only Tiers 0 and 2 can refute.
- **CI-friendly output.** Text, JSON, SARIF (for GitHub code scanning) and HTML reports, with
  stable exit codes.

## Install

Not on PyPI yet. From a clone:

    python -m venv .venv
    .venv/Scripts/pip install -e ".[qiskit,z3]"        # Linux/macOS: .venv/bin/pip

Requires Python 3.10 or newer. Extras:

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

Validate a hardware contract:

    $ qtiming contract validate src/qtiming/contract/instances/ibm_heron.toml
    OK ibm_heron sha256=9cf4d27a06ae placeholders=0 missing=0 warnings=0

Check a teleportation circuit. It holds, but only under a vendor-claimed feed-forward latency, so
the verdict says so and prints the assumption with its source:

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

A variant that is genuinely wrong gets a counterexample:

    $ qtiming check benchmarks/families/teleportation/tp_sync --contract ibm_heron --policy eq
    REFUTED  (contract ibm_heron, policy eq, sha256 9cf4d27a06ae)
      why: O4 at node 11: idle gap on q2 must not vary with outcomes or latencies
      O4 failed at benchmarks/families/teleportation/tp_sync.qasm:17 (tier 2)
      ...
      timeline (counterexample):
    (exit 1; the full report also draws the replayed timeline)

A contract that does not publish a number refuses to guess it:

    $ qtiming check benchmarks/families/teleportation/tp_basic --contract artiq --policy eq
    error: E-CT-MISSING: contract 'artiq_rtio' has no duration for 'h'
      hint: add it to [durations] or import it from the backend Target
    (exit 2: the ARTIQ contract leaves unpublished numbers absent instead of guessing them)

And `repair` patches what it can and says so when it cannot:

    $ qtiming repair benchmarks/families/teleportation/tp_sync --contract ibm_heron --policy eq
    repair: unsupported: no automatic patch for O4 (idle gap on q2 must not vary with outcomes or latencies)
    before: REFUTED  after: REFUTED
    (exit 1)

`repair` only patches O1 (commit lead) failures today and re-verifies every patch.

### Commands and exit codes

`check`, `explain`, `lint`, `replay`, `repair`, `evidence`, and `contract validate|show|diff`.
Report formats: `text`, `json`, `sarif`, `html`. Full reference:
[`Docs/cli.md`](https://pratuldeshpande.github.io/qtiming/cli/).

| Exit | Meaning |
| --- | --- |
| `0` | PROVED or PROVED-UNDER |
| `1` | REFUTED |
| `2` | usage or contract error |
| `3` | UNKNOWN |
| `4` | internal error, including `I-REPLAY-MISMATCH` (executor and checker disagree) |

## How it works

    frontend -> elab -> graph -> oblig -> solve -> verdict

1. **frontend** reads OpenQASM 3 or a Qiskit circuit into a core AST.
2. **elab** applies the chosen policy (equalise, sync or expose) and unrolls.
3. **graph** builds a timed event graph using the rules of one hardware personality (IBM, Q1,
   ARTIQ or QUA).
4. **oblig** generates timing obligations O1 to O9 from the graph.
5. **solve** discharges them with Tier 0 (exact), Tier 1 (interval) and Tier 2 (Z3).
6. **verdict** combines the results, minimises any counterexample and replays it.

The reference executor for the four personalities is written independently of the graph side, and
differential tests (1000 random programs per personality and policy) check the two against each
other. Import layering is enforced by `lint-imports`. The normative rules live in
[`Docs/personality-spec/`](https://pratuldeshpande.github.io/qtiming/personality-spec/ibm/).

## Status and limitations

Be sceptical; this is what is and is not true today.

- **Phases.** P0 to P9 are committed (skeleton, core, contracts, front end, personality specs,
  executor, elaboration and graph, obligations and solvers, replayed counterexamples, reports).
  P10 to P14 (windowing, synthesis and repair, Qiskit passes, benchmarks, IBM evidence tooling)
  are committed too; see `CHANGELOG.md`.
- **Contract numbers are unpublished or vendor claims.** Where a vendor has not published a number
  it is left absent, so dependent obligations are UNKNOWN or the run stops with `E-CT-MISSING`; it
  is never guessed. IBM gate durations come from an unofficial snapshot and the IBM feed-forward
  latency is a vendor claim, which is why IBM results are PROVED-UNDER and not PROVED.
- **No real IBM evidence.** `experiments/ibm_dryrun/` can collect `scheduler_timing` from dry-run
  jobs but no hardware data is in the repository; `tests/fixtures/evidence/` is synthetic.
- **The DC checker is flagged UNVERIFIED** (`solve/synth/stnu_dc.py`, `Docs/theory/dc-rules.md`):
  rules were transcribed from memory and not yet checked against the paper or the 621-network
  oracle suite. It is used for synthesis, not for verification verdicts.
- **Not covered.** Obligations O4a, O6, O8, O9, and O7 for SYNC with a spread bound are not
  checked and every report says so. RUS formulas are not wired into `check`. Hardware-backed and
  oracle-backed claims (CSTNU Tool, IBM jobs) cannot be reproduced offline.
- `benchmarks/expected.json` is a regression snapshot, not ground truth.

## Documentation

| | |
| --- | --- |
| [Quickstart](https://pratuldeshpande.github.io/qtiming/quickstart/) | longer walkthrough |
| [CLI reference](https://pratuldeshpande.github.io/qtiming/cli/) | every command, flag and exit code |
| [Personality specs](https://pratuldeshpande.github.io/qtiming/personality-spec/ibm/) | normative timing rules per hardware |
| [Theory](https://pratuldeshpande.github.io/qtiming/theory/) | the formal background |
| [Status](https://pratuldeshpande.github.io/qtiming/status/) | what is built, phase by phase |
| [`artifact/README.md`](artifact/README.md) | how to reproduce the results |

Build the docs locally with `pip install -e ".[docs]" && mkdocs build --strict`.

## Contributing

Bug reports, hardware contract corrections and new test programs are welcome. Tests come first: a
test must fail before the fix. The full gate, the same one CI runs, is:

    pip install -e ".[dev,qiskit,z3]"
    ruff check . && mypy --strict src/qtiming/core && lint-imports && pytest -q

See [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md). Report
problems on the [issue tracker](https://github.com/PratulDeshpande/QTiming/issues).

## Citation

If you use qtiming in research, please cite it using [CITATION.cff](CITATION.cff) (GitHub's
"Cite this repository" button reads it).

## Author

Created and maintained by [Pratul Deshpande](https://github.com/PratulDeshpande).

## License

Copyright 2026 Pratul Deshpande. Released under the [Apache-2.0](LICENSE) licence; see
[NOTICE](NOTICE) for attributions.
