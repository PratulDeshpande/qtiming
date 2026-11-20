# Theorems, with honest status

Allowed statuses: `proved` (complete proof written out here and checked), `proof-sketch`,
`conjecture`, `tested-only`, `reduced-statement` (a weaker statement than the plan's is proved;
the section says which). Definitions: [definitions.md](definitions.md). Table: [index.md](index.md).
Notation: `G` an LTEG, `omega` an outcome assignment, `theta` a latency realisation, `t` the
dispatch time function. Convention E (`X -> Y (w)` means `t_Y - t_X <= w`) is used for networks.

Papers are cited only where the plan names them; anything not read for this document is marked
`[verify]`.

## T1

Tier 1 soundness. If Tier 1 proves obligation `o`, then `o` holds for every `(omega, theta)`.

Status: proof-sketch

Argument (`solve/interval.py`). Fix a guard. Invariant: for every `(omega, theta)` satisfying the
guard and every existing node `v`, `t(v) <= max over Fmax[v]` and `t(v) >= max over Fmin[v]`, where a
form is `c + sum a_i theta_i`. Induction over creation (= topological) order: `Fmax[v]` collects
`term + w(e)` over every in-edge that can be active under the guard (monotonicity of `+` and `max`);
`Fmin[v]` collects the same only over in-edges *guaranteed* active under the guard, which is valid
because `t(v)` dominates every active in-edge term. Pruning drops duplicates and terms dominated for
every theta, and collapsing past `K` terms to a constant is an over- (resp. under-) approximation. A
snapped node is bounded by `g*ceil(.)` of the constant bounds (ceil is monotone). `diff_upper` and
`diff_lower` bound `t_x - t_y` termwise, so a proved `Diff` or `Variation` holds.

What is not yet a proof, and two defects found while checking it against the code:

1. **False proof (confirmed by running it).** In `forms`, a snapped node whose upper form contains
   an unbounded latency (`hi = None`) is skipped (`continue`), so it is absent from `fmax`. Every
   later node then silently ignores that in-edge (`e.src not in fmax`), and `tier1` returns
   `proved` with reason "vacuous: a node cannot exist under the guard" when the obligation's own node
   is missing. Hand-built graph `origin -> a (0)`, `a -> s (latency [0, None])`, `s` snapped to 4,
   obligation `t(s) - t(a) <= 0`: `verify` returns `proved` (tier 1). This contradicts the
   statement above, so the status cannot be `proved`. It is unreachable from the pipeline today
   only because no builder emits snap nodes (definitions.md section 2); it is a latent soundness bug.
   "Node absent from `fmax`" conflates "cannot exist" with "bound not computable".
2. `Fmin` defaults to the constant 0 when no in-edge is guaranteed active ("times are
   non-negative"). That is valid only if every constant weight is non-negative, which no invariant
   enforces (I6 checks only that weights are integers). True of all current builders (durations and
   costs), but a hypothesis.

Tests: `tests/property/test_soundness.py::test_proved_obligations_are_never_violated`,
`tests/property/test_tier_properties.py::test_tier1_containment_property_11`,
`tests/unit/solve/test_appendix_a.py`, `tests/unit/solve/test_smt.py::test_tier2_agrees_with_tier1_whenever_tier1_proves`.
Mechanisation: not done (plan 15.6).

## T2

Tier 2 exactness. The encoding in `solve/smt.py` has a model `(omega, theta, t)` iff `t` is the
dispatch time function of `(omega, theta)` on existing nodes; so UNSAT proves the obligation and
SAT yields a violating execution.

Status: proof-sketch

Argument. The encoder introduces per node `v` a real `pre_v` with `pre_v >= term_e` for every
active in-edge `e` and, if `v` exists, `pre_v = term_e` for some active `e`; hence `pre_v` is the
maximum of the active terms; `t_v = pre_v` or `t_v = g * -floor(-pre_v/g)` (= `g*ceil(pre_v/g)`).
Induction over topological order gives uniqueness of `t` on existing nodes given `(omega, theta)`;
nodes that do not exist have unconstrained `t`, but every use is guarded by `ex`.

Hypotheses the sketch needs and that the code supplies only indirectly:

- **Label closure.** `ex[v]` is the node *label*, not "label and some in-edge active". If a label
  holds but no in-edge is active, `Implies(ex, Or([]))` forces `ex` false, so that scenario is
  silently excluded (an unsound pruning). Invariant I3 (`graph/invariants.py`) checks that this
  never happens, but only by enumerating `omega` when there are at most 12 bit propositions and
  only at `theta = lo` (sufficient, since existence does not depend on `theta`).
- **Integer semantics.** Derived propositions are encoded in 32-bit vectors; this equals Python
  integer evaluation only when no intermediate value overflows. `EVar` and division are rejected
  (`E-SMT-UNSUPPORTED`, result UNKNOWN). `Events` (O5) is not encoded (UNKNOWN).
- **Unbounded latency.** SAT with an unbounded `LatVar` in the cone is reported UNKNOWN, so SAT
  is a refutation only for bounded cones; UNSAT is unaffected (a larger box only adds models).

Tests: `tests/unit/solve/test_smt.py`; `tests/property/test_vertex_lemma.py` (Tier 2 verdict equals
brute-force dispatch evaluation at all box vertices, which cross-checks both directions of the
equivalence on random programs); every SAT is also replayed in the executor.

## T3

EQ implies DMO. If every branch is EQ, loops are bounded or capped, calls have bounded latency, and
O2a, O2b, O7 (with `Delta_eff = 0`) hold for every branch, then `P` is DMO.

Status: proof-sketch

Argument. Let `V` be the nodes of kind `valid` (result-arrival points). If no `V` node is ever the
strict maximiser of an in-edge max (this is what O2b asserts at every arm start; the other `V`
in-edges are `ibm.cond-valid` and `cond-operand`), deleting `V` and its out-edges changes no dispatch
time, by induction over topological order. If, in addition, every latency-carrying edge enters a `V`
node, the valid-free graph has no `theta`, so all times are independent of `theta`; outcome
independence of the join time is O7 with `Delta_eff = 0`; causality is O2a.

Gaps: (a) the second hypothesis is **false for QUA**: `dispatch/qua.py` puts the `align` latency on
an edge `j -> last` that does not enter a `valid` node, so the argument does not cover QUA (it
covers IBM, where the only latency edge is `feedforward` into `valid`, and ARTIQ's `in2cpu`).
(b) "Never the maximiser" must be read as "not strictly larger than another active term", since
ties are harmless. (c) DMO's trace equality includes which events exist, which depends on `omega`
only; the sketch does not address trace equality across different `omega`, which DMO as written in
plan 15.2 quantifies per `omega`. No test exercises T3 directly.

## T4

Windowed composition. If the cut rules hold, the obligations of the whole program hold if they
hold in every window analysed with `J` as origin.

Status: proof-sketch

The argument and its evidence are in [T4-windowing.md](T4-windowing.md). Differences from the plan:

- The plan states "iff"; the existing argument (and `graph/window.py`) claims only the direction
  *windows PROVED => whole program holds*, which is the only one the tool relies on. A refuted
  window is refuted in the whole program only when the iteration is reachable, which is not
  argued.
- The plan applies windowing to every personality with a summarised state (9.7 rule 4); the code
  windows only `ibm` and refuses ARTIQ, Q1 and QUA (`E-GRAPH-CUT`, UNKNOWN). The differential test
  found a QUA cross-cut O4 gap, which is why.
- "All differences independent of `t(J)` (dispatch is shift invariant)" is true without snap
  and with grids of 1 dt, and fails for a snapped node unless `t(J)` is aligned to its grid. The
  code refuses any contract with a grid coarser than 1 dt (rule 5).

Tests: `tests/differential/test_window_vs_whole.py`, `tests/unit/graph/test_window.py`.
Nothing in soundness of the non-windowed path depends on T4.

## T5

Rigid equivalence. For rigid graphs, `DC(N_rigid(P) + obligations)` iff all obligations hold for all
`(omega, theta)`.

Status: reduced-statement

What is proved (complete proof below): fix `omega`. Let `G` be rigid in the sense of
`synth/rigid.py` (no snap; the in-edges of every node have pairwise exclusive labels), with every
constant weight `>= 0`, every latency bounded, and let the obligations be `Diff` checks. Let
`N = relax(G, obligations, omega, strategy=False)`. Then `N` is dynamically controllable iff every
obligation holds for every `theta` in the box.

*Proof.* Under `omega` each existing non-origin node `v` has exactly one active in-edge (at least one
by existence, at most one by rigidity); the active edges form a tree rooted at the origin. `N` has a
point per existing node and a fresh contingent end `c_e` per latency edge `e`. For a constant edge
`u -> v (w)` it imposes `t_v - t_u = w` (two inequalities); for a latency edge it imposes the link
`t_{c_e} - t_u in [lo, hi]` and `t_v = t_{c_e}`. Obligations are requirement constraints on node
points. So in every situation (every `theta`) the equalities force `t_v` to equal the dispatch time
`t(v; omega, theta)` and no other schedule satisfies them.
(=>) If `N` is DC, a winning strategy produces for each `theta` a schedule satisfying all
requirements; that schedule is the forced one, so every obligation holds at the dispatch times, for
every `theta`.
(<=) Suppose every obligation holds for all `theta`. Strategy: execute the origin at 0; execute `v`
at `t_u + w` after its parent `u` has executed if the edge is constant, and at the instant `c_e` is
observed if the edge is a latency edge. Because `w >= 0` the decision never refers to the past, and
it uses only observations already made, so it is dynamic; it satisfies every equality by
construction and the obligations by hypothesis. Zero-delay reaction to an observation is the
standard convention of dynamic controllability. QED

Where the plan's statement is stronger than this and false or unsupported:

- **Non-negative weights are needed.** Counter-example (run): `origin -lat[0,10]-> a`, `a -(-3)-> b`,
  obligation `t(b) - t(origin) <= 7`. The graph is rigid, `verify` returns `proved`, and
  `stnu_dc.dynamically_controllable` returns `dc = False`: `b` must execute 3 before `a`, i.e.
  before the latency has been observed. Nothing in `graph/invariants.py` forbids negative weights;
  the current builders do not emit them (durations, costs and zeros), so for built graphs the
  hypothesis is believed to hold but is not enforced.
- Only `Diff` obligations are encoded; `Variation`, `Mod`, `Events` are skipped with a note in
  `Relaxed.notes`, and the equivalence says nothing about them.
- The relaxation is per `omega` (no conditional/CSTNU network).
- The plan's remark that strong controllability is strictly stronger is confirmed: with a
  latency of `lo < hi` the equality `t_v = t_c` has no `theta`-independent schedule
  (`strongly_controllable` returns False on the equality encoding of a 2-node chain with box
  `[2, 9]`).
- **Evidence is thin.** The plan promises a property test over random rigid graphs against both
  Tier 2 and an external CSTNU Tool. The only test is
  `tests/unit/solve/synth/test_synth_relax.py::test_t5_on_a_rigid_graph_dc_agrees_with_verification`,
  five parameter points on one 2-node chain, with the DC decision made by `solve/synth/stnu_dc.py`, whose
  own header says UNVERIFIED (`dc-rules.md`) and which is not validated for `lo = 0`, the lower bound used here.

## T6

Necessary condition. If `P` is safe under its dispatch then `N_geq(P)` with the obligations is
dynamically controllable.

Status: reduced-statement

What is proved is stronger in one respect (strong, not merely dynamic, controllability) and
narrower in others. Fix `omega`; let all latencies of existing edges be bounded, obligations be
`Diff` checks, and let `N = relax(G, obligations, omega)` (default `strategy=True`: every
dispatch edge `u -> v (w)` becomes the requirement `t_v - t_u >= w`; every latency edge becomes a
contingent link `u -> c` plus `t_v - t_c >= 0`; snapping is dropped). If every obligation holds for
all `theta` then `N` is **strongly controllable**, hence dynamically controllable.

*Proof.* Take `theta* = hi` componentwise and `S = t(.; omega, theta*)`, the dispatch times of the
existing nodes. Assign `S` to the executable points (a single schedule, chosen without knowing
`theta`). Constant edge: `S_v >= S_u + w` because `S_v` is a maximum over in-edges (and
snapping, if present, only increases it, since ceil never decreases a value). Latency edge with end `c = S_u + theta` for
an arbitrary `theta <= hi`: `S_v >= S_u + hi >= c`. Obligation: `S` is the dispatch at one
`theta`, so each `Diff` holds by hypothesis. So `S` satisfies every constraint for every `theta`.
Strong controllability implies dynamic controllability. QED

Notes on the plan's text:

- The plan states DC and builds the argument on "the dispatch is a strategy"; that argument also
  works but gives less. The code's own test (`test_relaxed_sc_is_necessary_for_the_dispatch_being_safe`)
  asserts the stronger SC, which is what is proved here.
- "T6 needs snap dropped": snap is dropped by `relax`, and dropping is harmless as shown above
  (dropped constraints only enlarge the feasible set). No builder emits snap nodes today.
- The code differs from plan 12.2 by inserting a fresh contingent end `c` per latency edge and the
  requirement `t_v >= t_c` (so a node with several latency in-edges, or a latency end that
  activates another link, stays well formed). It is a refinement, not a different network.
- Not covered: `Variation`, `Mod`, `Events` obligations; labelled (CSTNU) networks; an unbounded
  latency (`relax` raises `Unbounded`, the theorem does not apply). The converse is false (plan 12.2).

Tests: `tests/unit/solve/synth/test_synth_relax.py::test_relaxed_sc_is_necessary_for_the_dispatch_being_safe`
(four small cases at `omega = {}`; it compares to Tier 1 verdicts, not to a proof).

## T7

Delta-DMO from SYNC. If branches are SYNC with O7 bounds `Delta_k`, then `P` is Delta-DMO with
`Delta_e` the sum of `Delta_k` over the joins before `e`; a join that re-anchors to an absolute point
restarts the sum.

Status: conjecture

Nothing in `src/` computes or reports `Delta_e`, no test exercises it, and the plan's statement
does not define when a join "re-anchors". Plausible route: `t_e - t_e'` over two executions is
bounded by telescoping the O7 variation of each join along the path to `e`; the telescoping
step needs each `Variation` to bound the difference between *two executions that may take
different branches*, which is what the two-copy encoding of `Variation` checks, but the
re-anchoring clause is unproved. Reported as a property only; no tool soundness depends on it.

## T8

Conformance. For every personality, graph evaluation `evaluate_graph` and the executor agree on all
event times and violations.

Status: tested-only

Backed by `tests/differential/test_graph_vs_executor.py` (1000 random programs per personality
and policy, 12 pairs) and the hand-computed goldens in `tests/personality/*/golden`. The executor
is written from `Docs/personality-spec/` separately from the builder (import-linter enforces that
`exec` does not import the graph side). No proof, not even for IBM-EQ. Because REFUTED is
replay-checked in the executor, T8 is what makes a REFUTED trustworthy.

## T9

Strong controllability reduction. For an STNU with distinct contingent ends and executable
activations, the Vidal-Fargier rewrite (`synth/sc.py`) yields an STN over the executable points
that is consistent iff the STNU is strongly controllable.

Status: proved

Complete proof and the worked example are in [sc-derivation.md](sc-derivation.md). The plan lists
T9 as `[cited]`; the proof there is a direct derivation, not a transcription. The citation (Vidal and
Fargier; CEUR Vol-2509, as named in the plan) is `[verify]`: the paper was not read for this
document. The proof does not depend on it.

Tests: `tests/unit/solve/synth/test_synth_sc.py` (worked example, row-by-row constants, and 600
random STNUs whose returned schedule is replayed at `lo`, `hi` and the midpoint of each link; this
checks the "consistent => SC" direction on examples only, the converse rests on the proof).

## T10

Vertex lemma. In a graph without snap nodes in which every latency occurrence labels exactly one
edge, for fixed `omega` and any two nodes `x, y` that exist under `omega`, the function
`theta -> t_x - t_y` is monotone in each coordinate `theta_i` separately; hence it attains its
maximum and minimum over the box at a vertex (every `theta_i` in `{lo_i, hi_i}`). Consequently a
`Diff` or `Variation` obligation is violated iff it is violated at some `(omega, vertex)`.

Status: proved

*Proof.* Existence does not depend on `theta`, so fix `omega`. Unrolling the recursion without snap,
`t_v` is the maximum over the paths `p` from the origin that are active under `omega` of
`c_p + sum of the latencies on p`. The graph is acyclic and each latency is on exactly one edge
(invariant I5, enforced by `check_invariants`), so a path contains each `theta_i` at most once.
Fix all coordinates but `theta_i`: `t_v(theta_i) = max(A_v, B_v + theta_i)` where `A_v` is the maximum over
paths avoiding the edge of `theta_i` (constant) and `B_v` the maximum over the other paths
(either may be absent). Hence `t_v` is non-decreasing and piecewise linear with slope
`s_v(theta_i) = 1[theta_i > a_v]`, with `a_v = A_v - B_v` (`+inf` if no path uses the edge, `-inf` if
all do). For `d = t_x - t_y` the slope is `1[theta_i > a_x] - 1[theta_i > a_y]`: if `a_x <= a_y` it is
`>= 0` everywhere, otherwise `<= 0` everywhere. So `d` is monotone in `theta_i`. Given any `theta`,
move `theta_1` to whichever endpoint does not decrease `d` (resp. does not increase it, for the
minimum), then `theta_2`, and so on; after `n` steps every coordinate is at an endpoint and `d` has not
got worse. For `Variation`, `max` of `d` over `(omega, theta)` is the maximum over `omega` of the
per-`omega` maximum (and likewise the minimum), so vertices suffice. For a `Diff`, a violated
inequality is a violated bound on the maximum or minimum. QED

Hypotheses that matter, and what they exclude:

- **Snap.** The proof uses the path-maximum form; `ceil` breaks it (the plan says this). No builder
  emits snap nodes today, so the lemma applies to every graph the pipeline builds; for hand-built
  snapped graphs the oracle is not exact.
- **Bounded boxes.** With `hi = None` the supremum is approached, not attained; Tier 2 treats such cones
  as UNKNOWN.
- **`Mod` and `Events` are not covered.** `verdict/minimise.py` moves latencies to endpoints for
  `Diff` and `Mod` obligations citing this lemma; for `Mod` it is only a heuristic, but it is harmless
  because a change is kept only if the exact Tier 0 evaluation still shows the violation.
- **Executor ground truth.** `bench/truth.py` uses vertices as exact ground truth for per-run executor
  violations (RTIO underflow, stale read, ...). That these are `Diff`-type conditions on the same
  times is assumed here, not proved; the file already limits the claim to snap-free programs and to
  per-run violations.
- Distinct `LatVar`s must have distinct `occurrence` keys, since `dispatch_times` looks `theta`
  up by that string; the builders construct them from the consumer's node id.

Tests: `tests/property/test_vertex_lemma.py::test_tier2_equals_vertex_enumeration` (random programs,
IBM and QUA policies, at most 6 propositions and 5 latencies each, 40 seeds by default).
