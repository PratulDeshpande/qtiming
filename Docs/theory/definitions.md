# Definitions

Source of truth: plan Sections 9, 10, 11, 13 and 15.2; where this file and the code differ, the
code (`src/qtiming/graph/lteg.py`, `solve/`) was read and this file says what the code does.
Theorem statuses are in [index.md](index.md); the arguments are in [theorems.md](theorems.md).

## 1. Semantic objects

- **Program, contract.** `P` is an elaborated program (`elab.elaborate`), `C` a timing contract
  with a personality (`ibm`, `artiq`, `q1`, `qua`).
- **Outcomes.** `Omega_P` is the set of assignments `omega` of 0/1 to the bit propositions (one per
  measurement occurrence). Derived propositions (conditions such as `a xor b`) are computed from
  `omega` by `lteg._env`; they add no freedom.
- **Latencies.** The LTEG carries one `LatVar` per contingent latency *occurrence*, with integer
  bounds `lo` and `hi` (`hi` may be `None` = unpublished). `Theta_C` is the box
  `prod_i [lo_i, hi_i]`; a realisation `theta` is a point of it (rationals are allowed; the solver
  returns exact `Fraction`s). Existence of nodes depends on `omega` only, never on `theta`.
- **Times** are in dt, exact rationals (`Fraction`). Constant edge weights are integers.

## 2. The LTEG and fixed dispatch (plan 9.1)

An LTEG `G` is a DAG: nodes `v` with a label (conjunction of literals over propositions), an optional
`snap` grid `g`, and edges `e = (src, dst, w, label)` with `w` an integer or a `LatVar`. Builders
create nodes in topological order (invariant I1: every edge has `src < dst`). For fixed
`(omega, theta)`:

    exists(v)  iff  omega |= label(v)  and  (v = origin  or  some in-edge of v is active)
    active(e)  iff  omega |= label(e)  and  exists(src(e))
    t(origin) = 0
    t(v) = snap_v( max over active in-edges e of ( t(src(e)) + w(e) ) )        (v existing)
    snap_v(x) = g * ceil(x / g) if v.snap = g, else x

This is `lteg.dispatch_times`. It is a maximum, not a system of difference constraints: the
hardware fires each event as soon as its last active predecessor allows. `exec_C(P, omega, theta)`
of plan 15.1 is, by the conformance claim T8, the same function computed by the independent
executor `qtiming.exec`.

Consequences used later (all immediate from the recursion): `t(v)` is monotone non-decreasing in
every `theta_i` and in every constant weight; without snap, `t(v)` is the maximum, over paths from the
origin that are active under `omega`, of the sum of the path's weights.

**Status of snap in this repository.** `Node.snap`, `dispatch_times`, Tier 1 and Tier 2 support it, but
no dispatch builder (`graph/builder.py`, `dispatch/*.py`) sets it as of this commit. Grid
alignment is checked by the `Mod` obligation O8 instead. Statements below that say "snap-free" are
therefore true of every graph the pipeline builds today and matter only for hand-built graphs and
for future builders.

## 3. Obligations (plan 10)

An obligation `o = (code, guard, check, deps, assumptions, hard, severity)` is a claim about the
dispatch, never a constraint added to the graph. `guard` is a label: `o` is only required under
outcomes satisfying it. `check` is one of (`oblig/model.py`):

| Check | Meaning, for the fixed dispatch |
| --- | --- |
| `Diff(x, y, op, c)` | for every `(omega, theta)` with the guard true and `x`, `y` existing: `t(x) - t(y) op c`, `op` in `<=`, `>=` |
| `Variation(x, y, B)` | `max - min` of `t(x) - t(y)` over all `(omega, theta)` with the guard true and both existing is `<= B` (two independent executions) |
| `Mod(x, g, r)` | `t(x) = r (mod g)` for every execution where `x` exists |
| `Events(kind, items, params)` | O5: a concrete event list checked by the personality's rules (SED lanes, collisions, ...) |

Codes O1 to O9 (plan 10.2): O1 no underflow, O2a result valid when consulted (causality), O2b no stall
(EQ), O3 deadline, O4 gap variation, O5 capacity, O6 blocking call, O7 join determinism, O8 grid,
O9 loops. A `deps` set lists the `LatVar`s in the obligation's cone of influence.

**Safe(P, C)** (plan 15.2): every obligation of severity `safety` holds. `DMO`, `Delta-DMO` and
`Safe-only` are as in plan 15.2 (safety + causality + trace or time independence of `theta`).
They quantify over executions of the *fixed* dispatch, not over schedules; the research report's
"EXP safe iff DC" is false as stated (plan 15.3).

## 4. Solvers and verdict soundness (plan 11, 13)

| Tier | What it computes | Direction |
| --- | --- | --- |
| 0 (`solve/concrete.py`) | direct evaluation of the dispatch over all `omega` when the cone has no `LatVar` | exact: proves and refutes |
| 1 (`solve/interval.py`) | for each node a max of affine forms `Fmax` (upper) and `Fmin` (lower) in the `theta`s | may only prove (T1) |
| 2 (`solve/smt.py`) | QF_LRA + Booleans encoding of the dispatch, `UNSAT` of the negated obligation | proves and refutes (T2); a SAT that depends on an unbounded latency is UNKNOWN |
| 3 (`solve/synth/`) | controllability of a relaxed network (T5, T6, T9) | off the verification path; never imported by Tiers 0 to 2 |

A **verdict** is the minimum, in the order REFUTED < UNKNOWN < PROVED-UNDER < PROVED, of the
per-obligation results (plan 13.1). The verdict soundness claim, in the form the code supports:

1. PROVED or PROVED-UNDER: every safety obligation holds for every `(omega, theta)` in the box
   given by the stated assumptions. This rests on Tier 0 being exact (it is the dispatch itself),
   on T1 for Tier 1 and on T2 for Tier 2 (UNSAT side).
2. REFUTED: a concrete `(omega, theta)` was found, minimised, and **replayed in the independent
   executor** (`verdict.replay`); a mismatch is `I-REPLAY-MISMATCH` and exit 4, never a verdict. So
   REFUTED does not depend on T2's SAT side, only on the executor agreeing with the graph (T8).
3. UNKNOWN is always allowed.

Hence nothing in the soundness of PROVED depends on T3, T4 (windowing can be disabled with
`--no-window`), T5, T6, T7 or T9; windowed PROVED does depend on T4.
