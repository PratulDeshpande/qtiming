# Command reference

    usage: qtiming [-h] {contract,check,explain,lint,replay,repair,evidence} ...

Every command except `evidence` and `contract validate|diff` takes `--contract C`, a contract file or the name of a shipped instance (`ibm_heron`, `q1`, `artiq`, `qua`), and a program: an OpenQASM 3 file (`.qasm`, the extension may be omitted) or a QPY file (`.qpy`). Each takes `--assume KEY=VALUE`, which overrides a contract number for the run and is recorded in the report. See [Contracts](contracts.md).

| Form | Sets |
| --- | --- |
| `durations.x=32` | gate duration, ns |
| `timeline.commit_lead=50` | commit lead, ns |
| `ff.default=0:600` | latency `lo:hi`, ns; class `vendor` only |

The separate command `qtiming-bench` is the benchmark harness and needs the `bench` extra.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | `check`: PROVED or PROVED-UNDER. Other commands: success. |
| 1 | `check`: REFUTED, or PROVED-UNDER with `--strict-proved`. `contract validate`: a contract failed. `contract diff`: the contracts differ. `repair`: no automatic patch. `replay`: `NOT REPRODUCED`. |
| 2 | Usage, program, contract or lint error: any `E-` code in [Error codes](errors.md). |
| 3 | `check`: UNKNOWN. `repair`: the patched program is still UNKNOWN. |
| 4 | Internal error: an unexpected Python exception, for example a missing optional dependency. |

## `qtiming check PROGRAM --contract C`

Verify a program. The output is a verdict and the obligations behind it. See [Reading a verdict](verdicts.md).

| Option | Meaning |
| --- | --- |
| `--assume KEY=VALUE` | Contract override, repeatable. |
| `--policy eq\|sync\|exp` | Policy for branches with no `timing.policy` annotation. An annotation wins. Default: the contract's. |
| `--format text\|json\|sarif\|html` | Report format. Default `text`. |
| `--out FILE` | Write the report to a file instead of standard output. |
| `--max-safe KEY` | Bisect the largest safe upper bound of the latency `KEY`, re-elaborating at each step. |
| `--no-tier1` | Skip the interval abstraction. |
| `--no-tier2` | Skip the SMT solver; no Z3 is needed. What Tier 1 cannot prove is UNKNOWN. |
| `--timeout S` | Seconds per SMT query. Default 10. |
| `--first-failure` | Stop at the first REFUTED obligation. |
| `--no-window` | Never summarise a long loop by an iteration window; unroll it or fail with `E-ELAB-LOOP-LIMIT`. Windowing applies to IBM only. |
| `--strict-proved` | Treat PROVED-UNDER as a failure (exit 1). |

## `qtiming explain PROGRAM --contract C`

With no option, a one-line summary of the graph. Options: `--assume`, `--policy`, `--elaborated` (the program after elaboration, synthesised statements marked `synth(from nN)`), `--obligations` (every obligation with its check and message), `--graph dot` (the event graph in Graphviz DOT), `--out FILE`.

## `qtiming lint PROGRAM --contract C`

Front-end and static lint only. Options: `--assume`, `--format text|sarif`, `--out FILE`. Exit 2 if any finding is an error; a warning alone exits 0. Only the IBM structural rules are implemented. See [Error codes](errors.md).

## `qtiming replay CEX PROGRAM --contract C`

Replay a counterexample in the reference executor. `CEX` is the JSON from `check --format json`, or one entry of its `counterexamples` array. Options: `--assume`, `--policy`, `--index N` (which counterexample of the report), `--trace` (print the executed timeline). It prints `REPRODUCED: O4 at node 11` and exits 0, or `NOT REPRODUCED: ...` and exits 1.

## `qtiming repair PROGRAM --contract C`

Suggest declared `delay` insertions that fix a REFUTED program. Options: `--assume`, `--policy`, `--out FILE`, `--verbose` (also print the patched verdict).

Only O1 failures are repaired automatically. The delay is grown until the re-verified program stops failing, because on ARTIQ the delay itself costs issue time. O3 is refused: a delay makes a deadline worse. Every candidate is re-verified by the normal pipeline before it is shown. Exit 0 when the program was already fine or the patch re-verifies; 1 when no automatic patch exists; 3 when the patched program is still UNKNOWN.

## `qtiming contract`

| Subcommand | Does |
| --- | --- |
| `validate FILES` | Check that the contract files load. Takes paths only. Exit 1 if any fails. |
| `show FILES` | Print a JSON summary (durations and latencies in dt). Takes a file or an instance name. |
| `diff A B` | List the differences. Exit 1 if there are any. |

All three accept `--assume`; `diff` applies it to both sides.

## `qtiming evidence ingest|report JOBS...`

Turn IBM `scheduler_timing` job records into a contract patch (`ingest`) or a summary (`report`). `--out FILE` writes the patch. Jobs flagged synthetic are refused unless `--allow-synthetic` is given; the patch then says so. Collecting jobs needs an IBM account; see `experiments/ibm_dryrun`. No hardware data is in the repository, so this command has not been exercised on real jobs.

    $ qtiming evidence ingest tests/fixtures/evidence/conclusive/ff1.json
    error: synthetic job(s) ['tests/fixtures/evidence/conclusive/ff1.json']: pass allow_synthetic to ingest test data
    $ echo $?
    2

## Not implemented

`qtiming synth` does not exist. The Tier 3 synthesis algorithms are library code and back `repair`.
