# STNU dynamic controllability: rules implemented in `solve/synth/stnu_dc.py`

**Status: UNVERIFIED.** The rules below are transcribed from memory of Morris and Muscettola
(2005) and Morris (CPAIOR 2014, DOI 10.1007/978-3-319-07046-9_33), then adjusted until the
checker agreed with the independent integer game solver `bruteforce_dc.py`. They have not been
compared with the paper text. The module flag `UNVERIFIED = True` stays until the Prob-in-Ctrl
(621 networks) and CSTNU Tool gates of plan Section 12.7 pass.

## Convention E

Edge `X -> Y` with weight `w` means `t_Y - t_X <= w`. A contingent link `(A, C, [lo, hi])` has
`C = A + theta`, `theta in [lo, hi]`, `A` executable.

## Edges

| Kind | Form | Reading |
| --- | --- | --- |
| ordinary | `X -> Y (w)` | requirement `t_Y - t_X <= w` |
| lower-case | `A -> C (c: lo)` | not stored; rules R3/R4 use `lo` of the link |
| upper-case (label) | `X -> A (C: v)` | wait: `X >= A - v` unless `C` has been observed; the original one is `C -> A (C: -hi)` |

Deviation from the paper as remembered: each link also contributes two implied ordinary edges,
`C -> A (-lo)` and `A -> C (hi)`. They hold in every run, so adding them is sound, and without
them the checker accepted a deadlock (two activations each waiting for the other's contingent
end; found by the agreement run).

## Rules (applied to a fixpoint)

| Rule | Premises | Derived |
| --- | --- | --- |
| R1 no-case | `X -> Y (u)`, `Y -> Z (v)` ordinary | `X -> Z (u+v)` ordinary |
| R2 upper-case | `X -> Y (u)` ordinary, `Y -> Z (C: v)` | `X -> Z (C: u+v)` |
| R3 lower-case | link `A -> C (c: lo)`, `C -> B (v)` ordinary with `v < 0` | `A -> B (lo+v)` ordinary |
| R4 cross-case | link `A -> C (c: lo)`, `C -> B (D: v)` with `v < 0`, `D != C` | `A -> B (D: lo+v)` |
| R5 label removal | `X -> Z (D: v)` with `v >= -lo_D` | `X -> Z (v)` ordinary |

A label self-loop `Z -> Z (D: v)` with `v < 0` is a failure (an activation would wait for its
own contingent end). Ordinary self-loops with negative weight are failures.

## Verdict

DC iff the fixpoint is reached with no negative ordinary cycle (Bellman-Ford over the ordinary
edges after every pass) and no failing self-loop. The reason string lists the tags of the
derived edges on the negative cycle. Preconditions (`STNU.validate`): activations executable,
distinct contingent ends, `lo <= hi`; chains need `model.normalise`.

## Validation so far

- `tests/unit/solve/synth/test_synth_dc.py`: 1500 seeded random STNUs (3 to 6 points, 1 to 3
  links, `0 < lo < hi`, requirement weights in `[-5, 6]`) agree exactly with `bruteforce_dc.dc`
  (horizon 24). Three further seeds of 2500 networks each were also run: no disagreement.
- The oracle horizon matters: with horizon 16 one network was wrongly "not DC" because the
  needed chain was 18 ticks long. That was an oracle limit, not a checker bug.
- Not validated: more than 6 points, shared activations, non-integer bounds, `lo = 0`.
