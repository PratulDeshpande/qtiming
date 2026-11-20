# Strong controllability by rewriting onto the activation points (T9)

Status: proved (direct derivation below, checked against `src/qtiming/solve/synth/sc.py`).
The rewrite is attributed in the plan to Vidal and Fargier (CEUR Vol-2509); that citation is
`[verify]`, the paper was not read for this document.

## Setting

Convention E: a requirement `(u, v, w)` means `t_v - t_u <= w`. A contingent link `(A, C, [lo, hi])`
means `C = A + theta` with `theta` chosen by nature in `[lo, hi]`, `A` executable. Assumptions
(`STNU.validate`): the contingent ends are pairwise distinct, no activation is a contingent end
(chains are first rewritten by `model.normalise`, which inserts a support node joined by two
zero-weight edges), and `lo <= hi`. Distinct links have independent `theta`s.

**Definition.** The STNU is *strongly controllable* (SC) if there is one assignment `s` to the
executable points, made without knowing any `theta`, such that for every `theta` in the box
`prod [lo, hi]` all requirements hold with `t_C = s_A + theta` for each end `C`.

## The rewrite

Every requirement mentions two points. Cases (X, Y executable; C, C1, C2 contingent ends of links
with activations A, A1, A2):

| Requirement | Quantified over theta | Worst case | Rewritten (executable only) | Code branch in `sc.py` |
| --- | --- | --- | --- | --- |
| `(u=X, v=C, w)`: `C - X <= w` | `A + theta - X <= w` | `theta = hi` | `(X, A, w - hi)` | `elif kv` |
| `(u=C, v=X, w)`: `X - C <= w` | `X - A - theta <= w` | `theta = lo` | `(A, X, w + lo)` | `elif ku` |
| `(u=C1, v=C2, w)`, different links: `C2 - C1 <= w` | `A2 + th2 - A1 - th1 <= w` | `th2 = hi2`, `th1 = lo1` | `(A1, A2, w - hi2 + lo1)` | `if ku and kv` |
| `C - C <= w` (same end) | `0 <= w` | none | constant: fails iff `w < 0` | `u == v` |
| X, Y executable | none | none | unchanged | `else` |

A requirement between `C` and its own activation `A` is the second or first row with `X = A`: it
becomes the self-loop `(A, A, w + lo)` or `(A, A, w - hi)`, a constant check `0 <= w + lo`
resp. `0 <= w - hi` that Bellman-Ford sees as a negative self-cycle if it fails
(`C - A <= w` needs `hi <= w`; `A - C <= w` needs `-lo <= w`).

(The plan's table writes the third row with `C1 - C2 <= w` and worst case "C1 max, C2 min", giving
`w - hi1 + lo2`; the code's tuple convention has `u = C1` as the *subtracted* end. Both are the
same rewrite with the roles of the two links named differently. `test_two_links_row` pins the
code's reading.)

## Theorem (T9)

The STNU is SC iff the STN over the executable points with the rewritten requirements is consistent
(has a solution). Moreover a solution `s` of the STN is an SC schedule.

*Proof.* Let `R` be the original requirements and `R'` the rewritten ones.

(1) Each requirement `r` involves at most two contingent `theta`s and they belong to different
links, so they vary independently. The condition "`s` satisfies `r` for every `theta` in the box" is
a condition `L(s) <= w + (a linear function of the thetas with coefficient +1 or -1 on each)`. A linear
function of independent variables over a box is minimised (maximised) at the corner that
minimises (maximises) each term, so the condition for all `theta` is equivalent to the same
inequality at that corner. The table lists exactly these corners (second column to fourth).
Thus, for every `s`: `s` satisfies `r` for all `theta` iff `s` satisfies the rewritten `r'`.

(2) The condition "for all `theta`, all of `R` hold" is the conjunction over `r` of "for all `theta`,
`r` holds" (the quantifier distributes over a conjunction). By (1) this is equivalent to `s |= R'`.
`R'` mentions only executable points. So an SC schedule exists iff `R'` is satisfiable over the
executable points, and any satisfying assignment is an SC schedule.

(3) `R'` is a system of difference constraints. It is satisfiable iff its constraint graph has no
negative cycle (standard; Bellman-Ford finds a cycle or a solution, `stn.bellman_ford` and
`stn.solution`). A negative cycle consists of rewritten edges, each tagged with the corner it used
(`@theta=hi`, `@theta=lo`, `@C1=hi,C2=lo`), which is the reported witness. QED

Why not "replace each link by the requirement `[lo, hi]`": that checks pseudo-controllability,
which is weaker than SC, because it lets the schedule depend on `theta`.

## Worked example (plan 12.4; `test_synth_sc.py::test_worked_example`)

`A` executable; `C = A + theta`, `theta` in `[20, 50]`; `X` executable with

- (a) `X >= C`, that is `C - X <= 0`, requirement `(X, C, 0)`;
- (b) `X <= C + D`, that is `X - C <= D`, requirement `(C, X, D)`.

Rewrite: (a) is `C - X <= w` with `w = 0`: `A - X <= 0 - hi = -50`, edge `X -> A (-50)`, i.e.
`X >= A + 50`. (b) is `X - C <= w` with `w = D`: `X - A <= D + lo = D + 20`, edge `A -> X (D + 20)`,
i.e. `X <= A + D + 20`. (The plan's text takes `D = 10` and writes the bound `X <= A + 30`.)
The cycle `A -> X -> A` has weight `(D + 20) - 50 = D - 30 = D - (hi - lo)`. So the network is SC iff
`hi - lo <= D`:

- `D = 10`: weight `-20`, not SC; the witness names (a) at `theta = hi` and (b) at `theta = lo`
  (the test checks the witness mentions `a`).
- `D = 30`: weight 0, SC, and the schedule has `X - A = 50` (the test checks this): the schedule
  waits out the worst case, which is EQ's behaviour and its idle cost.

Dynamic controllability is strictly weaker here: `X` can fire the instant `C` is observed, which
satisfies (a) and (b) for every `D >= 0`. This is the trade between EQ (SC-like, pays idle time) and
SYNC or EXP (DC-like, no wait, the timeline varies). `solve/synth/stnu_dc.py` decides DC; its rules
are UNVERIFIED (see [dc-rules.md](dc-rules.md)), so the DC half of this paragraph is the
reasoning above, not a tool result.
