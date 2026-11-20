# T4: windowed checking is sound (status: proof sketch, tested)

**Claim.** Let `P = pre ; for n { B } ; post` and let `W(B)` be the body checked as one iteration
window and `R` the program `pre ; J ; post` with the loop replaced by its opening join `J`. If the
cut rules in `src/qtiming/graph/window.py` hold, then `check(R)` and `check(W(B))` both PROVED
(or PROVED-UNDER with the same assumptions) implies every obligation of the fully unrolled `P`
holds.

**Why.** (1) Full join: a barrier over every qubit sets all lanes to one time `t(J)`, so the
timed state entering each iteration is `t(J)` plus per-iteration offsets, independent of earlier
iterations. (3) No obligation crosses the cut: every obligation of `P` is local to `pre`, `post`
or one iteration, and the iterations are copies of `W(B)` with fresh propositions, so an
obligation of iteration k holds if it holds for `W(B)` for every latency in its box (the boxes
are the same each iteration, and latencies vary independently per occurrence). (4) Canonical
state: for `ibm` the barrier is exact, so `t(J)` is the whole state; this is the only personality
for which the argument goes through. (5) Grid residue: with every grid at 1 dt the residue is 0.

**Disabled when** any rule fails: no opening or closing full join; a bit read outside the body
that wrote it; a personality other than `ibm` (ARTIQ SED lanes, Q1 RT queue, QUA align latency);
a contract grid coarser than 1 dt. The check then returns UNKNOWN naming the rule
(`E-GRAPH-CUT`); `--no-window` restores the plain unroll-or-fail behaviour.

**Evidence.** `tests/differential/test_window_vs_whole.py` (equal verdicts wherever both are
feasible), `tests/unit/graph/test_window.py` (refusals per rule, H3 smoke).

**Open.** A mechanised proof; the periodic-cut variant with state that is not a single join.
