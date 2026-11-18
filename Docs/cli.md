# qtiming command reference

Every command takes `--contract C` (a contract file, or the name of a shipped instance:
`ibm_heron`, `q1`, `artiq`, `qua`) and a program: an OpenQASM 3 file (`.qasm`, the extension may
be omitted) or a QPY file (`.qpy`). `--assume KEY=VALUE` overrides a contract number and is
recorded in the report: `durations.x=32` (ns), `timeline.commit_lead=50` (ns),
`ff.default=0:600` (lo:hi ns, class `vendor`).

## `qtiming check PROG --contract C`

Verify a program. Output is a verdict plus the obligations behind it.

| Option | Meaning |
| --- | --- |
| `--policy eq\|sync\|exp` | policy for branches with no `timing.policy` annotation (an annotation wins) |
| `--format text\|json\|sarif\|html` | report format; SARIF 2.1.0 validates against the OASIS schema; HTML is a static page with an inline SVG timeline |
| `--out FILE` | write the report to a file |
| `--max-safe KEY` | bisect the largest safe `hi` (dt and ns) of a contract latency, re-elaborating at each step |
| `--no-tier1`, `--no-tier2` | skip the interval abstraction, or the SMT solver (UNKNOWN where only it can decide) |
| `--timeout S` | seconds per SMT query (default 10) |
| `--first-failure` | stop at the first REFUTED obligation |
| `--strict-proved` | treat PROVED-UNDER as a failure (exit 1) |

Exit codes: `0` PROVED or PROVED-UNDER, `1` REFUTED, `2` usage or lint error, `3` UNKNOWN,
`4` internal error (including `I-REPLAY-MISMATCH`).

Verdicts: PROVED (no assumption weaker than cycle-counted), PROVED-UNDER (holds if the listed
latency bounds are true), REFUTED (a counterexample the independent executor reproduced, or a
policy the backend cannot express), UNKNOWN (a number is missing or a tier could not decide).
Every report ends with the obligation kinds this build did not check.

## `qtiming explain PROG --contract C`

`--elaborated` prints the program after elaboration (synthesised statements marked
`synth(from nN)`); `--obligations` lists the generated obligations; `--graph dot` prints the
event graph in Graphviz DOT; with none of these, a one-line summary.

## `qtiming lint PROG --contract C [--format sarif]`

Front-end and static lint only; exit 2 if any finding is an error.

## `qtiming replay CEX.json PROG --contract C [--index N] [--trace]`

Replay a counterexample (the JSON from `check --format json`, or one entry of its
`counterexamples` array) in the reference executor. Prints `REPRODUCED` or `NOT REPRODUCED`.

## `qtiming contract validate|show|diff`

`validate FILES` checks contracts load; `show C` prints a summary as JSON; `diff A B` lists the
differences (exit 1 if any).

## Not implemented yet

`qtiming synth`, `qtiming repair`, `qtiming evidence`, `qtiming-bench` (phases P11, P14, P13).
