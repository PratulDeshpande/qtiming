# Error codes

Every diagnostic has a stable code. `E-` is an error, `W-` a warning, `I-` an internal inconsistency. The text form is `error: CODE: message`, followed by `hint: ...` when there is one. The code is also the rule id in SARIF output.

Codes starting `E-` or `W-` that are raised during a command end it with exit code 2 (`lint` exits 2 only if a finding is an error). An `I-` code is an internal inconsistency and ends the command with exit code 4, as does any unexpected Python exception.

Verdict lines (`policy-incompatible`, `missing contract field`, `Tier 2 needs z3`) are not error codes; see [Reading a verdict](verdicts.md).

## Command line and contract

| Code | Meaning | Remedy |
| --- | --- | --- |
| `E-CLI-CONTRACT` | `--contract` is neither a file nor a shipped instance. | Use a path, or one of `artiq`, `ibm_heron`, `q1`, `qua`. |
| `E-CLI-PROGRAM` | No program found for the name given. | Pass a `.qasm` or `.qpy` file; the extension may be omitted. |
| `E-CT-SCHEMA` | The contract does not match the schema (unknown key, wrong type, `lo_ns` above `hi_ns`, duplicate latency key, bad number). All problems are listed together. | Fix the field named. See [Contracts](contracts.md). |
| `E-CT-ASSUME` | An `--assume` value is malformed, or names a class other than `vendor`. | Use `KEY=LO:HI`, `durations.NAME=NS` or `timeline.commit_lead=NS`. |
| `E-CT-MISSING` | The program uses a gate for which the contract has no duration. | Add it to `[durations]` or pass `--assume durations.NAME=NS`. |
| `E-CT-TARGET` | The Target snapshot cannot be read, or `dt_ns = "from_target"` with no Target. | Fix `[target] source`, or pass a Target. |
| `E-CT-TARGET-CONFLICT` | The contract disagrees with the Target on dt, a grid value or a duration. | Remove the override, or set `override = true` with a reason. |
| `E-CT-RESOLUTION` | With `latency_resolution = "dt"`, a latency is not a whole number of dt. | Round the latency or use `continuous`. |
| `E-CT-LOOP` | `loop.while_supported = true` while `branch.allow_loops = false`. | Make the two agree. |
| `W-CT-ROUND` | A latency in ns was rounded outward to whole dt. Shown in the notes. | None needed; the rounding is conservative. |

## Front end

| Code | Meaning | Remedy |
| --- | --- | --- |
| `E-FE-MISSING-EXTRA` | Reading OpenQASM 3 needs the `openqasm3` parser, which comes with the `qiskit` extra. | `pip install 'qtiming[qiskit]'`. |
| `E-FE-PARSE` | The OpenQASM 3 text does not parse. | Fix the syntax at the location given. |
| `E-FE-UNSUPPORTED` | A construct outside the supported fragment: box durations, delay units, `timing.cap` exhaust labels, a bit written in only some branches before it is read. | Rewrite as the hint says. |
| `E-FE-EXPR-UNSUPPORTED` | An expression in a condition that is not a bit or register comparison, parity, or and/or/not. | Rewrite the condition. |
| `E-FE-UNKNOWN-OP` | A Qiskit instruction that is not a gate or a supported operation. | Map it to a supported gate first; there are no default durations. |
| `E-FE-INDEX` | A register index is out of range. | Fix the index. |
| `E-FE-BIT-UNWRITTEN` | A condition reads a bit before any measurement writes it. | Measure into the bit first. |
| `E-FE-NO-DT` | A duration in time units was written but no contract was supplied for dt. | Pass `--contract`, or write the duration in `dt`. |
| `E-FE-UNBOUNDED-WHILE` | A `while` loop with no `timing.cap`. | Wrap it in a `box` annotated `@timing.cap N`. |
| `E-FE-ANNOT-PLACEMENT` | A `timing.*` annotation on something other than a `box`. | Wrap the statement in `box { ... }`. |
| `E-FE-ANNOT-PAYLOAD` | A `timing.*` annotation with an unknown kind or a payload that does not parse (duration, policy, cap, pmin). | Check the payload against [Policies](policies.md). |
| `E-FE-ANNOT-BIT` | A `within` anchor or a register named in an annotation is not a declared bit. | Name a bit of the circuit as `reg[i]`. |
| `E-FE-CALL-UNBOUND` | A `timing.call` payload that is not `<fn> latency=<key>`. | Use that form. |
| `E-FE-STRETCH-INCONSISTENT` | The stretch equations contradict each other, or a stretch would be negative. | Check the box durations that constrain the stretches. |
| `E-FE-STRETCH-AMBIGUOUS` | A stretch variable is not determined by the program (error in strict mode). | Constrain it with a box duration. |
| `W-FE-STRETCH-AMBIGUOUS` | The same condition, non-strict: the free variable is resolved to 0. | Constrain it. |
| `E-TIME-EXACT` | A fixed duration is not an integer multiple of dt. | Fix the duration, contract or Target. |
| `N-FE-DUR-UNRESOLVED` | A note: a gate duration was not resolved because no contract was given. | Pass a contract. |

## Lint

`qtiming lint` and the SARIF report emit these for the IBM personality only.

| Code | Severity | Meaning |
| --- | --- | --- |
| `E-LINT-IBM-NESTED-IF` | error | An `if` inside an `if`. IBM takes one non-nested `if/else` per block. |
| `E-LINT-IBM-ELSEIF` | error | An `else if` chain. |
| `E-LINT-IBM-MEAS-IN-IF` | error | A measurement or reset inside a conditional. |
| `E-LINT-IBM-LOOP` | error | `for`, `while` or `switch` control flow. |
| `E-LINT-IBM-ARITH-COND` | error | Arithmetic or a shift in a condition. |
| `E-LINT-IBM-OPERAND-WIDTH` | error | A condition reading more than 32 bits. |
| `E-LINT-IBM-BOX` | warning | A `box` is present. Strip the annotations before submission. |

`E-LINT-IBM-BROADCAST`, `E-LINT-IBM-INSTR-BUDGET`, `E-LINT-Q1-COND` and `E-LINT-QUA-STRICT` are named in the source but not implemented; nothing emits them.

## Elaboration, graph and solvers

| Code | Meaning | Remedy |
| --- | --- | --- |
| `E-ELAB-POLICY-REJECTED` | The policy is not accepted by the backend's branch class. In `check` this becomes a REFUTED verdict with a `policy-incompatible` reason, not an error line. | See [Policies](policies.md). |
| `E-ELAB-Q1-NOT-EQUALISABLE` | On Q1 the two arms of an `eq` branch differ in total real-time time, or hold something other than real-time instructions. | Match instruction counts and durations, or use another policy. |
| `E-ELAB-EQ-VARIABLE-ARM` | `eq` cannot equalise an arm that contains something with a variable length. | Remove it from the arm. |
| `E-ELAB-LOOP-LIMIT` | A `for` loop or `while` cap above the unroll limit (64) that was not summarised. | Windowing summarises long top-level `for` loops (IBM only); `--no-window` turns it off. See the note below. |
| `E-ELAB-UNBOUND` | A condition reads a proposition before a measurement. | Measure first. |
| `E-ELAB-UNSUPPORTED` | A statement kind not elaborated: assignment, `switch`, call. | Not supported in 0.1.0. |
| `E-ELAB-WITHIN-ANCHOR` | The bit named by `within` is never written. | Measure into it before the box. |
| `E-GRAPH-UNSUPPORTED` | The personality cannot build the program: for IBM, nested `if` or a measurement inside an arm (a `while` counts); for Q1, an arm holding more than real-time instructions. | Restructure the program. |
| `E-GRAPH-CUT` | A long loop cannot be summarised by one window: no full-join barriers at the ends of the body, a cross-iteration dependency, or a personality or grid that windowing does not support. | Open and close the loop body with a barrier over every qubit, or keep the loop under the unroll limit. |
| `E-GRAPH-CYCLE`, `E-GRAPH-LABEL`, `E-GRAPH-LATVAR`, `E-GRAPH-PROP`, `E-GRAPH-PERSONALITY`, `E-GRAPH-UNELABORATED` | A graph invariant failed, or the builder was misused. | These indicate a checker bug. Report it. |
| `E-SMT-UNSUPPORTED` | The Tier 2 encoder meets an operator or real-time variable it does not encode. | Report it. |
| `E-INTERVAL`, `E-LABEL-OP`, `E-LABEL-UNBOUND` | Internal consistency errors in the data model. | Report it. |

## Executor

The reference executor runs counterexamples for `replay` and for every REFUTED.

| Code | Meaning |
| --- | --- |
| `E-EXEC-PARAM` | ARTIQ `commit_lead` is unspecified; the executor will not guess it. Pass `--assume timeline.commit_lead=NS`. |
| `E-EXEC-UNBOUNDED` | A latency without an upper bound was asked for a value. |
| `E-EXEC-THETA` | A supplied latency value lies outside its interval. |
| `E-EXEC-EXHAUSTIVE` | Exhaustive exploration would exceed its limit of outcome bits or latencies. |
| `E-EXEC-UNBOUND`, `E-EXEC-UNSUPPORTED`, `E-EXEC-PERSONALITY` | The executor met a program or contract it cannot run (a condition read before measurement, an unelaborated statement, a contract for another personality). |

## `I-REPLAY-MISMATCH`

The solver produced a counterexample and the independent executor did not reproduce it. The counterexample is withheld and the command ends with exit code 4. The message says this is a bug in the checker or the executor, and asks for a report.

## Note on `E-ELAB-LOOP-LIMIT`

A loop longer than the unroll limit is summarised by a window on IBM contracts. The error appears when windowing is switched off with `--no-window`, or on a personality that does not window. The hint names both remedies: raise the unroll limit, or omit `--no-window`.
