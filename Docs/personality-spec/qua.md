# QUA personality specification (resync, implicit aligns)

Normative for the reference executor (`src/qtiming/exec/qua.py`) and the graph builder
(`src/qtiming/dispatch/qua.py`, P6). Golden traces: `tests/personality/qua/golden/*.json`.
Status: frozen for P4; changes go through the decision log (plan Section 21.2).

## Resources and time

One resource per quantum element (`elem:q<n>`). Operations follow the common rule: an operation
starts when every resource it uses is ready (plan 9.3). A measurement result is valid at
`end + theta`, with `theta` the contract latency `measure -> branch` (`active_reset`, 224 ns).

## Alignment

An element is **dynamic** if its clock depends on an outcome or on an uncertain gap.

- `barrier` over elements `E` is an `align`. Join `j = max(clock[e])`. If any `e` in `E` is dynamic
  the align is non-deterministic and adds a gap `theta_align` drawn from
  `align.<tier>` (`align_tier`, default `same_fem`): `align = j + theta_align`. Otherwise it adds no
  gap. Afterwards all of `E` has clock `align` and none is dynamic.
- `if`/`else` over participating elements `P` (touched by either arm), condition valid at `v`:
  - default (implicit align): all of `P` are set to `max(v, clock[e])`, then aligned as above
    (non-deterministic if any is dynamic). Tags `ialign` (before the gap) and `align` (after).
  - `skip_implicit_align = true` (compiler flag `skip-add-implicit-align`): each element starts at
    `max(v, clock[e])` with no align and no gap.
  - The taken arm runs per element. There is **no implicit join after the block**: afterwards all of
    `P` are dynamic, so a later `align` pays `theta_align`.
  - Exception: a single `Gate` or `Delay` on one element with no `else` compiles to a conditional
    play with an equal-length wait on the false path; the element stays non-dynamic.

## Named parameters

| Parameter | Default | Provenance |
| --- | --- | --- |
| `personality_params.qua.align_tier` | `same_fem` | topology choice; `cross_fem`, `cross_chassis` also exist |
| `personality_params.qua.skip_implicit_align` | `false` | QM compiler flag |
| `personality_params.qua.strict_timing` | `true` | `strict_timing_`; a non-deterministic align with non-zero uncertainty is a lint error (`E-LINT-QUA-STRICT`), not an executor event |
| `align.*` bounds | `[0, 12]`, `[0, 24]`, `[0, 48]` ns | **illustrative placeholders**: only "a few cycles" is published; flagged `placeholder = true` |

## Not modelled

Broadcast and cross-core measurement implicit aligns (always added, not suppressible), `while_` and
`switch_`, real-time variables, and the exact compiled wait lengths.

## Golden cases (hand-computed)

Seven cases: a deterministic align, measurement validity, an `if` followed by a non-deterministic
align, an implicit align after a dynamic element, skip versus implicit align on two elements, and a
single conditional play that stays deterministic.

## Sources

QM documentation (`align`, implicit align, `strict_timing_`, active reset); per-number source
strings in `src/qtiming/contract/instances/qua.toml`.
