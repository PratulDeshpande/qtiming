# Status and limits

qtiming is alpha, version 0.1.0. This page states what is built, what is unverified and what a verdict does not cover. The same facts are in `README.md` ("Status and limitations") and `CHANGELOG.md`.

## What is built

- Front end: OpenQASM 3 and Qiskit circuits, `timing.*` annotations with OpenQASM 3 and QPY round trips, stretch resolution, the IBM structural lint.
- Elaboration of the three policies, and unrolling of `for` loops and capped `while` loops (unroll limit 64).
- A timed event graph and dispatch rules for four personalities: IBM, Q1, ARTIQ, QUA.
- Obligations O1, O2a, O2b, O3, O4, O5 and O7. [Obligations](obligations.md) says which personality produces which.
- Three solver tiers: Tier 0 exact, Tier 1 interval (proves only), Tier 2 Z3 (needs the `z3` extra).
- Counterexamples that are minimised and replayed in a reference executor written separately from the graph side. A mismatch is `I-REPLAY-MISMATCH`.
- Reports in text, JSON, SARIF 2.1.0 and HTML. Commands `check`, `explain`, `lint`, `replay`, `repair`, `evidence` and `contract validate|show|diff`.
- Windowing: a top-level `for` loop above the unroll limit is summarised by one iteration window if it meets the cut rules, for IBM only.
- Qiskit passes `TimingCheck`, `EqualizeBranches`, `StripTimingAnnotations` and a scheduling-stage plug-in. See [Qiskit](qiskit.md).
- `qtiming repair` for O1 failures only. Every patch is re-verified.
- `qtiming-bench` and 56 benchmark programs in eight families (`benchmarks/families`).

## Not built

- Obligations O4a, O6 (blocking calls), O8 (timing grid), O9 (loop windows) and O7 for `sync` with a spread bound are not generated. Every report lists them under "not checked by this build". A PROVED or PROVED-UNDER verdict says nothing about them.
- O5 has no symbolic encoding. On ARTIQ, O5 is UNKNOWN for every program I ran, so ARTIQ results do not reach PROVED or PROVED-UNDER when an O5 obligation is generated.
- Repeat-until-success formulas exist in code (`verdict/rus.py`) but are not wired into `check`.
- `qtiming synth` does not exist. The Tier 3 synthesis algorithms are library code that `repair` uses.
- The `delta` and `gap` arguments of `sync(...)` are parsed and unused.
- The annotations `pmin`, `call`, `declared_idle` and `cut` are accepted but have no effect that I found.
- Windowing applies to IBM only, and only to top-level `for` loops. QUA and the others unroll or stop with `E-ELAB-LOOP-LIMIT` or `E-GRAPH-CUT`.
- The IBM personality supports one non-nested `if/else` per block, with no measurement inside an arm, and no loops. A capped `while` therefore does not run on `ibm_heron`.
- Q1 accepts only the `eq` policy for predicated branches, and only for arms made of real-time instructions of equal total time.
- Two lint rules, `E-LINT-IBM-BROADCAST` and `E-LINT-IBM-INSTR-BUDGET`, and the Q1 and QUA lint rules are named in the source but not implemented.

## Unverified

- **Contract numbers are unpublished or vendor claims.** Where a vendor has not published a number, the shipped contract leaves it absent, and the dependent obligation is UNKNOWN or the run stops with `E-CT-MISSING`. IBM gate durations come from an unofficial snapshot of one backend. The IBM feed-forward latency (0 to 600 ns) is a vendor claim with a conservative lower bound; that is why IBM results are PROVED-UNDER. The QUA `align.*` latencies are placeholders. The ARTIQ `commit_lead` is unpublished.
- **No real IBM evidence.** `experiments/ibm_dryrun/` can collect `scheduler_timing` from dry-run jobs, but no hardware data is in the repository. `tests/fixtures/evidence/` is synthetic. `qtiming evidence` refuses synthetic jobs unless `--allow-synthetic` is given.
- **The dynamic-controllability checker is flagged UNVERIFIED** (`solve/synth/stnu_dc.py`, [DC rules](theory/dc-rules.md)). Its rules were transcribed from memory and not checked against the paper or the 621-network oracle suite. It is used for synthesis and repair, not for verdicts.
- **Theory status.** [The theory index](theory/index.md) gives each theorem its own status. T1 (soundness of Tier 1) is a proof sketch, T3 does not hold for QUA, T4 (windowing) is a proof sketch, T5 and T6 are reduced statements, T7 is a conjecture and T8 (executor and graph agree) is backed by tests only. Nothing is mechanically proved. The T1 section of `theorems.md` describes a false-proof defect in Tier 1 for graphs with snapped nodes; `CHANGELOG.md` records it as fixed in 0.1.0. The theory page text predates the fix.
- **The benchmark expectations are a regression snapshot.** `benchmarks/expected.json` records what the checker did, not ground truth.
- **Hardware- and oracle-backed claims cannot be reproduced offline.** That covers IBM jobs and the CSTNU Tool comparison.

## Fixed in 0.1.0

The 0.1.0 changelog lists three checker fixes found while building the benchmarks. A capped `while` whose body re-measures the tested bit no longer unrolls into contradictory arms. The QUA `while` bug, where a join over an empty qubit set had a label and no in-edge (`E-GRAPH-LABEL`), is fixed: the graph now matches the executor. The Tier 1 false proof on snapped nodes downstream of an unbounded latency now stays unproved.
