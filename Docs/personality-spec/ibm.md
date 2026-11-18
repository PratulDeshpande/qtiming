# IBM personality specification (restricted, block model)

Normative for both the reference executor (`src/qtiming/exec/ibm.py`) and the graph builder
(`src/qtiming/dispatch/ibm.py`, P6). Golden traces: `tests/personality/ibm/golden/*.json`.
Status: frozen for P4; changes go through the decision log in the implementation plan (Section 21.2).

## Resources and time

- One resource per qubit (`q<n>`). Time is integer `dt` (the backend `dt`, from the `Target`).
- An operation on resources `R` with duration `d` starts at `max(clock[r] for r in R)` and ends `d`
  later; every `r` in `R` then has clock `end`. Gates, delays and measurements all follow this rule
  (plan 9.3). A barrier over `R` sets every clock in `R` to their maximum (tag `join`).
- Measure durations come from the contract (`durations.measure`, `durations.measure_2`), selected by
  the measure variant (`std`, `mid`).

## Feedforward

`valid(c) = end(measure) + theta_ff`, with `theta_ff` drawn from the contract latency
`measure -> branch` for the measurement's tier (`ff.default` in `ibm_heron.toml`, `[0, 600] ns`).

## `if` / `else` block

Let `R` be the qubits touched by either arm and `v` the time the condition is valid (the last valid
operand).

| Step | Rule |
| --- | --- |
| block start `bstart` | `all_resources`: `max(v, clock[r] for r in R)`, and every `r` in `R` is set to `bstart` |
| arms | the taken arm runs by the common rule from `bstart`; arms may not nest an `if` or contain a measurement (`branch.allow_nested = false`) |
| block end `bend` | `pad_to_longest_block`: `bstart + Dmax`, with `Dmax = max(D_then, D_else)`, the longest per-resource chain of each arm. `restart_at_join`: `bstart + D_taken` |
| after the block | every `r` in `R` has clock `bend` |

Under EQ elaboration a barrier and a wait of `hi` precede the block, so `bstart` does not depend on
`theta_ff` for any `theta_ff <= hi` (golden `08_eq_elaborated_is_latency_independent`).

## Named parameters

| Parameter | Values | Default | Provenance |
| --- | --- | --- | --- |
| `block_start` | `all_resources` (`per_resource` is named but not implemented: both stages refuse it) | `all_resources` | `vendor`, from IBM documentation of the old fast-path stack |
| `join_behavior` | `pad_to_longest_block`, `restart_at_join` | `pad_to_longest_block` | `vendor`, documented only for qiskit-ibm-runtime <= 0.39; to be calibrated from `scheduler_timing` evidence (plan Section 18) |

Neither value is hidden behaviour: both are contract parameters (`personality_params.ibm`).

## Not modelled

- Late events: IBM has no exposed commit model, so there is no O1. Violations are job-validation
  failures, reported by the front-end lint (plan 6.6), not by the executor.
- `SwitchCaseOp`, nested `if`, `while`, measurements inside a branch: rejected by the lint and
  refused by the executor (`E-EXEC-UNSUPPORTED`).
- Variation in feedforward latency across the two tiers of one chip: a contract concern.

## Golden cases (hand-computed)

Eight cases, listed in `tests/personality/ibm/golden/`: resource chain, multi-resource start,
feedforward validity, padded block with each arm taken, `restart_at_join`, a busy arm resource,
and the EQ-elaborated form.

## Sources

IBM Quantum documentation on dynamic circuits and fast-path control flow; the contract instance
`src/qtiming/contract/instances/ibm_heron.toml` carries the per-number source strings.
