# qtiming: Repository Implementation Plan v2 (validated)

## 0. Title, date, status, how to read this document

| Field | Value |
| --- | --- |
| Project | `qtiming`: a static timing checker for dynamic quantum circuits |
| Document | Implementation Plan v2 (validated) |
| Date | 2026-11-17 |
| Supersedes | "Timing Checker: Technical Implementation Plan" (v1, 2026-10-26) |
| Status | Draft for build. Validated against vendor documentation and literature as of 2026-11-17; items still unverified are marked **[verify]** |
| Audience | The researcher-engineer who builds the repository, and the advisor who reviews the design |
| Scope | The complete version: four contracts, four executor personalities, three branch policies, bounded loops, windowing, SMT tier, a full synthesis/controllability module, Qiskit passes, CLI, SARIF, benchmarks, differential testing, artifact, docs site, IBM evidence pipeline. There is no reduced MVP and no calendar or hour budget. Phases are ordered by dependency and closed by checkable gates (Section 20). |
| Inputs consulted | v1 plan; research report "Timed semantics for dynamic quantum programs"; plain-language "Timing rulebook for quantum computers"; the validation pass and user decisions of 2026-11-17 |

### How to read this document

- Section 1 lists everything v1 got wrong or left open, each with an ID (F1, F2, ...). Later sections cite these IDs, so every changed design choice is traceable. Section 21 (decision log) and Appendix B (traceability matrix) close the loop.
- Sections 2 to 4 give the vision, architecture and repository layout. A builder can create the empty skeleton from Section 4 alone.
- Sections 5 to 14 are the implementation specification, one subsystem per section, with real Python code where the design is subtle (data model, Z3 encoding, executor engine).
- Section 15 is the theory track. It states what is a definition, what is a theorem to be proved, and what is only a conjecture.
- Sections 16 to 19 cover testing, evaluation, IBM evidence, packaging.
- Section 20 is the build order. Section 21 holds risks and the decision log.
- Appendix A re-does the worked example under the new semantics and shows, side by side, the false proof that v1's encoding would have produced.
- Conventions: all times are in `dt` (integer) unless a unit is written. "Illustrative" means a number chosen to make an example concrete, not a measured or published value. **[conjecture]** marks a claim not yet proved. **[verify]** marks a fact that should be re-checked against its source before it is relied on in a paper.

### One-paragraph summary of the change from v1

v1 asked "does some schedule exist that satisfies these timing constraints?" and answered it with temporal-network consistency and controllability. Real controllers do not choose schedules. They run one deterministic dispatch: each operation starts as soon as its resources and predecessors allow, joins wait for the last arrival, and an output is stamped at the programmer's cursor whether or not the classical side is ready. A solver that is free to place events can satisfy a lower-bound obligation by delaying an event that the hardware would never delay, and then report PROVED for a program that underflows. v2 therefore separates **dispatch edges**, which define when every event happens, from **obligations**, which are only checked. Verification is a universal check of the obligations over every outcome sequence and every latency realisation of that fixed dispatch. Temporal-network controllability (STN, strong, dynamic, CSTNU) is kept as a separate synthesis module that answers a different question: could any dispatcher, or any choice of compile-time delays, make the program safe?

---

## 1. Validation summary

### 1.1 What v1 and the research report got right (kept)

These parts were checked and stand. v2 reuses them with the changes noted in later sections.

| Kept element | Why it stands |
| --- | --- |
| Pipeline structure: front end, contract, elaboration, event graph, obligations, solver dispatch, verdict, plus an independent executor | Sound separation of concerns; every stage is a pure function of immutable inputs |
| Pure core with no Qiskit imports, enforced by import-linter | Keeps the checker testable and reusable |
| Integer `dt` for program constants | Exact arithmetic for everything the program fixes |
| Verdict lattice PROVED, PROVED-UNDER, REFUTED, UNKNOWN | Honest about assumptions; UNKNOWN names the missing field |
| Every REFUTED is replayed in the executor before it is reported | Catches solver and builder bugs in normal use |
| Policy compatibility table (EQ, SYNC, EXP against backend class) | Directly measures the portability hypothesis H4. Updated for corrected Q1 semantics (Section 7.6) |
| Complexity statement for RUL⁻ (Cairo, Hunsberger, Rizzi, TIME 2018) | Verified: O(MN + K²N + KN log N) |
| ARTIQ silent-drop motivation | Verified in the ARTIQ manual (events discarded, logged, not raised) |
| H1 to H6 hypotheses with pre-registration of thresholds | Good scientific practice; unchanged except the corrected property list (F9) |
| Benchmark families including Dynamarq | Reduces benchmark bias |
| SARIF output, Qiskit `TimingCheck` and `EqualizeBranches` passes, CLI, artifact layout, Apache-2.0 | Fit the intended users and review process |
| Labels keyed by measurement occurrence `bit@node`, fresh per unrolled iteration | Correct; a bit overwritten in a loop is a different observation |
| Provenance as the honesty mechanism (weakest evidence reported in the verdict) | Correct idea; implementation was too thin (F8) |
| The research report's reframing of necessity: portability, FT deadlines, untestable rare branches, silent drops (not raw idle fidelity) | Matches the counter-evidence in the report |

### 1.2 Findings table

Severity: 🔴 breaks soundness or makes a headline claim false; 🟠 materially wrong or unsafe to build on; 🟡 inconsistency or minor error. "v1 loc" refers to the section of the v1 plan (or the research report, marked R). "Source" is a URL listed in Appendix C or the word "reasoning" where the finding is a logical derivation.

| ID | Sev | v1 loc | Problem | Correction in v2 | Source |
| --- | --- | --- | --- | --- | --- |
| F1 | 🔴 | §2, §7, §9, R "Encoding" | Core semantics was STN consistency or STNU/CSTNU dynamic controllability: "does some schedule satisfy the constraints". Controllers run one deterministic dispatch. A solver with free time-points satisfies lower-bound obligations by delaying events hardware never delays (example: O1 commit lead on ARTIQ). Result: false PROVED, which breaks hypothesis H1 (checker versus executor) by design. | Core semantics is verification of a fixed dispatch (D1): the LTEG separates dispatch edges (define times) from obligations (checked). Tiers 0, 1, 2 verify. Controllability moves to the Tier 3 synthesis module. Sections 9 to 12, Appendix A. | reasoning; Appendix A is a worked counterexample |
| F2 | 🔴 | §7.2 | Ordering edges were inequalities `start(next) - end(prev) >= 0`, and joins and branch starts were lower bounds. Real dispatch is `t_v = max over in-edges (t_u + w)`. A maximum is not expressible as a conjunction of difference constraints. | Dispatch edges define `t_v` as a max; Tier 2 encodes the max exactly (lower-bound clauses plus a disjunction of equalities, guarded by labels). Section 9.1, 11.4. | reasoning |
| F3 | 🔴 | §9.2 | "Contingent links replaced by lo and hi requirement edges is sound for strong controllability." This is pseudo-controllability (Morris), which is unsound for strong controllability. | Strong controllability uses the Vidal-Fargier rewrite onto activation points (Section 12.3). Pseudo-controllability is never used as a proof. Rewrite derived and worked: `X - C <= w` becomes `X - A <= w + lo`; `C - X <= w` becomes `A - X <= w - hi`. | CEUR Vol-2509 paper12 (Appendix C); reasoning |
| F4 | 🟠 | §9.3 | Per-scenario STN enumeration was claimed to give "strong controllability over outcomes and latencies". A per-scenario STN lets the schedule depend on the scenario (it "knows the future"); that is weak controllability. | Per-scenario evaluation is kept only as Tier 0 (concrete evaluation of a fixed dispatch per scenario) and as an optimisation inside Tier 2. It is never called a controllability notion. | reasoning; Sumic and Vidal (TIME 2024) on weak controllability |
| F5 | 🔴 | R "Correspondences to prove" | Conjecture "EXP safety iff N(P) is dynamically controllable" and "DMO is a hybrid SC/DC notion" is false unless N(P) encodes the controller's dispatch rigidly. DC asks whether some dispatcher exists. | Restated (Section 15): verification is a universal check over (ω, θ) of the fixed dispatch. DC is existence of a dispatcher. For rigid (tree-shaped) dispatch the two coincide (theorem target T5). For flexible specifications (stretch, box, within) SC or DC is the right question for compile-time or runtime freedom. | reasoning |
| F6 | 🟠 | §8 O4, §5.1 `idle` | O4 default G = 0 flags nearly every circuit (any non-zero idle). | O4 redefined as "unplanned gap": the gap length varies with (ω, θ): `max gap - min gap <= G_r` (Section 10). Absolute idle length becomes optional advisory O4a, off by default. | reasoning (varying idle breaks compile-time DD and phase tracking) |
| F7 | 🟠 | §5.4 | Loader rounds every `lo` down and every `hi` up. Correct for uncertain intervals, wrong for requirements: a deadline rounded up, or a commit lead rounded down, is unsound. | Rounding by role (Section 5.1): uncertainty intervals outward; upper-bound requirements (deadline D, gap G, spread Δ) round down; lower-bound requirements (commit lead, minimum separation) round up; fixed durations must be exact multiples of dt or the loader errors. | reasoning |
| F8 | 🟠 | §3 `Prov(IntEnum)`, `Interval.__add__` | Provenance as a bare IntEnum with `min` loses which latencies and sources a proof used; `Interval.__add__` drops `source`. mσ and percentile values had no defined path to an upper bound. | Structured provenance record (class, source, metadata); combination keeps the full assumption set; verdict reports weakest class plus every assumption. mσ and pctl never auto-produce a bound: the contract must state `hi` with `k` or `p` recorded. Hard obligations discharged only by `cert` or `cyc`. Section 5.2. | reasoning |
| F9 | 🟠 | §12.1 property 3 | "Tightening a latency interval never turns PROVED into REFUTED" is false when elaboration depends on contract values: EQ waits to `hi`; a smaller `hi` arms earlier, leaving less issue slack, which can cause an O1 underflow. | Monotonicity holds only for a fixed elaborated program. Elaboration-dependent monotonicity is not a property (Section 16.2). | reasoning |
| F10 | 🟠 | §2 dependency table | Python pinned to 3.11 to 3.13; Qiskit 2.6.2 (released 2026-11-05) is the latest and requires Python 3.10 or newer. | Core supports Python 3.10 to 3.14; `qiskit` extra pinned `>=2.3,<2.7`, tested on 2.6.2; the q1simulator cross-check needs Python 3.12 or newer. Section 4.4. | pypi.org/project/qiskit; q1simulator on PyPI |
| F11 | 🟠 | §4.1, §15.4 | Timing annotations ride on `box`. IBM rejects `box` on direct job submission (boxes are used only by Samplomatic and the Executor). A circuit annotated for the checker cannot be submitted as is. | `StripTimingAnnotations` pass removes `timing.*` annotations (and unwraps boxes that exist only for annotations) before submission. Section 6.7. | IBM docs (Appendix C) **[verify]** on current box acceptance |
| F12 | 🟠 | §5.1 `dd_inserted_by_backend = true`; R "IBM moved DD" | The documentation reviewed does not state that DD is inserted by the backend for dynamic circuits. | Contract field `dd_inserted_by_backend` defaults to `unknown` with a vendor-class source note; no obligation relies on it. | IBM docs (Appendix C) |
| F13 | 🟠 | §3 labels, §4.2 | Front end missed Qiskit 2.x `expr` conditions (`bit_xor` parity, comparisons, boolean operators), `Var` and `Store` real-time variables, `else`, `SwitchCaseOp`, `BoxOp` with Duration or Stretch expression durations, and `measure_2`. Duplicating branch bodies per disjunct was a poor encoding. | Each condition evaluation becomes ONE derived proposition, observed at the maximum of its operand bits' valid times (sound over-approximation of correlations); no disjunct duplication. Section 6.2 and 6.3. | Qiskit release notes 2.1 and 2.3 (Appendix C) |
| F14 | 🟠 | §4.1 | Annotations referenced `Clbit` objects, which are not serialisable through QASM3 or QPY. | Annotations name bits by string (register name and index). Resolution to `Clbit` happens in the front end. Section 6.4. | Qiskit annotation API (Appendix C) |
| F15 | 🔴 | §5.3, R control table | Q1 feedback latencies "160 / 250 / 472 ns (self / intra / multicast)" were not found in the current Qblox documentation. | Q1 contract rebuilt from documented numbers (D9): trigger network 212 ns to all receivers (212 to 239 ns depending on the 28 ns timegrid), network free again after 252 ns, OP plus IP base 149 ns (output 40 baseband or 50 RF, input 109), RTP plus 24 ns output, TTL input 35 ns faster, worked example total 388 ns. Section 7.3. | docs.qblox.com trigger_handling (Appendix C) **[verify exact page path]** |
| F16 | 🟠 | §8.2, §6.3 | Q1 instruction costs partly wrong or stale; `set_cond` semantics under-modelled. | Costs: `jmp` 16 ns; conditional jumps (`jge`, `jlt`, `loop`) 24 ns taken, 4 ns not taken; `nop` 4 ns; old `jge`/`jlt`/`loop` forms deprecated in favour of compare or subtract plus flag jump (one extra instruction). `set_cond`: the condition is evaluated before EVERY RT instruction; if false, the RT core waits `else_time` ns per skipped RT instruction, so arms are equal only when instruction counts and durations align. The checker models this per instruction (Section 8.5). RT queue holds 32 instructions; underflow raises `SEQUENCE_PROCESSOR_RT_EXEC_COMMAND_UNDERFLOW` and halts the sequencer. | docs.qblox.com Q1 index, sequencer docs (Appendix C) |
| F17 | 🔴 | §8.1 | O5 for ARTIQ stated "more than 8 events in the same coarse slot" is a violation. That is not the hardware rule. | O5 implements the real rules (D10): coarse timestamps must strictly increase within a lane; if the new event's timestamp is not greater than the previous one on the current lane (or the lane is nearly full), the SED moves to the next lane; if all lanes hold an event with time at or after the new one, the event is dropped with a sequence error; behaviour is deterministic from reset unless `sed_spread_enable` is set. Collision: same channel, same coarse timestamp, different fine timestamp (or same timestamp without replace behaviour). Busy: channel still executing a multi-cycle event. Default 8 lanes (gateware `sed_lanes`); coarse clock typically 125 MHz (8 mu). Sequence, collision and busy errors discard the event and log to the core log (`artiq_coremgmt log`); underflow and overflow raise. Section 10.5, 14.4. | m-labs.hk/artiq/manual/rtio.html |
| F18 | 🟠 | §5.3 `qua.toml` | QUA implicit aligns under-specified. | Implicit align at the start of `for_`, `while_`, `if_`, `else_`, `switch_` for participating elements (removable with the compiler flag `skip-add-implicit-align`). Also non-suppressible implicit aligns for broadcast operations and for `measure()` results read by another core. Non-deterministic align gap is "a few cycles", topology dependent (same FEM less than cross-FEM less than cross-chassis) and unpublished, so it is a contract interval with `vendor` provenance and a placeholder. `strict_timing_` turns gaps into compile errors (flag `not-strict-timing` gives warnings). Section 7.3. | docs.quantum-machines.co timing_in_qua (Appendix C) |
| F19 | 🟠 | §2 dependency table, §9.5 | CSTNU Tool listed as 7.2. Latest release is v7.1 (2026-09-08); 7.2 is unreleased. `java -jar` opens the GUI editor, not a batch checker. Since v6.6 the STNU checker rejects contingent links in sequence (a contingent node as the activation point of another link) and links that share an activation node. | Pin v7.1 by SHA-256; invoke the `Checker` main class via `java -cp`; the exporter inserts support nodes joined by zero-length requirement edges. Subprocess only, never vendored (LGPL-3.0 plus CC0 parts). Section 12.6. | profs.scienze.univr.it/~posenato/software/cstnu (Appendix C) |
| F20 | 🟠 | §5.1 `grid acquire = 16`, §5.3 | IBM contract hard-coded a 16 dt grid and a single `measure` duration. The unofficial Heron r2 snapshot reports dt = 4 ns and alignments of 1; `measure` and `measure_2` (MidCircuitMeasure) are separate Target entries; durations differ per backend (measure: fez 1660 ns, kingston 2180 ns, marrakesh 2684 ns; measure_2: 1340, 1380, 1884 ns; unofficial). | dt, alignments (acquire, pulse, granularity, `min_length`) and gate and measure durations are read from `backend.target`; the hand-written TOML holds only what the Target lacks (latencies, branch class, late policy, capacity, broadcast budget). Section 7.4. | gororoba-quantum snapshot (**unofficial**, Appendix C); qiskit Target docs |
| F21 | 🟠 | §4.3, §6 | IBM restrictions listed incompletely; the join behaviour "pad unequal arms to the longest block" is documented only for the old fast-path stack (qiskit-ibm-runtime 0.39 and earlier). | IBM lint rules (current docs): only if/else (no else-if, for, while, switch), no nesting, no measure or reset inside conditionals, no arithmetic or shift in conditions, operand at most 32 bits, broadcast budget (about 300 broadcasts of 60 bits or 2400 of 1 bit per job), 26.8 M instructions per qubit, other job limits. The IBM personality's join behaviour is a parameter calibrated from evidence (Section 18), tagged `vendor` until then. | IBM docs: execute-dynamic-circuits, dynamic-circuits-considerations, job limits, qasm feature table |
| F22 | 🟠 | §14 | Phase-drift probe swept delays 0 to 1000 ns. At a calibrated detuning of about kHz the accumulated phase at 100 ns is a few mrad, below shot noise at 2000 shots. | Primary evidence becomes `scheduler_timing` job metadata from `dry_run=True` (no QPU time). The phase probe becomes optional and redesigned: delay sweep into tens of µs, plus a same-job standard Ramsey to measure δf, DD on and off. Section 18. | reasoning (SNR); IBM runtime docs on `dry_run` **[verify]** |
| F23 | 🟠 | §10.3 | RUS expected-time formula omitted the exhaust term. The deadline-miss probability used `m = floor(D/T)` and gave 3.1% for the research report's example (p = 0.5, D = 10 µs, T = 2 µs), where the report states (1-p)^4, about 6%. | `E[T_cap] = T(1-q^N)/p + q^N T_exh`, `q = 1-p`; p_min gives an upper bound because expected iterations decrease in p. Miss probability uses `m = floor((D - T_post)/T)` where `T_post` is the worst-case work after the loop that must still fit before the deadline; with `T_post = 2 µs` this reproduces (1-p)^4 = 6.25%; with `T_post = 0` it gives 3.125%. Exact rational arithmetic. Section 13.5. | reasoning |
| F24 | 🟡 | §10.1 | Example JSON (margin 740, max_safe ff 1340) disagrees with the Appendix worked example (margin 2400 ns, max-safe ff 3000 ns). | Verdict JSON example in Section 13.2 uses the Appendix A numbers. | reasoning |
| F25 | 🟠 | R "Prior art", v1 positioning | Closest work was understated. New: qlin (arXiv:2611.19618, 2026-11-14), qconform (arXiv:2610.10427), q1asm-simulator, DART-Q (arXiv:2605.09142); GRAMPUS now has a "...with Measurement" TYPES 2026 talk (work in progress). | Novelty statement reworded (Section 22.2); pre-submission arXiv sweep task added (Section 20, P14). | arXiv links in Appendix C |
| F26 | 🟠 | §7.4 | Windowed composition soundness left as "one of the paper's technical results" with no rule for where cuts are legal. | Cuts only at full joins; no obligation may cross a cut; personality state at the cut must be canonical; the builder enforces all three (Section 9.7); theorem target T4. | reasoning |
| F27 | 🟠 | §9.6 | Tier D used integer difference logic (QF_IDL, QF_LIA). Contingent latencies are physically continuous; integer θ misses counterexamples between integers and over-constrains. | Tier 2 uses QF_LRA with real θ; counterexample θ is rational; the executor uses `fractions.Fraction`. Grid checks use `IsInt(t/g)` (mixed real-integer). Optional contract flag `latency_resolution = "dt"` restricts θ to integers. Section 11.4. | reasoning |
| F28 | 🟠 | §9.1 | Dispatch rule based on label counting and controllability class (A, B, C1, C2, D) no longer describes verification. | New tier rule: Tier 0 (no contingent links on the path), Tier 1 (interval abstraction, never REFUTED), Tier 2 (exact SMT). Tier 3 is a separate module (Section 11.1). | reasoning |
| F29 | 🟠 | R "Encoding" | Condition `c == 5` or `c > 2` over a register expanded into labels and disjuncts; correlations between conditions were lost or duplicated. | Derived proposition per condition evaluation with an explicit expression over operand-bit propositions; Tier 2 encodes it exactly; Tiers 0 and 1 may treat it as free (over-approximation). Section 5.4. | reasoning |
| F30 | 🟡 | §14 budget | IBM Open Plan numbers were approximate. | Open Plan: 10 minutes per rolling 28 days; a one-time 180-minute opt-in for 12 months (needs a non-trial account with 20 minutes already used); ibm_kingston is available on the Open Plan. Section 18.5. | IBM plans documentation (Appendix C) **[verify]** |
| F31 | 🟡 | §5.1 | `commit_lead` default `0, vendor` makes O1 vacuous on contracts that publish nothing. | Missing required numbers yield UNKNOWN naming the missing field instead of silently weakening the obligation (Section 7.1). | reasoning |
| F32 | 🟡 | §11.3 | The q1simulator cross-check was proposed without noting its Python requirement. | Cross-check runs in a separate venv with Python 3.12 or newer (Section 14.7). | q1simulator on PyPI |

---

## 2. Vision, scope and non-goals

### 2.1 What `qtiming` is

`qtiming` is a Python package and command-line tool. It reads a dynamic quantum program (a circuit with mid-circuit measurement, classical feedforward, bounded loops and timing intent) and a hardware timing contract, and decides before the program runs whether the controller's deterministic dispatch of that program can ever arrive late, underflow a queue, drop an event, miss a declared deadline, or leave a gap whose length depends on the data. It answers with one of four verdicts: PROVED, PROVED-UNDER (with a list of assumptions), REFUTED (with a replayable counterexample), or UNKNOWN (naming the missing number or the tier that gave up).

Plain-language version, for the advisor and for readers of the rulebook note: it is a spell-checker for time. The program says what it wants. The contract says what the machine promises. The checker asks whether, for every possible measurement result and every allowed latency, the machine's own way of running the program stays within the promises.

### 2.2 Why it is worth building (from the research report, reframed)

The strong arguments are four: portability of timing intent across vendors, fault-tolerance reaction deadlines and lattice-surgery synchronisation, rarely-taken branches that cannot be tested empirically, and silent failures (ARTIQ discards events without an exception). Raw idle fidelity is the weakest argument and is not used to motivate the tool.

### 2.3 Scope of the complete version

| In scope | Out of scope (stated non-goals) |
| --- | --- |
| Qiskit `QuantumCircuit` (2.x, including `expr` conditions, `Var`, `Store`, `else`, `SwitchCaseOp`, `BoxOp`) and OpenQASM 3 text with mid-circuit measurement and `if`/`else` | Unbounded `while` loops |
| Bounded `for`, capped `while` (repeat-until-success) with an exhaust handler | Pulse-level `defcal` bodies |
| Three branch-timing policies: EQ, SYNC(Δ, G), EXP | Noise and fidelity modelling |
| Blocking classical calls with declared latency (`device_call`) | Multi-controller synchronisation protocols (abstracted as sync domains with a contract cost) |
| Four contracts: IBM Heron, ARTIQ, Qblox Q1, QM QUA, with provenance-typed numbers | Decoder internals (a decoder is a latency bound) |
| Four executor personalities replaying counterexamples | Qubit mapping and routing |
| Obligations O1 to O9 plus advisory O4a and a lint layer | Mechanised proofs on the critical path (optional stretch) |
| Verification tiers 0, 1, 2 (concrete, interval, exact SMT) | Hardware control or pulse generation |
| Synthesis and controllability module (STN, strong controllability, STNU DC, CSTNU bridge, `qtiming repair`) | Silently weakening a verdict to fit a deadline |
| Windowed (compositional) checking for long, repetitive programs | Proving anything about the quantum state |
| Qiskit transpiler passes (`TimingCheck`, `EqualizeBranches`, `StripTimingAnnotations`), CLI, SARIF, HTML timeline | |
| Benchmarks, differential testing, mutation testing, pre-registered evaluation | |
| IBM evidence pipeline (`scheduler_timing` from `dry_run=True`), optional redesigned phase probe | |
| Artifact (Docker plus VM), documentation site, packaging | |

### 2.4 Engineering principles

These decide every later trade-off. Items 8 and 9 are new in v2; items 3 and 6 are sharpened.

1. **Soundness over completeness.** The checker may say UNKNOWN. It must never say PROVED for a program that can fail under the executor. Every solver tier is cross-checked against a slower, simpler one.
2. **Exact arithmetic.** Program constants are integer `dt`. Latencies are real-valued variables inside the solver (QF_LRA), and every number leaving the solver is an exact rational (`fractions.Fraction`). No floating point enters a verdict.
3. **Provenance travels with every number and every verdict.** A verdict lists every assumption it used and reports the weakest evidence class among them. Hard obligations are discharged only by `cert` or `cyc` evidence.
4. **Cheap tier first, but never at the cost of soundness.** Tier 0 and Tier 1 may prove; only Tier 2 may refute (after executor replay).
5. **Every REFUTED is replayable.** A counterexample is a concrete outcome assignment plus rational latencies that the reference executor reproduces deterministically.
6. **Pure core, thin adapters.** The core IR and solvers never import Qiskit. Front ends and personalities are adapters.
7. **One artifact, every committee.** Pinned dependencies, Docker image, VM script, smoke test under 30 minutes from the first commit.
8. **Obligations are checked, never used to schedule.** Obligations never appear as constraints that move an event. Only dispatch edges place events.
9. **Dispatch semantics is defined once per personality and implemented twice.** Each personality has a written dispatch specification (`docs/personality-spec/<name>.md`). The graph builder and the reference executor implement that specification independently, with no shared helper code beyond the AST and contract types (enforced by import-linter). Agreement between them is real evidence, not a tautology.

---

## 3. Architecture

### 3.1 Pipeline

```text
   Qiskit QuantumCircuit / QPY / OpenQASM 3 text            contract.toml  (+ backend.target for IBM)
                    |                                                |
                    v                                                v
        [1] FRONT END  ----> TQ core AST                [2] CONTRACT LOADER --> Contract (frozen, SHA-256)
        (qiskit_fe, qasm3_fe, annotations)                       |
                    |                                            |
                    +---------------------+----------------------+
                                          v
                        [3] ELABORATION  (policy: EQ / SYNC / EXP made explicit;
                                          loops unrolled or capped; calls bound;
                                          conditions -> derived propositions)
                                          |
                                          v
                        [4] GRAPH BUILDER  + personality dispatch rules  (qtiming.dispatch)
                                          |
                                          v
                        LTEG = nodes + DISPATCH EDGES (define times) + CONTINGENT LATENCIES
                                          |
                                          v
                        [5] OBLIGATION GENERATOR  (O1..O9, O4a, lint L-rules)   <-- contract
                                          |
                                          v
                        [6] VERIFICATION DISPATCHER
                              Tier 0 concrete  ->  Tier 1 interval  ->  Tier 2 exact SMT (Z3)
                                          |
                                          v
                        [7] VERDICT + COUNTEREXAMPLE (rational theta, minimised)
                                          |
                           +--------------+---------------+
                           v                              v
                 [E] REFERENCE EXECUTOR           reports: terminal / JSON / SARIF / HTML
                 (independent re-implementation   (replays every REFUTED before reporting)
                  of the personality spec)

   Separate module, NOT on the verification path:
        [S] SYNTHESIS / CONTROLLABILITY (Tier 3): STN, strong controllability (Vidal-Fargier),
            STNU dynamic controllability (Morris 2014, optional RUL-), CSTNU Tool bridge,
            `qtiming repair`, policy-feasibility claims, cross-validation on rigid encodings.
```

### 3.2 Stage table

| # | Stage | Input | Output | Package |
| --- | --- | --- | --- | --- |
| 1 | Front end | `QuantumCircuit`, QPY file, or OpenQASM 3 text | TQ core AST (frozen dataclasses) | `qtiming.frontend` |
| 2 | Contract loader | TOML or JSON contract file, optional `Target` | validated `Contract` (integer `dt`, provenance records, SHA-256) | `qtiming.contract` |
| 3 | Elaboration | TQ AST plus Contract | elaborated AST: explicit waits, joins, cursor ops, unrolled or capped loops, derived propositions | `qtiming.elab` |
| 4 | Graph builder | elaborated AST plus personality | LTEG (dispatch edges, contingent latencies, labels) | `qtiming.graph`, `qtiming.dispatch` |
| 5 | Obligation generator | LTEG plus Contract | list of `Obligation` records (O1 to O9, O4a) with dependencies and provenance | `qtiming.oblig` |
| 6 | Verification dispatcher | obligations plus LTEG | per-obligation result (proved, refuted with witness, unknown) | `qtiming.solve.{concrete,interval,smt}` |
| 7 | Verdict and witness | results | `Verdict`, `Counterexample`, reports | `qtiming.verdict` |
| E | Reference executor | elaborated AST plus Contract plus (ω, θ) | trace or violation list | `qtiming.exec` |
| S | Synthesis (Tier 3) | LTEG (relaxed) | consistency, SC, DC results; repair suggestions | `qtiming.solve.synth`, `qtiming.repair` |
| I | Evidence ingestion | IBM `scheduler_timing` JSON | contract parameter patches with provenance | `qtiming.evidence` |

Each stage is a pure function from immutable input to immutable output, so each is unit-testable, cacheable and snapshot-testable. The only stage with I/O beyond reading files is the CSTNU Tool bridge (subprocess) and evidence ingestion (reads job metadata files; network access lives in `experiments/`, not in the package).

### 3.3 Data flow of one check (`qtiming check prog.qasm --contract q1.toml`)

1. The front end parses the program, resolves stretch and `durationof` expressions, and emits a TQ AST with stable node IDs (`nid`) and source locations.
2. The loader reads `q1.toml`, converts all numbers to `dt` by role (Section 5.1), freezes the `Contract` and computes its SHA-256.
3. Elaboration applies the effective policy for each `if` and loop (annotation, else contract default), checks policy compatibility (Section 7.6), unrolls bounded loops, rewrites conditions into derived propositions, and inserts the waits the policy requires. Elaboration may use contract `hi` values (EQ waits until `hi`); the elaborated program is therefore a function of the contract.
4. The graph builder walks the elaborated program with the personality's dispatch rules and emits nodes and dispatch edges. It runs the structural invariants of Section 9.5.
5. The obligation generator emits obligations referencing LTEG nodes, each with its guard label, the set of latency variables it depends on, and a hard or advisory flag.
6. The verification dispatcher chooses a tier per obligation (Section 11.1). Tier 0 and Tier 1 try to prove; unresolved obligations go to Tier 2.
7. The verdict builder combines results, collects the assumption set, computes margins, and for each Tier 2 SAT result extracts a rational (ω, θ), minimises it, and replays it in the executor. A replay mismatch is an internal error, never a reported counterexample.
8. Reports are rendered.

### 3.4 Where personalities plug in

A personality is a pair of independent implementations of one written specification.

| Part | Location | Role |
| --- | --- | --- |
| Specification | `docs/personality-spec/<name>.md` | Normative text: how branches, joins, commits, cursors, queues and late events behave, with every unpublished behaviour listed as a named parameter |
| Dispatch rules (graph side) | `src/qtiming/dispatch/<name>.py` | Emits dispatch edges and personality obligations into the LTEG |
| Executor hooks (simulation side) | `src/qtiming/exec/personalities/<name>.py` | Event-by-event interpreter hooks |
| Contract instance | `src/qtiming/contract/instances/<name>.toml` | Numbers and provenance |
| Conformance tests | `tests/personality/<name>/` | Golden traces from the specification's worked examples, run against both implementations |

### 3.5 Tier dispatch rule (new in v2)

For every obligation `o` with guard label `L_o` and dependency set `D_o` (contingent latency variables it depends on):

1. **Tier 0 (concrete).** If `D_o` is empty, evaluate `t_x - t_y` exactly for each scenario of the propositions that the obligation depends on (topological longest path; `k_o` propositions, at most `2^k` scenarios, capped by `tier0_scenario_cap`, default 4096; above the cap, treat remaining propositions symbolically in Tier 2). Result is exact: proved or refuted.
2. **Tier 1 (interval abstraction).** If `D_o` is non-empty, compute sound bounds on `t_x - t_y` from affine-max forms (Section 11.3). If the bounds imply the obligation, the obligation is proved. Otherwise escalate. Tier 1 never reports REFUTED.
3. **Tier 2 (exact SMT).** Assert the negation of the obligation over the exact dispatch encoding. UNSAT means proved. SAT yields a concrete (ω, θ), which is replayed. Timeout means UNKNOWN, with the window and `k` reported.
4. Obligations that are two-execution properties (O4 variation) go directly to Tier 1 bounds (spread of upper minus lower) and then Tier 2 with a product encoding.
5. Tier 3 is never consulted to prove an obligation. It is consulted by `qtiming repair`, by `qtiming synth`, and by cross-validation tests.

---

## 4. Repository layout

### 4.1 Full tree

```text
qtiming/
├── pyproject.toml                      # hatchling; extras: [qiskit] [z3] [synth] [bench] [dev] [docs]
├── uv.lock / requirements.lock         # pinned resolution for the artifact
├── README.md  LICENSE (Apache-2.0)  NOTICE  CITATION.cff  CONTRIBUTING.md  CODE_OF_CONDUCT.md
├── .importlinter                       # layering contracts (Section 4.5)
├── .github/workflows/                  # lint.yml test.yml oracle.yml diff.yml bench-smoke.yml release.yml docs.yml
├── src/qtiming/
│   ├── __init__.py  __main__.py  py.typed
│   ├── core/                           # stdlib only: NO qiskit, NO z3, NO pydantic
│   │   ├── time.py                     # Dur, Interval, rounding roles, ns<->dt with Fraction
│   │   ├── provenance.py               # ProvClass, Prov record, Assumption, combine/weakest
│   │   ├── labels.py                   # Lit, Label, derived propositions, Expr tree, evaluation
│   │   ├── ast.py                      # TQ node table (frozen dataclasses), Policy, SourceLoc
│   │   ├── errors.py                   # QtError, error codes, Severity, SARIF rule ids
│   │   └── ids.py                      # stable nid / occurrence-key generation
│   ├── frontend/
│   │   ├── qiskit_fe.py                # QuantumCircuit/DAG walk -> TQ AST
│   │   ├── qiskit_expr.py              # qiskit.circuit.classical.expr -> core Expr
│   │   ├── qasm3_fe.py                 # openqasm3 AST -> TQ AST (fallback)
│   │   ├── annotations.py              # timing.* Annotation subclasses (namespace "timing")
│   │   ├── serialise.py                # qasm3 annotation_handlers, qpy annotation_factories
│   │   ├── stretch.py                  # stretch/durationof resolution (linear system)
│   │   └── lint.py                     # per-backend front-end lint rules (IBM etc.)
│   ├── contract/
│   │   ├── schema.py                   # pydantic v2 models for every clause
│   │   ├── loader.py                   # TOML/JSON -> Contract; rounding by role; Target merge; SHA-256
│   │   ├── target_import.py            # backend.target -> dt, alignments, durations (needs qiskit)
│   │   ├── compat.py                   # policy-compatibility table
│   │   └── instances/                  # ibm_heron.toml artiq.toml q1.toml qua.toml + README.md per instance
│   ├── elab/
│   │   ├── driver.py                   # elab(stmt, env) -> (stmt', interval, env')
│   │   ├── eq.py  sync.py  exp.py      # per-policy rules
│   │   ├── loops.py                    # unroll / cap / summarise
│   │   ├── q1_setcond.py               # per-instruction else_time modelling
│   │   ├── calls.py  within.py
│   │   └── env.py                      # valid-time environment Gamma
│   ├── graph/
│   │   ├── lteg.py                     # Node, DEdge, LatVar, LTEG (arrays + index maps)
│   │   ├── builder.py                  # elaborated AST + personality -> LTEG
│   │   ├── invariants.py               # structural invariants I1..I7 (Section 9.5)
│   │   ├── window.py                   # cut finder, window summaries
│   │   └── export.py                   # JSON / DOT dump for debugging
│   ├── dispatch/                       # personality semantics, graph side (specification-driven)
│   │   ├── base.py                     # Personality protocol, GraphBuilder facade
│   │   └── ibm.py  artiq.py  q1.py  qua.py
│   ├── oblig/
│   │   ├── model.py                    # Obligation, Check variants (Diff, Variation, Modular, Capacity, Lane, Count)
│   │   ├── o1_underflow.py  o2_ready.py  o3_deadline.py  o4_gap.py  o5_capacity.py
│   │   ├── o6_call.py  o7_sync.py  o8_grid.py  o9_loops.py
│   │   ├── lint.py                     # L-rules (static, no solver)
│   │   └── generate.py
│   ├── solve/
│   │   ├── dispatcher.py               # tier selection (Section 3.5)
│   │   ├── concrete.py                 # Tier 0: topological longest path per scenario
│   │   ├── interval.py                 # Tier 1: affine-max forms, must/may label analysis
│   │   ├── smt.py                      # Tier 2: Z3 QF_LRA encoding, product encoding for O4
│   │   ├── smt_o5.py                   # Tier 2 lane/collision encodings
│   │   ├── cache.py  pool.py           # content-hash cache; process pool
│   │   └── synth/                      # Tier 3, NOT on the verification path
│   │       ├── stn.py                  # STN consistency, Bellman-Ford, negative-cycle witness, Floyd-Warshall
│   │       ├── sc.py                   # strong controllability (Vidal-Fargier rewrite)
│   │       ├── stnu_dc.py              # Morris 2014 O(N^3); optional rul.py (RUL-)
│   │       ├── bruteforce_dc.py        # tiny-network game solver (oracle of last resort)
│   │       ├── cstnu_tool.py           # GraphML export + subprocess bridge
│   │       ├── relax.py                # LTEG -> relaxed STNU (>= edges only) N_geq(P)
│   │       └── rigid.py                # rigid-encoding detector (tree dispatch) for T5 tests
│   ├── verdict/
│   │   ├── model.py                    # Verdict, assumption list, Margin, Counterexample
│   │   ├── minimise.py                 # witness shrinking
│   │   ├── rus.py                      # RUS three-part verdict, exact Fractions
│   │   └── render_text.py  render_json.py  render_sarif.py  render_html.py
│   ├── exec/
│   │   ├── engine.py                   # discrete-event engine, Fraction time
│   │   ├── oracle.py                   # Fixed, Random, Extreme, Exhaustive
│   │   ├── state.py                    # per-resource clocks, store, valid times
│   │   ├── trace.py                    # Trace, Violation, SilentDrop
│   │   ├── personalities/              # ibm.py artiq.py q1.py qua.py  (independent of qtiming.dispatch)
│   │   └── q1sim_bridge.py             # q1simulator cross-check (separate venv, Python >= 3.12)
│   ├── evidence/
│   │   ├── scheduler_timing.py         # parse IBM scheduler_timing metadata
│   │   ├── calibrate.py                # metadata -> contract parameter patch with provenance
│   │   └── schema.py
│   ├── repair/
│   │   ├── suggest.py                  # counterexample-guided delay/stretch suggestions
│   │   └── patch.py                    # diff output, re-verification
│   ├── qiskit_pass/
│   │   ├── timing_check.py             # TimingCheck (analysis)
│   │   ├── equalize.py                 # EqualizeBranches (transformation)
│   │   ├── strip.py                    # StripTimingAnnotations
│   │   └── plugin.py                   # preset pass manager stage plug-in
│   └── cli/
│       ├── main.py                     # entry points: qtiming, qtiming-bench
│       └── cmd_check.py  cmd_explain.py  cmd_synth.py  cmd_repair.py
│           cmd_contract.py  cmd_replay.py  cmd_evidence.py  cmd_bench.py
├── benchmarks/
│   ├── families/<family>/<program>/{prog.qasm|prog.py, meta.yaml, ground_truth.json?}
│   ├── contracts/                      # variants used by sensitivity studies
│   ├── external/                       # Dynamarq programs, ARTIQ manual kernels (with licences)
│   ├── harness/                        # runner, report generators (matplotlib scripts)
│   └── results/                        # Parquet, not committed (artifact ships cached copies)
├── tests/
│   └── unit/  golden/  property/  differential/  oracle/  personality/  mutation/  fixtures/
├── experiments/
│   ├── ibm_dryrun/                     # dry_run scheduler_timing collection scripts (primary evidence)
│   └── ibm_probe/                      # optional redesigned phase probe + cached results
├── prereg/                             # pre-registration (thresholds), dated tags
├── docs/                               # mkdocs-material site, personality-spec/, contract spec, tutorials, theory/
├── paper/                              # LaTeX sources, figure scripts reading only Parquet
└── artifact/                           # Dockerfile, vm/build.sh, smoke.sh, core.sh, full.sh, README.md
```

### 4.2 One-line purpose of the files that matter most

| File | Purpose |
| --- | --- |
| `core/time.py` | Integer `dt`, `Interval`, rounding by role, exact ns to dt conversion with `Fraction` |
| `core/provenance.py` | Structured provenance records, assumption sets, weakest-class computation |
| `core/labels.py` | Propositions, labels (conjunctions), derived propositions with expression trees, exact evaluation |
| `core/ast.py` | TQ syntax tree |
| `graph/lteg.py` | The single intermediate representation: dispatch edges, contingent latencies, labels |
| `dispatch/*.py` | Personality dispatch rules, written from `docs/personality-spec` |
| `oblig/generate.py` | Turns the LTEG and contract into obligations; never adds scheduling constraints |
| `solve/concrete.py` | Exact evaluation of the fixed dispatch for a given (ω, θ) or per scenario |
| `solve/interval.py` | Sound abstraction; proves cheaply; never refutes |
| `solve/smt.py` | Exact encoding with `max`, labels, real θ; produces counterexamples |
| `solve/synth/*` | Controllability and synthesis algorithms; independent of the verification path |
| `exec/engine.py` | Executor core; shares only `core.ast` and `contract` types with the checker |
| `verdict/rus.py` | Exact repeat-until-success formulas |
| `evidence/*` | Turns IBM `scheduler_timing` into contract patches |
| `qiskit_pass/*` | Qiskit integration |

### 4.3 Package boundaries

- `core` is importable with only the standard library. Contract models (pydantic) live in `contract`, not in `core`, so `core` stays dependency-free.
- `graph`, `dispatch`, `oblig`, `solve`, `verdict` import `core` and `contract` only. `solve.smt` imports `z3`. `solve.synth.cstnu_tool` imports only `subprocess`.
- `exec` imports `core` and `contract`. It never imports `graph`, `dispatch`, `oblig`, `solve`, `elab` or `verdict`. This is what makes principle 9 checkable. The `q1sim_bridge` runs the external simulator in a subprocess only.
- `frontend`, `qiskit_pass`, `contract.target_import` are the only modules that import `qiskit`.
- `cli` imports everything and is imported by nothing.

### 4.4 Dependency policy

| Dependency | Role | Pin | Notes |
| --- | --- | --- | --- |
| Python | runtime | core: 3.10 to 3.14; CI matrix 3.10, 3.12, 3.14 (3.11 and 3.13 weekly) | Qiskit 2.6.2 requires 3.10 or newer |
| `qiskit` | front end, passes (extra `[qiskit]`) | `>=2.3,<2.7`; tested on 2.6.2 (released 2026-11-05) | Rust-native control flow from 2.3; `BoxOp` annotations since 2.1; weekly job on Qiskit main |
| `openqasm3` | OpenQASM 3 fallback parser | `>=1.0,<2` | Covers programs Qiskit cannot import |
| `z3-solver` | Tier 2 (extra `[z3]`) | `>=4.13` (artifact pins an exact version) | QF_LRA plus `IsInt` |
| `pydantic` | contract schema | v2 | Only hard runtime dependency besides stdlib |
| `networkx` | debugging visualisation only | 3.x | Not on any hot path |
| `hypothesis` | property tests (dev) | latest | |
| `pytest`, `pytest-xdist`, `pytest-cov` | tests (dev) | latest | |
| `mutmut` | mutation testing (dev) | latest | Monthly; targets `solve/` and `oblig/` |
| `ruff`, `mypy`, `import-linter` | lint (dev) | latest | `mypy --strict` on `core/`, `solve/`, `graph/`, `oblig/` |
| `pyarrow`, `pandas`, `matplotlib` | benchmark reports (extra `[bench]`) | latest | Parquet outputs |
| `mkdocs-material` | docs (extra `[docs]`) | latest | |
| `q1simulator` | Q1 cross-check (separate venv) | latest | Needs Python 3.12 or newer; licence **[verify]** (v1 noted MIT) |
| CSTNU Tool (Java) | Tier 3 oracle and DC back end | **v7.1 (2026-09-08)**, jar pinned by SHA-256 | LGPL-3.0 (plus CC0 parts); subprocess only; never vendored or linked; 7.2 is unreleased |
| HEATlab Prob-in-Ctrl | Tier 3 oracle (STNU DC benchmarks) | commit hash pinned | MIT; git submodule under `tests/oracle/third_party/` |
| JDK | CSTNU Tool runtime | 21 | In Docker image |
| `qiskit-ibm-runtime` | evidence collection (experiments only, not a package dependency) | current | `dry_run=True`, `scheduler_timing` |

The core package has `pydantic` as its only hard dependency (used by `contract`). Qiskit, Z3 and the synthesis extras are optional, so the core installs in seconds and runs anywhere.

### 4.5 Import-linter contracts

```ini
# .importlinter
[importlinter]
root_package = qtiming
include_external_packages = True

[importlinter:contract:core-is-pure]
name = core imports only stdlib
type = forbidden
source_modules = qtiming.core
forbidden_modules = qiskit, z3, pydantic, openqasm3, networkx, numpy, pandas

[importlinter:contract:qiskit-confined]
name = qiskit only in adapters
type = forbidden
source_modules =
    qtiming.core
    qtiming.contract.schema
    qtiming.contract.loader
    qtiming.elab
    qtiming.graph
    qtiming.dispatch
    qtiming.oblig
    qtiming.solve
    qtiming.verdict
    qtiming.exec
    qtiming.evidence
    qtiming.repair
forbidden_modules = qiskit

[importlinter:contract:executor-independence]
name = executor never sees the graph side
type = forbidden
source_modules = qtiming.exec
forbidden_modules =
    qtiming.graph
    qtiming.dispatch
    qtiming.oblig
    qtiming.solve
    qtiming.elab
    qtiming.verdict

[importlinter:contract:synthesis-isolated]
name = verification path never imports synthesis
type = forbidden
source_modules =
    qtiming.solve.concrete
    qtiming.solve.interval
    qtiming.solve.smt
    qtiming.solve.smt_o5
    qtiming.solve.dispatcher
forbidden_modules = qtiming.solve.synth

[importlinter:contract:layers]
name = pipeline layering
type = layers
layers =
    qtiming.cli
    qtiming.qiskit_pass | qtiming.repair
    qtiming.verdict
    qtiming.solve
    qtiming.oblig
    qtiming.graph | qtiming.dispatch
    qtiming.elab
    qtiming.contract | qtiming.frontend
    qtiming.core
```

The "synthesis-isolated" contract encodes principle 8 at the code level: nothing on the verification path can accidentally prove an obligation by asking a controllability question. The "executor-independence" contract encodes principle 9.

---

## 5. Core data model

The core is a small, frozen, standard-library-only representation of "timed OpenQASM 3" (TQ). Durations are integer `dt`, latency intervals carry structured provenance, every statement has a stable `nid` and a source location. All code is Python 3.10 compatible (`from __future__ import annotations`).

### 5.1 `core/time.py`

```python
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from .errors import QtError

Dt = int                       # integer multiples of the backend dt
Time = Fraction                # solver / executor time (exact rational, in dt)

# Rounding by ROLE (finding F7): ns -> dt depends on what the number means.
Role = Literal[
    "latency_lo",       # uncertain interval lower end          -> floor (outward)
    "latency_hi",       # uncertain interval upper end          -> ceil  (outward)
    "deadline",         # upper-bound requirement D             -> floor (tighter)
    "gap_bound",        # upper-bound requirement G             -> floor (tighter)
    "spread_bound",     # upper-bound requirement Delta         -> floor (tighter)
    "commit_lead",      # lower-bound requirement               -> ceil  (tighter)
    "min_separation",   # lower-bound requirement               -> ceil  (tighter)
    "exact",            # fixed gate / measure duration         -> must be an exact multiple of dt
]

_ROUND: dict[str, str] = {
    "latency_lo": "floor", "latency_hi": "ceil",
    "deadline": "floor", "gap_bound": "floor", "spread_bound": "floor",
    "commit_lead": "ceil", "min_separation": "ceil",
    "exact": "exact",
}

def ns_to_dt(ns: Fraction | int | str, dt_ns: Fraction, role: Role, *, what: str = "") -> Dt:
    """Convert nanoseconds to integer dt, rounding in the SOUND direction for `role`.

    `ns` must be a Fraction, int or decimal string. TOML floats are converted by the loader
    with Fraction(str(x)) so 0.1 never becomes 0.1000000000000000055.
    """
    q = Fraction(ns) / Fraction(dt_ns)
    mode = _ROUND[role]
    if mode == "floor":
        return q.numerator // q.denominator
    if mode == "ceil":
        return -((-q.numerator) // q.denominator)
    if q.denominator != 1:
        raise QtError("E-TIME-EXACT",
                      f"{what or 'value'} = {ns} ns is not an integer multiple of dt = {dt_ns} ns",
                      hint="fix the contract or Target; fixed durations must be exact")
    return q.numerator

def dt_to_ns(x: Time | Dt, dt_ns: Fraction) -> Fraction:
    return Fraction(x) * Fraction(dt_ns)

@dataclass(frozen=True, slots=True)
class Interval:
    """Closed interval [lo, hi] of dt; hi=None means unbounded above (verdict UNKNOWN for dependants)."""
    lo: Dt
    hi: Dt | None

    def __post_init__(self) -> None:
        if self.hi is not None and self.lo > self.hi:
            raise QtError("E-INTERVAL", f"empty interval [{self.lo}, {self.hi}]")

    @property
    def bounded(self) -> bool: return self.hi is not None

    def __add__(self, o: "Interval") -> "Interval":
        hi = None if self.hi is None or o.hi is None else self.hi + o.hi
        return Interval(self.lo + o.lo, hi)

    def hull(self, o: "Interval") -> "Interval":
        hi = None if self.hi is None or o.hi is None else max(self.hi, o.hi)
        return Interval(min(self.lo, o.lo), hi)

    def contains(self, x: Time) -> bool:
        return self.lo <= x and (self.hi is None or x <= self.hi)

@dataclass(frozen=True, slots=True)
class Latency:
    """A named uncertain latency from the contract: interval plus structured provenance."""
    key: str                     # contract name, e.g. "ff.intra"
    iv: Interval
    prov: "Prov"                 # core/provenance.py
```

Design notes:

- The sound direction is a property of how a number is used. A deadline of 3001 ns on a 4 ns grid becomes 750 dt (floor): 751 dt would admit executions that violate the stated deadline. A commit lead of 101 ns becomes 26 dt (ceil) for the same reason.
- `Interval` carries no provenance. Provenance attaches to named `Latency` entries and is combined in assumption sets (Section 5.2). This fixes the v1 bug where `__add__` dropped `source`.
- Fixed gate durations come from the `Target` or the contract as `exact`. A non-multiple of dt is a loader error, never a silent rounding.
- Inside the solver and the executor, time is `Fraction` in units of dt. Only program constants are integers.

### 5.2 `core/provenance.py` (finding F8)

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from fractions import Fraction
from typing import Iterable


class ProvClass(IntEnum):
    """Evidence class, ordered by strength. The order is used ONLY to name the weakest class.

    VENDOR  documentation or marketing claim, no method stated
    MSIGMA  mean and spread (e.g. 63 +- 17 us); never yields a bound by itself
    PCTL    percentile under a stated load; never yields a bound by itself
    MMAX    sample maximum over n runs
    SCHED   value reported by the vendor scheduler for a specific compiled job (Section 18):
            a deterministic fact about that job, not a bound over all jobs
    CYC     cycle-counted design bound
    CERT    formally certified worst case
    """
    VENDOR = 0
    MSIGMA = 1
    PCTL = 2
    MMAX = 3
    SCHED = 4
    CYC = 5
    CERT = 6

    @property
    def may_discharge_hard(self) -> bool:
        return self >= ProvClass.CYC


@dataclass(frozen=True, slots=True)
class Prov:
    cls: ProvClass
    source: str                              # citation, URL, job id, measurement id
    n: int | None = None                     # MMAX: sample count
    p: Fraction | None = None                # PCTL: percentile (e.g. 99/100)
    load: str | None = None                  # PCTL: stated load (e.g. "rho=0.8, simulation")
    k_sigma: Fraction | None = None          # MSIGMA: k used by whoever STATED hi explicitly
    meta: tuple[tuple[str, str], ...] = ()   # e.g. (("backend", "ibm_kingston"),)

    def __post_init__(self) -> None:
        if self.cls == ProvClass.MMAX and self.n is None:
            raise ValueError("mmax provenance requires n")
        if self.cls == ProvClass.PCTL and (self.p is None or self.load is None):
            raise ValueError("pctl provenance requires p and load")
        if self.cls == ProvClass.MSIGMA and self.k_sigma is None:
            raise ValueError("msigma provenance requires k_sigma (the contract must state hi explicitly)")


@dataclass(frozen=True, slots=True)
class Assumption:
    """One latency value a proof relied on. The verdict lists all of them."""
    key: str                      # contract latency key, e.g. "ff.intra"
    lo: int                       # dt
    hi: int | None                # dt
    prov: Prov


def weakest(assumptions: Iterable[Assumption]) -> ProvClass | None:
    """Weakest class among the assumptions; None for an empty set (nothing was assumed)."""
    classes = [a.prov.cls for a in assumptions]
    return min(classes) if classes else None


def combine(*sets: frozenset[Assumption]) -> frozenset[Assumption]:
    """Union. The full list is kept; it is never collapsed to a single class."""
    out: set[Assumption] = set()
    for s in sets:
        out |= s
    return frozenset(out)


def can_discharge(hard: bool, assumptions: frozenset[Assumption]) -> bool:
    """A hard obligation may be discharged only if every assumption is CYC or CERT."""
    return (not hard) or all(a.prov.cls.may_discharge_hard for a in assumptions)
```

Rules enforced elsewhere:

1. **mσ and pctl never produce a bound.** The loader accepts `prov = "msigma"` or `"pctl"` only if the entry also states `hi` explicitly, together with `k_sigma` or `p` and `load`. It never computes `hi = mean + k*sigma`. A contract that gives only mean and sigma loads with `hi = null`, and every obligation depending on it is UNKNOWN naming that key.
2. **Hard obligations.** If a hard obligation is proved but `can_discharge` is false, the obligation result is PROVED-UNDER and the report names the assumption that blocked a full PROVED.
3. **Sets, not minima.** Verdicts carry `frozenset[Assumption]`. The weakest class is a one-line summary; the table of assumptions is the content.
4. **The order is a summary only.** `SCHED` is not "stronger than `MMAX`" in every sense (it is exact for one job and says nothing about other jobs). No logic other than `may_discharge_hard` depends on the numeric order.

### 5.3 `core/ast.py` (TQ)

| Node | Fields | Notes |
| --- | --- | --- |
| `Gate` | `name, qubits, dur: Dt` | `dur` resolved from `Target` or contract at load; exact |
| `Delay` | `qubits, dur: Dt, declared: bool` | declared delays are intentional idle (O4a exempt) |
| `Barrier` | `qubits` | zero duration; a join over its resources |
| `Measure` | `qubit, cbit: BitRef, variant, tier` | `variant` is `std` or `mid` (IBM `measure` vs `measure_2`); `tier` selects the feedback-latency path |
| `Reset` | `qubit` | may itself be conditional on some backends |
| `Assign` | `var: str, expr: Expr` | classical real-time variable store (Qiskit `Store`) |
| `Seq` | `stmts: tuple[Node, ...]` | n-ary |
| `Box` | `dur: DurExpr or None, body, annotations` | `dur` may be a `Duration` or a stretch expression |
| `If` | `cond: Expr, then_, else_ or None, policy or None` | `policy` None means "contract default" until elaboration |
| `Switch` | `target: Expr, cases, default` | rejected on IBM; elaborates to nested `If` elsewhere |
| `For` | `var, n: int, body` | `n` static |
| `While` | `cond, body, cap: int, exhaust, policy` | `cap` and `exhaust` mandatory |
| `Call` | `fn, args, latency_key, blocking: bool` | bound by `timing.call` |
| `Within` | `deadline: Dt, anchor: BitRef, body` | the body's first operation must start within `deadline` of the anchor's valid time |

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Union

@dataclass(frozen=True, slots=True)
class SourceLoc:
    file: str
    line: int = 0
    col: int = 0
    instr: int | None = None       # Qiskit instruction index when no text position exists

@dataclass(frozen=True, slots=True)
class BitRef:
    reg: str                       # register NAME (string, not a Clbit object; finding F14)
    idx: int

PolicyKind = Literal["eq", "sync", "exp"]

@dataclass(frozen=True, slots=True)
class Policy:
    kind: PolicyKind
    delta: int | None = None       # SYNC spread bound (dt; rounded DOWN by the loader when given in ns)
    gap: int | None = None         # SYNC per-resource gap bound G (dt)

@dataclass(frozen=True, slots=True, kw_only=True)
class Node:
    nid: int
    loc: SourceLoc
    origin_nid: int | None = None  # set by elaboration for synthesised nodes

@dataclass(frozen=True, slots=True, kw_only=True)
class Gate(Node):
    name: str
    qubits: tuple[int, ...]
    dur: int

@dataclass(frozen=True, slots=True, kw_only=True)
class Delay(Node):
    qubits: tuple[int, ...]
    dur: int
    declared: bool = True

@dataclass(frozen=True, slots=True, kw_only=True)
class Measure(Node):
    qubit: int
    cbit: BitRef
    variant: Literal["std", "mid"] = "std"
    tier: str = "default"

@dataclass(frozen=True, slots=True, kw_only=True)
class Seq(Node):
    stmts: tuple["Stmt", ...]

@dataclass(frozen=True, slots=True, kw_only=True)
class If(Node):
    cond: "Expr"
    then_: "Stmt"
    else_: "Stmt | None" = None
    policy: Policy | None = None

# Reset, Barrier, Assign, Box, Switch, For, While, Call, Within follow the table above.
```

Rules for `nid`: assigned by one `IdGen` in source order during front-end construction and never recomputed. Elaboration creates new nodes with fresh IDs and records `origin_nid`, so every graph node can point back to a source line. Every counterexample and every SARIF result cites the origin `nid` and `loc`.

### 5.4 `core/labels.py` (findings F13, F29)

Propositions come in two kinds.

- **Bit propositions** are keyed by measurement occurrence: `"c0@m17#i3"` means "the value written into `c0` by measurement node 17 in unrolled iteration 3". They are the only primitive outcome variables (ω).
- **Derived propositions** are one per condition evaluation: `"cond@n42#i3"` means "the Boolean value of the condition of `if` node 42 in iteration 3". It carries an expression tree over bit propositions, constants and real-time variables.

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Union

Prop = str   # "c0@m17#i3" or "cond@n42#i3"

@dataclass(frozen=True, slots=True)
class Lit:
    prop: Prop
    pos: bool = True

Label = frozenset[Lit]            # conjunction of literals; empty = always true
TOP: Label = frozenset()

def consistent(a: Label, b: Label) -> bool:
    return not any(Lit(l.prop, not l.pos) in b for l in a)

def conj(a: Label, b: Label) -> Label | None:
    return None if not consistent(a, b) else a | b

def implies(a: Label, b: Label) -> bool:      # every literal of b appears in a
    return b <= a

# Expression language: what real controllers support plus Qiskit expr operators.
@dataclass(frozen=True, slots=True)
class EBit:   prop: Prop
@dataclass(frozen=True, slots=True)
class EConst: value: int; width: int = 1
@dataclass(frozen=True, slots=True)
class EVar:   name: str; width: int          # real-time classical variable (Var/Store)
@dataclass(frozen=True, slots=True)
class EUn:    op: str; a: "Expr"             # "not", "bit_not"
@dataclass(frozen=True, slots=True)
class EBin:   op: str; a: "Expr"; b: "Expr"  # "and" "or" "xor" "eq" "ne" "lt" "le" "gt" "ge" "bit_xor" ...

Expr = Union[EBit, EConst, EVar, EUn, EBin]

@dataclass(frozen=True, slots=True)
class Derived:
    prop: Prop                 # "cond@n42#i3"
    expr: Expr                 # exact definition over bit propositions / variables
    operands: tuple[Prop, ...] # bit propositions the expression reads (for the valid-time max)
```

Semantics of derived propositions:

- **Observation time.** The controller evaluates the condition after the last of its operand bits is available. The builder creates a node `valid(cond)` with a zero-weight dispatch edge from every operand's `valid` node, so `t_valid(cond) = max over operands`. This is a sound over-approximation of any cleverer hardware that could evaluate parity earlier.
- **Value.** The executor evaluates `expr` exactly from the measured bits (ω). Tier 2 encodes `Derived.prop <=> expr(bits)` exactly. Tiers 0 and 1 may treat the derived proposition as free (more behaviours, so still sound).
- **No disjunct duplication.** `c > 2` over a 3-bit register is one derived proposition, not a disjunction of labels with duplicated branch bodies. v1's 32-disjunct cap disappears.
- **IBM restriction.** IBM does not accept arithmetic or shifts in conditions and limits operands to 32 bits; the front-end lint (Section 6.6) rejects them for the IBM contract. The core model handles them for other backends.
- **Variables.** A `Store` into a classical `Var` becomes an `Assign` node. `EVar` reads resolve to the latest assignment's expression during elaboration (substitution inside a straight-line region; across unrolled loop iterations the unroller renames).

### 5.5 `core/errors.py`

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

Severity = Literal["error", "warning", "note"]

@dataclass(frozen=True, slots=True)
class QtError(Exception):
    code: str                  # stable id, also the SARIF ruleId, e.g. "E-FE-UNBOUNDED-WHILE"
    message: str
    loc: "SourceLoc | None" = None
    hint: str | None = None
    severity: Severity = "error"
```

Code families:

| Prefix | Meaning | Examples |
| --- | --- | --- |
| `E-TIME-*` | time and rounding | `E-TIME-EXACT`, `E-INTERVAL` |
| `E-FE-*` | front end | `E-FE-UNBOUNDED-WHILE`, `E-FE-BIT-UNWRITTEN`, `E-FE-CALL-UNBOUND`, `E-FE-ANNOT-BIT` |
| `E-LINT-IBM-*` | IBM restrictions | `E-LINT-IBM-NESTED-IF`, `E-LINT-IBM-MEAS-IN-IF`, `E-LINT-IBM-SWITCH`, `E-LINT-IBM-OPERAND-WIDTH`, `E-LINT-IBM-ARITH-COND` |
| `E-CT-*` | contract | `E-CT-MISSING`, `E-CT-SCHEMA`, `E-CT-PROV-HI` |
| `E-ELAB-*` | elaboration | `E-ELAB-POLICY-INCOMPAT`, `E-ELAB-EQ-VARIABLE-ARM` |
| `E-GRAPH-*` | builder invariants | `E-GRAPH-LABEL`, `E-GRAPH-CYCLE`, `E-GRAPH-CUT` |
| `V-O1` ... `V-O9`, `V-O4A` | obligation findings (verdict results) | `V-O1` underflow |
| `I-*` | internal errors | `I-REPLAY-MISMATCH`, `I-TIER-DISAGREE` |

---

## 6. Front end

The primary front end walks a Qiskit `QuantumCircuit` (control-flow ops recursively) and emits TQ. Timing intent travels as custom `Annotation` objects on `BoxOp`, which round-trip through OpenQASM 3 and QPY without changing either language. A secondary front end parses raw OpenQASM 3 text with the `openqasm3` package for programs Qiskit cannot import. Both produce the same TQ AST (Section 5.3) with stable `nid`s.

### 6.1 Entry points

```python
# qtiming/frontend/__init__.py
def from_circuit(qc: "QuantumCircuit", *, target: "Target | None" = None,
                 contract: "Contract | None" = None) -> "Program": ...
def from_qasm3(text: str, *, filename: str = "<string>") -> "Program": ...
def from_qpy(path: str) -> "Program": ...

@dataclass(frozen=True, slots=True)
class Program:
    body: Stmt
    qubits: tuple[int, ...]
    bits: tuple[BitRef, ...]
    vars: tuple[tuple[str, int], ...]          # real-time classical variables (name, width)
    notes: tuple[QtError, ...]                 # warnings and notes from the front end
```

`target` and `contract` are optional at this stage; they are used only to fill gate durations and measure tiers early. Elaboration repeats the lookup if they were absent, so the front end is usable on its own for linting.

### 6.2 Qiskit walker: instruction to TQ mapping

The walker iterates `circuit.data` in program order (never the DAG order, which may reorder commuting ops), recursing into control-flow blocks. Per-qubit and per-clbit cursors are not kept here; scheduling is the graph builder's job. Control-flow bodies in Qiskit 2.x are `QuantumCircuit` blocks whose qubits and clbits map to the outer circuit through the instruction's operand lists; the walker builds the map explicitly and does not rely on positional equality.

| Qiskit instruction | TQ node | Duration source | Notes |
| --- | --- | --- | --- |
| standard gate | `Gate` | `Target[name][qargs].duration`, else contract `[durations]` | exact multiple of dt or `E-TIME-EXACT` |
| `Delay(d, unit)` | `Delay(declared=True)` | converted to dt; `unit="dt"` passes through | a `Stretch` duration is resolved in `stretch.py` |
| `Measure` | `Measure(variant="std")` | `target["measure"]` | feedback tier assigned from the contract topology |
| IBM `measure_2` (MidCircuitMeasure) | `Measure(variant="mid")` | `target["measure_2"]` | separate Target entry with its own duration; ~65% shorter than `measure`, ~940 ns faster capture (vendor) |
| `Reset` | `Reset` | contract | conditional reset on some backends |
| `IfElseOp(condition, true_body, false_body)` | `If(cond, then_, else_)` | n/a | condition may be a `(bit|register, value)` tuple or an `expr.Expr` (Section 6.3); `else` body optional |
| `ForLoopOp(indexset, loop_parameter, body)` | `For(n=len(indexset))` | n/a | non-range index sets are allowed; the loop parameter is substituted per iteration |
| `WhileLoopOp(condition, body)` | `While` | n/a | requires `timing.cap` and an exhaust handler, else `E-FE-UNBOUNDED-WHILE` |
| `SwitchCaseOp(target, cases)` | `Switch` | n/a | rejected on IBM contracts (`E-LINT-IBM-SWITCH`); elsewhere elaborated into a chain of `If` on derived propositions |
| `BoxOp(body, duration, unit, annotations)` | `Box` | `duration` may be `Duration` or `Stretch` expression | annotations parsed into policy, within, cap, etc. |
| `Barrier` | `Barrier` | zero | join over its qubits |
| `Store(lvalue, rvalue)` | `Assign(var, expr)` | zero (classical) | real-time classical variable update; condition reads later resolve to the stored expression |
| `expr.Var` declarations | recorded in `Program.vars` | n/a | width and initial value; scoped to the circuit |
| any other instruction | `Gate` if in the Target, else `E-FE-UNKNOWN-OP` | | no silent default durations |

Two engineering rules:

- **Do not mutate Qiskit objects.** From Qiskit 2.3 control flow is Rust-native. The front end only reads. Passes that rewrite circuits (`qiskit_pass/`, Section 19) build new circuits and substitute through the DAG API rather than editing a box's annotations in place.
- **Occurrence keys.** Each `Measure` receives `nid = m`. The bit proposition it writes is `"<reg><idx>@m<m>#<iter>"` where `iter` is the loop-unrolling iteration path (empty at top level). Two measurements into the same classical bit are different propositions.

### 6.3 Conditions: `expr`, registers and bits (finding F13)

Qiskit 2.x allows `if_test` conditions as `(Clbit, int)`, `(ClassicalRegister, int)`, or `expr.Expr` trees (`expr.bit_xor`, `expr.equal`, `expr.less`, `expr.logic_and`, `expr.logic_or`, `expr.logic_not`, `expr.bit_and`, `expr.bit_or`, shifts, casts, constants, `Var`, and register or bit references). `qiskit_expr.py` converts each into the core `Expr` (Section 5.4) by a small recursive visitor and refuses (with `E-FE-EXPR-UNSUPPORTED`) any operator outside a documented list.

Rules:

1. **One derived proposition per condition evaluation.** For `IfElseOp` node `n` in iteration path `i`, create `Derived(prop="cond@n#i", expr=E, operands=bit propositions read by E)`.
2. **Operand resolution.** A bit or register reference resolves to the most recent measurement occurrence that wrote it on the current program path. If control flow merges writers (a bit written in both arms of an earlier `if`), the operand is a derived merge proposition `"phi@n#i"` defined as `ite(cond_of_that_if, bit_from_then, bit_from_else)` with `valid` time equal to the join of the two. A read with no dominating writer is `E-FE-BIT-UNWRITTEN`.
3. **Valid time.** The condition is observed at the maximum of its operands' valid times (Section 5.4). This keeps parity conditions sound without modelling hardware that might evaluate early.
4. **`else`.** The else body is attached to the same derived proposition with negative polarity. An absent `else` is `None` (the elaborator decides what the empty arm costs under the policy).
5. **`Var` and `Store`.** A `Store` in program order updates a substitution map `var -> Expr`; a later condition reading the var substitutes the expression (so conditions are always over bit propositions and constants). A `Store` inside a conditional arm creates a merge expression at the join using the arm's derived proposition. Loops rename per iteration.

### 6.4 The `timing.*` annotation namespace (findings F11, F14)

Users express policy and deadlines by wrapping code in a `box` and attaching annotations. OpenQASM 3 form:

```text
OPENQASM 3.0;
include "stdgates.inc";
qubit[3] q; bit[2] c;

h q[1]; cx q[1], q[2];
cx q[0], q[1]; h q[0];
c[0] = measure q[0];
c[1] = measure q[1];

@timing.policy eq
@timing.within 3000ns c[1]
box {
  if (c[1]) { x q[2]; }
  if (c[0]) { z q[2]; }
}
```

Qiskit form:

```python
from qtiming.frontend.annotations import Policy, Within

with qc.box(annotations=[Policy("eq"), Within(3000, unit="ns", anchor="c[1]")]):
    with qc.if_test((c[1], 1)):
        qc.x(2)
    with qc.if_test((c[0], 1)):
        qc.z(2)
```

| Annotation (`timing.` prefix) | Payload | Meaning | Default when absent |
| --- | --- | --- | --- |
| `policy` | `eq` \| `sync(delta=<dur>,gap=<dur>)` \| `exp` | branch policy for every `if`, `switch` and `while` in the box | contract `branch.default_policy` |
| `within` | `<dur> <bitname>` | the first operation of the box body must start within the duration of the anchor bit's valid time (O3) | none |
| `cap` | `<N> exhaust=<label>` | iteration cap for a `while` in the box; the exhaust handler is the box named by the label, or the `else` of the loop | `while` without cap is `E-FE-UNBOUNDED-WHILE` |
| `pmin` | `<rational>` | declared lower bound on per-iteration success probability for RUS | none; expected-time verdict skipped |
| `declared_idle` | (none) | gaps inside the box are intentional (exempt from O4a) | not exempt |
| `call` | `<fn> latency=<key>` | binds an extern or `device_call` to a contract latency entry | `E-FE-CALL-UNBOUND` |
| `hard` | (none) | all obligations attached to this box are hard (discharged only by `cert` or `cyc`) | contract default |
| `cut` | (none) | request a window cut after this box (accepted only if the cut rules of Section 9.7 hold) | none |

Design points:

- **Bits are named by strings** (`"c[1]"`, register name plus index), never by `Clbit` objects, because `Clbit` instances are not serialisable through QASM3 or QPY and differ between circuit copies. Resolution to the actual bit happens in the front end against the circuit's registers; failure is `E-FE-ANNOT-BIT`.
- **Durations carry their unit** (`3000ns`, `750dt`, `3us`). The front end converts with the role-aware rounding: `within` uses role `deadline`; `sync delta` uses `spread_bound`; `sync gap` uses `gap_bound`.
- **One namespace, no collisions.** IBM's Samplomatic uses box annotations under its own namespaces. We use `timing` only and test that a circuit carrying both round-trips intact.

Serialiser sketch (class and method names to be confirmed against the Qiskit 2.6 API documentation **[verify]** when implementing; the verified facts are: annotations subclass `Annotation` with a `namespace`; `QuantumCircuit.box(annotations=...)`; `qasm3.dumps(..., annotation_handlers=...)`; `qpy.dump(..., annotation_factories=...)`; QPY format version 15):

```python
# qtiming/frontend/annotations.py   (requires qiskit)
from qiskit.circuit import annotation

class TimingAnnotation(annotation.Annotation):
    namespace = "timing"
    kind: str = ""
    def __init__(self, payload: str): self.payload = payload
    def __eq__(self, o): return type(self) is type(o) and self.payload == o.payload
    def __hash__(self): return hash((type(self).__name__, self.payload))

class Policy(TimingAnnotation):  kind = "policy"
class Within(TimingAnnotation):  kind = "within"
class Cap(TimingAnnotation):     kind = "cap"
# ... PMin, DeclaredIdle, Call, Hard, Cut

# qtiming/frontend/serialise.py
class TimingQasm3Handler:                       # passed as annotation_handlers={"timing": TimingQasm3Handler()}
    def dump(self, ann: TimingAnnotation) -> str | None:
        return f"{ann.kind} {ann.payload}".strip()          # rendered as `@timing.<kind> <payload>`
    def load(self, namespace: str, payload: str) -> TimingAnnotation:
        kind, _, rest = payload.partition(" ")
        return _CLASSES[kind](rest)

class TimingQpyFactory:                          # passed as annotation_factories={"timing": TimingQpyFactory}
    ...                                          # dump_annotation / load_annotation, payload is UTF-8 bytes
```

Golden test: for every benchmark carrying annotations, `qasm3.loads(qasm3.dumps(qc, annotation_handlers=H), annotation_handlers=H) == qc` and the same for QPY; plus a test that annotation payload strings re-parse to an identical `Policy`/`Within`/... record.

### 6.5 OpenQASM 3 fallback front end

`qasm3_fe.py` uses `openqasm3.parser.parse` and maps its AST: `QuantumGate`, `DelayInstruction`, `QuantumMeasurementStatement`, `BranchingStatement`, `ForInLoop`, `WhileLoop`, `Box`, `Annotation` nodes. Differences from the Qiskit path:

- `@timing.*` annotations are read directly from the parser's annotation lists.
- Gate durations are not available from a Target; they must come from the contract (`[durations]`), else `E-CT-MISSING`.
- `stretch`, `duration` and `durationof` are resolved with the same `stretch.py`.
- Constructs outside the supported fragment (subroutines with side effects, `defcal` bodies, arbitrary-width arithmetic) are rejected with a precise `E-FE-UNSUPPORTED` and a pointer to the line.

Equivalence test: for programs expressible in both front ends, the TQ ASTs are equal modulo `loc` and `nid`.

### 6.6 Stretch resolution and per-backend lint

**Stretch.** `stretch.py` collects, per region between barriers, the linear equations arising from `box[d]` (the sum of contained durations, including stretch terms, equals `d`) and the non-negativity of every stretch. Coefficients are `Fraction`. Gaussian elimination over `Fraction` solves the equalities; a unique non-negative solution is recorded as the resolved values. If the system is under-determined, the stretch is a compile-time degree of freedom: the front end resolves it to the **minimal non-negative solution** and emits a warning `W-FE-STRETCH-AMBIGUOUS` naming the variable. In `--strict` mode it is an error. Over-determined inconsistent systems are `E-FE-STRETCH-INCONSISTENT`. IBM restricts stretch to a single stretch per qubit set per barrier region in the linear form `X*stretch + Y`; the IBM lint checks that restriction when an IBM contract is selected. The question "could some stretch assignment make the program safe?" is a synthesis question (Section 12), not part of verification.

**Lint.** Front-end lint rules are static and need no solver. They run when a contract with the corresponding `personality` is selected. Each is a `QtError` with a hint.

| Rule | Backend | Condition rejected | Source |
| --- | --- | --- | --- |
| `E-LINT-IBM-ELSEIF` | IBM | `else if` chains (only `if` and `else` supported) | IBM docs (Appendix C) |
| `E-LINT-IBM-LOOP` | IBM | `for`, `while` and `switch` control flow | same |
| `E-LINT-IBM-NESTED-IF` | IBM | nested `if` | same |
| `E-LINT-IBM-MEAS-IN-IF` | IBM | `measure` or `reset` inside a conditional | same |
| `E-LINT-IBM-ARITH-COND` | IBM | arithmetic or shift operators in conditions | same |
| `E-LINT-IBM-OPERAND-WIDTH` | IBM | condition operand wider than 32 bits | same |
| `E-LINT-IBM-BROADCAST` | IBM | estimated broadcasts exceed the job budget (about 300 broadcasts of 60 bits, or 2400 of 1 bit) | IBM job limits |
| `E-LINT-IBM-INSTR-BUDGET` | IBM | estimated instructions per qubit exceed 26.8 M | IBM job limits |
| `E-LINT-IBM-BOX` | IBM | `box` present at submission (use `StripTimingAnnotations`) **[verify]** | IBM docs |
| `E-LINT-Q1-COND` | Q1 | condition not reducible to one `set_cond` form (mask over trigger-network addresses with one logic operator) **[verify against Q1ASM docs]** | Qblox Q1 docs |
| `E-LINT-QUA-STRICT` | QUA | a non-deterministic align would appear while `strict_timing_` is on | QUA timing guide |
| `E-LINT-ARTIQ-WHILE` | ARTIQ | none (ARTIQ kernels are Python; unbounded loops still rejected by the checker's own scope) | scope |

Lint findings are reported before any solving. A lint error in a hard rule stops the run with exit code 2; a warning does not.

### 6.7 `StripTimingAnnotations` (finding F11)

IBM rejects `box` on direct submission (boxes are used only through Samplomatic and the Executor) **[verify against current docs before release]**. A circuit annotated for the checker must therefore be convertible back to a submittable circuit.

```python
class StripTimingAnnotations(TransformationPass):
    """Remove timing.* annotations. Unwrap a BoxOp that carries no non-timing annotations
    and has no explicit duration (it existed only to carry timing intent).
    Keep boxes with a duration (they are real timing constructs), or with other namespaces."""
```

Properties tested: (a) idempotent; (b) output contains no `timing` namespace annotation; (c) gate and control-flow content equals the input's; (d) `TimingCheck` run before and `StripTimingAnnotations` after leaves the verdict stored in the property set intact.

### 6.8 Feedback tier map

The latency of "measurement result becomes usable by a consumer" depends on where the measurement and the consumer sit. The contract declares a topology and a tier map; the front end tags each `Measure` with the tier that applies to each of its consumers.

```toml
[topology]
# module membership; qubit index -> module name (can be generated from a Target coupling map or a hand table)
modules = { m0 = [0, 1, 2, 3], m1 = [4, 5, 6, 7] }

[[feedback_tier]]
name = "intra"          # measure and consumer on the same module
match = { same_module = true }
[[feedback_tier]]
name = "multicast"      # consumer on a different module of the same chassis
match = { same_module = false, same_chassis = true }
[[feedback_tier]]
name = "network"
match = { same_chassis = false }
```

A `Measure` that feeds consumers in different tiers produces one contingent latency variable per (measurement occurrence, tier). The latency entries in `[[latency]]` are looked up by `(src="measure", dst="branch", tier=<name>)`. If a needed tier has no entry, the check returns UNKNOWN naming the missing `(src, dst, tier)`.

---

## 7. The timing contract

A contract is a per-backend TOML (or JSON) file, separate from the program, in which every uncertain number carries structured provenance. The loader validates it with pydantic, converts every value to integer `dt` using role-aware rounding (Section 5.1), merges in what a Qiskit `Target` already knows, and refuses to load a contract with a missing required field. Where a number is not published, the field is present with an explicit marker and every obligation that needs it is UNKNOWN, naming the field.

### 7.1 Schema, clause by clause

| Clause | Required | Feeds | Content and validation rule |
| --- | --- | --- | --- |
| `[meta]` | yes | all | `name`, `version`, `schema = "qtiming-contract/0.2"`, `personality` in `{ibm, artiq, q1, qua}` |
| `[target]` | IBM only | durations, dt | where dt, alignments and durations come from: `source = "backend" or "snapshot:<file>" or "none"`; `backend` name; list of imported groups |
| `[timebase]` | yes | O8 | `dt_ns` (decimal string or `"from_target"`), `grid` per op class in dt (`gate`, `acquire`, `rt`, `feedback`); `latency_resolution = "continuous"` (default) or `"dt"` |
| `[timeline]` | yes | O1 | `commit_lead` (lower-bound requirement, rounded up), `late_policy` in `{raise, drop_log, delay, defer_round, halt, compile_error}`; absent commit lead on a personality that needs one is UNKNOWN |
| `[issue_cost]` | Q1, ARTIQ | O1 | classical instruction costs: name to `{taken, not_taken}` or a single cost, with provenance (`cyc` where cycle counted) |
| `[capacity]` | yes | O5 | personality-specific: ARTIQ `lanes`, `coarse_mu`, `sed_spread_enable`, `fifo_depth`; Q1 `rt_queue_depth`; IBM `instr_per_qubit`, `broadcast_budget`; QUA none |
| `[durations]` | yes | all | gate and measure durations; for IBM mostly imported from the Target; each entry `exact` |
| `[[latency]]` | yes, at least 1 | O2, O3, O6 | `key`, `src`, `dst`, `tier`, `lo_ns`, `hi_ns` (may be absent = unbounded), `prov` and its fields, `source`, `data_dependent`, optional `placeholder = true` |
| `[topology]`, `[[feedback_tier]]` | optional | tier tags | which measure to consumer pairs use which latency tier (Section 6.8) |
| `[branch]` | yes | compatibility | `class` in `{predicated, equalized, resync, exposed, restricted}`, `default_policy`, `allow_nested`, `allow_measure_in_branch`, `allow_loops`, `max_cond_bits` |
| `[personality_params]` | per personality | dispatch | named parameters for undocumented behaviour (Section 7.3); each with provenance |
| `[dep]` | optional | O2, O3 | consumer constraints: deadline, freshness, version triples |
| `[domain_call]` | optional | O6 | WCET and RTT both present (hi bounded) or the entry is unusable |
| `[sync]` | optional | O7 | cost per participant count and tier: contingent interval with provenance |
| `[idle]` | yes | O4, O4a | `max_gap_variation_ns` per resource or default (O4); optional advisory `max_gap_ns` (O4a); `dd_inserted_by_backend = "unknown"` default |
| `[loop]` | yes | O9 | `while_supported`, consistency with `branch.allow_loops` |
| `[evidence]` | optional | traceability | list of ingested evidence patches (job ids, hashes) applied to this contract |

Cross-rules: `lo <= hi` when both present; `prov = "mmax"` requires `n`; `prov = "pctl"` requires `p` and `load`; `prov = "msigma"` requires an explicit `hi_ns` plus `k_sigma`; a latency used by an `[[feedback_tier]]` must exist for that tier; `latency_resolution = "dt"` forces integer endpoints.

### 7.2 Pydantic models (`contract/schema.py`)

```python
from __future__ import annotations
from fractions import Fraction
from typing import Literal, Annotated
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Num = Annotated[str | int, Field(description="decimal string or int; floats are rejected to avoid binary rounding")]

class ProvIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    cls: Literal["vendor", "msigma", "pctl", "mmax", "sched", "cyc", "cert"] = Field(alias="prov")
    source: str
    n: int | None = None
    p: Num | None = None
    load: str | None = None
    k_sigma: Num | None = None
    placeholder: bool = False
    meta: dict[str, str] = {}

    @model_validator(mode="after")
    def _need_fields(self) -> "ProvIn":
        if self.cls == "mmax" and self.n is None: raise ValueError("mmax requires n")
        if self.cls == "pctl" and (self.p is None or self.load is None): raise ValueError("pctl requires p and load")
        if self.cls == "msigma" and self.k_sigma is None: raise ValueError("msigma requires k_sigma")
        return self

class LatencyIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)
    key: str
    src: str
    dst: str
    tier: str = "default"
    lo_ns: Num = 0
    hi_ns: Num | None = None                 # None = unbounded; dependants are UNKNOWN
    data_dependent: bool = False
    prov: ProvIn

    @model_validator(mode="after")
    def _msigma_hi(self) -> "LatencyIn":
        if self.prov.cls in ("msigma", "pctl") and self.hi_ns is None:
            raise ValueError("msigma/pctl entries must state hi_ns explicitly; hi is never derived")
        return self

class BranchIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    klass: Literal["predicated", "equalized", "resync", "exposed", "restricted"] = Field(alias="class")
    default_policy: Literal["eq", "sync", "exp"]
    allow_nested: bool = True
    allow_measure_in_branch: bool = True
    allow_loops: bool = True
    max_cond_bits: int = 64

class TimebaseIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    dt_ns: Num                                # "from_target" allowed only when [target] present
    grid: dict[str, int] = {}
    latency_resolution: Literal["continuous", "dt"] = "continuous"

class ContractIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    meta: dict
    target: dict | None = None
    timebase: TimebaseIn
    timeline: dict
    issue_cost: dict | None = None
    capacity: dict
    durations: dict
    latency: list[LatencyIn] = Field(min_length=1)
    topology: dict | None = None
    feedback_tier: list[dict] = []
    branch: BranchIn
    personality_params: dict = {}
    dep: list[dict] = []
    domain_call: list[dict] = []
    sync: dict | None = None
    idle: dict
    loop: dict
    evidence: list[dict] = []
```

The loader converts `ContractIn` into the frozen core `Contract` (all times integer `dt`, `Latency` and `Prov` objects from `core`), which is what the rest of the pipeline sees.

### 7.3 The four shipped instances

Each instance is written only from public documentation. Every number's source is in its `source` field. A number not published is absent (unbounded) or a flagged placeholder, so a verdict depending on it is UNKNOWN or carries the placeholder in its assumption list.

#### 7.3.1 `ibm_heron.toml` (finding F20, F21, F12)

```toml
[meta]
name = "ibm_heron"
version = "0.2.0"
schema = "qtiming-contract/0.2"
personality = "ibm"

[target]
source = "backend"                    # or "snapshot:<file>" for offline use (the unofficial Heron r2 snapshot is a test fixture only)
backend = "ibm_kingston"
import = ["dt", "alignments", "durations"]   # taken from backend.target; NOT hard-coded here

[timebase]
dt_ns = "from_target"                 # unofficial snapshot reports dt = 4 ns, alignments = 1 for Heron r2
latency_resolution = "continuous"

[timeline]
late_policy = "compile_error"
# commit_lead: IBM does not expose a commit model; not required for this personality

[durations]
# gate, measure and measure_2 durations come from the Target. `measure` and `measure_2`
# (MidCircuitMeasure) are separate Target entries and differ per backend.
# Unofficial snapshot (fixture only): measure fez 1660 ns, kingston 2180 ns, marrakesh 2684 ns;
# measure_2 1340, 1380, 1884 ns respectively.
import_from_target = true

[[latency]]
key = "ff.default"
src = "measure"; dst = "branch"; tier = "default"
lo_ns = 0                              # conservative placeholder: no lower bound is published
hi_ns = 600
data_dependent = false
prov = "vendor"
source = "IBM blog, 2025-11-19 (feedforward about 600 ns); vendor claim, not a certified bound"

[branch]
class = "restricted"
default_policy = "sync"
allow_nested = false
allow_measure_in_branch = false
allow_loops = false
max_cond_bits = 32

[capacity]
instr_per_qubit = 26_800_000
broadcast_budget = { wide_60bit = 300, narrow_1bit = 2400 }   # approximate job limits, verify at release

[personality_params.ibm]
# Join behaviour for unequal if/else arms.
#   "pad_to_longest_block": both arms are padded to the longest block (documented for the OLD fast-path stack,
#                           qiskit-ibm-runtime <= 0.39 only)
#   "restart_at_join":      each arm ends when it ends; the next block restarts at the join
join_behavior = "pad_to_longest_block"
join_behavior_prov = { prov = "vendor", source = "old fast-path stack docs; to be calibrated from scheduler_timing evidence (Section 18)" }

[idle]
max_gap_variation_ns = { default = 0 }     # O4: unplanned gap = a gap whose length varies with (omega, theta)
dd_inserted_by_backend = "unknown"          # not documented in the sources reviewed (finding F12)

[loop]
while_supported = false
```

Notes:

- **Nothing about alignments or granularity is hard-coded.** The IBM `Target` exposes `dt`, `acquire_alignment`, `pulse_alignment`, `granularity`, `min_length`. The loader copies them into `Contract.grid`. The unofficial snapshot listing dt = 4 ns and alignments of 1 for Heron r2 is used only as an offline test fixture and is labelled unofficial in the repository.
- **Timing of feedforward.** The 600 ns figure is a vendor claim about the standard path; `lo_ns = 0` is a conservative widening, not a measurement. Evidence ingestion (Section 7.7, 18) replaces it with `sched`-class numbers and, when enough jobs exist, `mmax(n)`.
- **IBM has more than one feedforward path.** If evidence shows different timing for `measure` and `measure_2`, or for different qubit sets, additional `[[latency]]` entries and `[[feedback_tier]]` rows are added (`ff.mid`, and so on).

#### 7.3.2 `q1.toml` (finding F15, F16)

```toml
[meta]
name = "qblox_q1"
version = "0.2.0"
schema = "qtiming-contract/0.2"
personality = "q1"

[timebase]
dt_ns = "4"                              # RT instruction durations are multiples of 4 ns
grid = { rt = 1 }

[timeline]
commit_lead = { lo_ns = 0, prov = { prov = "cyc", source = "Q1 docs: RT queue is fed ahead of use; lead = classical issue cost, see [issue_cost]" } }
late_policy = "halt"                     # SEQUENCE_PROCESSOR_RT_EXEC_COMMAND_UNDERFLOW; sequencer halts

[issue_cost]                             # classical Q1 core, ns (cycle-counted design values)
set_mov  = { ns = 4,  prov = "cyc", source = "Q1 instruction table (v1 value; re-verify)" }
alu      = { ns = 12, prov = "cyc", source = "Q1 instruction table (v1 value; re-verify)" }
nop      = { ns = 4,  prov = "cyc", source = "Q1 docs" }
jmp      = { ns = 16, prov = "cyc", source = "Q1 docs" }
cond_jump = { taken_ns = 24, not_taken_ns = 4, prov = "cyc", source = "Q1 docs: jge, jlt, loop" }
# Old jge/jlt/loop forms are deprecated; the current form is cmp or sub followed by a flag jump,
# i.e. ONE EXTRA INSTRUCTION. The elaborator inserts it (cost = alu).

[capacity]
rt_queue_depth = 32                       # real-time instruction queue; underflow halts, overflow back-pressures the Q1 core

[[latency]]
key = "trigger.network"                   # measurement thresholded result -> all trigger-network receivers
src = "measure"; dst = "branch"; tier = "all_receivers"
lo_ns = 212
hi_ns = 239                               # 212 to 239 ns depending on the 28 ns timegrid
prov = "vendor"
source = "docs.qblox.com trigger_handling; documented figure, not cycle-certified [verify page path]"

[[latency]]
key = "trigger.network_busy"              # network occupied; free again after 252 ns (a SECOND trigger inside this window is lost or delayed)
src = "network"; dst = "network"; tier = "all_receivers"
lo_ns = 252; hi_ns = 252
prov = "vendor"
source = "docs.qblox.com trigger_handling"

[[latency]]
key = "path.opip.base"                    # OP + IP base
src = "measure"; dst = "network"; tier = "base"
lo_ns = 149; hi_ns = 149
prov = "vendor"
source = "docs.qblox.com trigger_handling: output 40 ns (baseband) or 50 ns (RF) + input 109 ns"

[[latency]]
key = "path.rtp_output"                   # real-time-processing output adder
src = "rt"; dst = "output"; tier = "rtp"
lo_ns = 24; hi_ns = 24
prov = "vendor"
source = "docs.qblox.com trigger_handling"

# Consistency fixture (not a contract entry): the documented worked example totals 388 ns.
# 149 (OP+IP) + 239 (network, worst timegrid case) = 388, so the golden test asserts that the
# contract-derived end-to-end path reproduces 388 ns. [verify the decomposition against the page]

[branch]
class = "predicated"
default_policy = "eq"
allow_nested = true
allow_measure_in_branch = true
allow_loops = true
max_cond_bits = 15                         # trigger-network addresses [verify]

[personality_params.q1]
set_cond_else_time_per_instruction = true  # else_time ns are waited PER skipped RT instruction (Section 8.5)
ttl_input_speedup_ns = 35                   # TTL input path is 35 ns faster than the standard input path (documented)

[idle]
max_gap_variation_ns = { default = 0 }
dd_inserted_by_backend = "unknown"

[loop]
while_supported = true
```

Corrected semantics (replacing v1's 160/250/472 ns and its set_cond description):

- **Trigger network.** The result of a thresholded acquisition reaches all receivers after 212 ns (212 to 239 ns depending on the 28 ns timegrid). The network is occupied until 252 ns after the trigger; a second trigger inside that window is a hazard the Q1 personality flags (O5, network occupancy).
- **`set_cond`.** The condition is evaluated before EVERY real-time instruction. If it is false, the RT core waits `else_time` ns for that instruction instead of executing it. Equal arms therefore require equal instruction counts and equal durations, per instruction. Two arms with different RT-instruction sequences can produce different total durations even if the user "padded" to the same total. Section 8.5 models this per instruction.
- **Underflow.** The RT queue holds 32 instructions. If the queue is empty when the RT core needs its next instruction, it raises `SEQUENCE_PROCESSOR_RT_EXEC_COMMAND_UNDERFLOW` and the sequencer halts. Classical instruction costs (above) determine how fast the Q1 core can refill the queue.

#### 7.3.3 `artiq.toml` (finding F17)

```toml
[meta]
name = "artiq_rtio"
version = "0.2.0"
schema = "qtiming-contract/0.2"
personality = "artiq"

[timebase]
dt_ns = "1"                               # machine unit mu = 1 ns (typical)
grid = { coarse = 8 }                     # coarse clock typically 125 MHz = 8 mu

[timeline]
# commit_lead is a REQUIRED but UNPUBLISHED number (minimum slack for an RTIO write to be accepted).
# Left absent: obligations depending on it are UNKNOWN until the user supplies --assume timeline.commit_lead=...
late_policy = "mixed"                     # underflow/overflow: raise; sequence/collision/busy: drop_log (see below)

[capacity]
lanes = 8                                 # SED lanes, gateware parameter sed_lanes (default 8)
coarse_mu = 8
sed_spread_enable = false                 # if true, lane assignment is not deterministic from reset
lane_fifo_depth = "unknown"               # "nearly full" rule needs this; gateware dependent [verify]

[[latency]]
key = "in2cpu"                            # input event timestamp -> value usable by the kernel CPU
src = "input"; dst = "cpu"; tier = "default"
lo_ns = 0
# hi_ns absent: no number published ("low and predictable")
prov = "vendor"
source = "ARTIQ manual (no numeric bound)"

[issue_cost]
cpu_issue = { lo_ns = 0, prov = { prov = "vendor", source = "none published; kernel-compiler dependent" } }

[branch]
class = "exposed"
default_policy = "exp"

[idle]
max_gap_variation_ns = { default = 0 }
dd_inserted_by_backend = "unknown"

[loop]
while_supported = true
```

Late-event handling (documented): sequence, collision and busy errors discard the event and append to the core log (`artiq_coremgmt log`); they do not raise exceptions. Underflow and overflow raise. The ARTIQ personality models each exactly (Section 14.4).

#### 7.3.4 `qua.toml` (finding F18)

```toml
[meta]
name = "qm_qua"
version = "0.2.0"
schema = "qtiming-contract/0.2"
personality = "qua"

[timebase]
dt_ns = "4"                               # clock cycle

[timeline]
late_policy = "compile_error"             # with strict_timing_ on; warnings otherwise

[[latency]]
key = "align.same_fem"
src = "align"; dst = "align"; tier = "same_fem"
lo_ns = 0
hi_ns = 12                                # ILLUSTRATIVE PLACEHOLDER: "a few cycles" is the only published statement
prov = "vendor"
placeholder = true
source = "QM Timing in QUA: non-deterministic align leaves 'a few cycles'; no number published"

[[latency]]
key = "align.cross_fem"
src = "align"; dst = "align"; tier = "cross_fem"
lo_ns = 0
hi_ns = 24                                # ILLUSTRATIVE PLACEHOLDER (larger than same_fem; ordering is documented, value is not)
prov = "vendor"; placeholder = true
source = "QM Timing in QUA; topology dependent: same FEM < cross-FEM < cross-chassis"

[[latency]]
key = "align.cross_chassis"
src = "align"; dst = "align"; tier = "cross_chassis"
lo_ns = 0
hi_ns = 48                                # ILLUSTRATIVE PLACEHOLDER
prov = "vendor"; placeholder = true
source = "QM Timing in QUA"

[[latency]]
key = "active_reset"
src = "measure"; dst = "branch"; tier = "default"
lo_ns = 0; hi_ns = 224
prov = "vendor"
source = "QM claim: 224 ns active reset (vendor)"

[branch]
class = "resync"
default_policy = "sync"

[personality_params.qua]
skip_implicit_align = false               # compiler flag skip-add-implicit-align
strict_timing = true                      # strict_timing_ ; "not-strict-timing" turns gap errors into warnings
# Implicit aligns: at the start of for_/while_/if_/else_/switch_ for participating elements (removable with
# skip_implicit_align); ALSO non-suppressible implicit aligns for broadcast operations and for measure()
# results that are read by another core.
```

All three QUA align entries are **placeholders** that illustrate the interface; none is a published figure. Reports print every placeholder in the assumption table with the word "placeholder", and a verdict that depends on one is at best PROVED-UNDER.

### 7.4 `Target` import (IBM)

`contract/target_import.py` (requires Qiskit) reads from `backend.target`:

1. `dt` (seconds) to `dt_ns` as an exact `Fraction` (via `Fraction(str(dt * 1e9))` rounded to a sensible decimal, then asserted to be an integer number of picoseconds).
2. Alignments: `acquire_alignment`, `pulse_alignment`, `granularity`, `min_length` into `Contract.grid` (op class to dt).
3. For every `(instruction name, qargs)` with a non-null `duration` in the `Target`, a duration in dt. `measure` and `measure_2` are separate entries (names as they appear in the Target). If an instruction has no duration, the loader does not guess: a program using it gets `E-CT-MISSING`.
4. A snapshot identifier (backend name, a hash of the imported tuple) stored in the contract and echoed in every verdict. Target-derived durations are fixed program constants (role `exact`), not uncertain latencies; the snapshot identifier is how a verdict says "valid for this calibration snapshot".
5. Offline mode: `source = "snapshot:<file>"` reads a JSON dump of the same fields so CI never needs network access.

### 7.5 Loader algorithm (`contract/loader.py`)

1. Parse with `tomllib` (Python 3.11 or newer; the `tomli` backport on 3.10) or `json`. Reject TOML floats in time fields (they must be decimal strings or integers); the loader converts with `Fraction`.
2. Validate against `ContractIn`, collecting all errors (not just the first) into `QtError` records with the TOML key path.
3. Resolve `dt_ns`: if `"from_target"`, require `[target]` and run the Target import; else parse as `Fraction`.
4. Convert by role (Section 5.1):
   - `latency lo` with role `latency_lo`, `latency hi` with role `latency_hi` (outward);
   - `commit_lead`, `min_separation` with their roles (up);
   - `deadline`, `gap_bound`, `spread_bound` from `[dep]`, `[sync]`, `[idle]` with their roles (down);
   - `[durations]` entries with role `exact` (error if not an exact multiple).
   Record a `W-CT-ROUND` warning whenever rounding changes a value.
5. Provenance: construct `Prov` for each latency; enforce Section 5.2 rules; reject a latency that has `hi` derived from msigma or pctl without an explicit value.
6. Target merge: Target values are authoritative for dt, alignments and fixed durations. A contract `[durations]` entry that conflicts with the Target is an error unless it sets `override = true` with a `reason`, in which case the verdict lists the override as an assumption.
7. Required-field check per personality (finding F31): if a required number is absent (for example ARTIQ `commit_lead`), the contract still loads, but the field is recorded in `Contract.missing` and obligations that need it return UNKNOWN naming it. The loader never fills a default that silently weakens an obligation.
8. Apply any `--assume key=lo:hi[:class]` overrides from the command line as `vendor` placeholders (flagged `placeholder=true`).
9. Freeze into an immutable `Contract` and compute SHA-256 of the canonical form (sorted keys, normalised numbers). Every verdict records the hash.

```python
def load_contract(path: str, *, target: "Target | None" = None,
                  assume: tuple[str, ...] = ()) -> Contract: ...
```

### 7.6 Policy compatibility relation (updated)

The program asks for a policy; the backend offers a class. The checker accepts the pair only if the backend can implement the request, possibly through a rewriting pass. The table is a frozen dict, unit-tested exhaustively (every cell has a test that asserts the verdict kind and the message).

| Program policy | predicated (Q1) | equalized | resync (QUA) | exposed (ARTIQ) | restricted (IBM) |
| --- | --- | --- | --- | --- | --- |
| EQ | native only when arms match **per RT instruction** (`set_cond` waits `else_time` per skipped instruction); otherwise via `EqualizeBranches` rewriting arms to the same instruction count and durations | native | via padding pass (delays before the branch up to `hi`, arms padded) | via explicit delays | via padding pass; only for a single, non-nested `if`/`else` |
| SYNC(Δ, G) | reject: cannot express a join gap bound; the RT core never resynchronises | reject | native | via explicit resync delay | native for a single `if_test` (join behaviour is a calibrated parameter) |
| EXP | reject | reject | reject (implicit aligns remove the exposed cursor) | native | reject |

"Via padding pass" means `EqualizeBranches` rewrites the program so the backend's native behaviour realises EQ. "Reject" produces a REFUTED verdict of kind `policy-incompatible`, which is the portability finding hypothesis H4 measures. For Q1, EQ is the only native policy; the change from v1 is the per-instruction condition on `set_cond` (finding F16).

### 7.7 Evidence ingestion (finding F22, decision D8)

Primary evidence for the IBM contract is the `scheduler_timing` metadata attached to jobs submitted with `dry_run=True`, which consumes no QPU time. The package side is `qtiming.evidence`; the network side (submitting jobs) lives in `experiments/ibm_dryrun/` and is not a package dependency.

```python
# qtiming/evidence/scheduler_timing.py
@dataclass(frozen=True, slots=True)
class SchedulerTiming:
    job_id: str; backend: str; runtime_version: str
    instructions: tuple[ScheduledInstr, ...]       # (name, qubits, start_dt, stop_dt, block_id)
    raw_sha256: str

def parse(path: str) -> SchedulerTiming: ...       # pydantic model with extra="allow" until the real schema is captured [verify]

# qtiming/evidence/calibrate.py
def derive_ff(st: SchedulerTiming) -> list[Observation]: ...         # measure end -> first branch instruction start, per measure/consumer pair
def derive_join(st: SchedulerTiming) -> list[Observation]: ...       # block durations vs arm durations: padding or restart?
def to_patch(obs: list[Observation]) -> ContractPatch: ...           # latency intervals with class "sched", n recorded
```

Class choice (documented decision): values read from `scheduler_timing` are class `sched`. They are exact facts about the schedule produced for those specific jobs, not a bound over all jobs, so they are not `cyc` and cannot discharge hard obligations. Across n jobs and several qubit sets the patch sets `lo = min`, `hi = max` and also records `n`, so a downstream report can print "sched, n = 40 jobs, 3 backends". If a distribution over many calibration snapshots is later collected, the entry may be promoted to `mmax(n)` with the sample count of independent snapshots. The patch is applied with `qtiming contract patch ibm_heron.toml evidence.patch.toml`, and the patched contract lists the evidence job ids in `[evidence]` so every verdict traces back to them.

Command line: `qtiming evidence ingest job_*.json --out evidence.patch.toml` and `qtiming evidence report job_*.json` (human-readable table of observed ff values and join behaviour).

---

## 8. Elaboration

Elaboration rewrites the program so that each branch's timing policy becomes explicit structure: EQ inserts a barrier, a wait of `hi` and arm padding; SYNC inserts a join with a contract cost; EXP keeps the programmer's explicit delays and marks cursor semantics; loops are unrolled, capped or summarised. After this stage no later stage needs to know what a "policy" is. It sees delays, barriers, joins and labelled alternatives.

Elaboration is not verification. It uses contract numbers (EQ waits until `hi`) to decide how much to insert, and it inserts only program statements. It never decides whether the result is safe, and it never emits constraints. Safety of the elaborated program is decided later by obligations over the dispatch graph.

Consequence (finding F9): the elaborated program is a function of the contract. Changing `hi` changes the inserted waits, so properties such as "tightening an interval cannot break a proof" do not hold across elaborations. They hold only for a fixed elaborated program (Section 16.2).

### 8.1 Elaboration judgement and environment

```python
@dataclass(frozen=True, slots=True)
class Env:
    """Abstract state during elaboration."""
    valid: Mapping[Prop, ValidInfo]        # for each bit proposition: its Measure node, tier, latency key
    ready: Mapping[str, Interval]          # per resource: ready time relative to the program start (dt interval, hull)
    iter_path: tuple[int, ...]             # unrolling path, forms the "#i3" suffix of propositions
    var_subst: Mapping[str, Expr]          # real-time variable substitution (Section 6.3)

@dataclass(frozen=True, slots=True)
class Out:
    stmt: Stmt                             # elaborated statement
    dur: Mapping[str, Interval]            # per-resource duration interval of the statement
    env: Env
    missing: frozenset[str]                # contract keys needed but unbounded (-> UNKNOWN for dependants)

def elab(stmt: Stmt, env: Env, ctx: "ElabCtx") -> Out: ...
```

`ctx` carries the contract, the personality, the unroll limit, and a `NodeFactory` that creates synthesised nodes with fresh `nid` and `origin_nid`. The per-resource duration interval replaces v1's single interval: arms of an `if` can occupy different resources for different times, and EQ has to equalise per resource.

Statement-level rules that do not depend on policy (gate, delay, barrier, measure, reset, seq, assign) keep the node and add its duration to `dur` and to `ready`. `Measure` registers `valid[prop] = ValidInfo(node=nid, tier=..., latency_key=...)` in the environment.

### 8.2 EQ (equalise)

Idea. The timeline after the branch must not depend on the outcome or on the realised latency. The elaborator

1. synchronises the measuring qubit(s) with all qubits touched by either arm using a `Barrier`, so the wait reference is the measurement's end;
2. delays every arm resource by the worst-case latency `hi` of the condition's operands to that consumer's tier;
3. pads both arms to the same duration on every resource.

```python
def elab_if_eq(node: If, env: Env, ctx: ElabCtx) -> Out:
    ops = env.cond_operands(node.cond)                       # list[ValidInfo] for the derived proposition
    then_o = elab(node.then_, env, ctx)
    else_o = elab(node.else_ or ctx.empty(node), env, ctx)
    res = sorted(set(then_o.dur) | set(else_o.dur))          # resources touched by either arm
    # 1. fixed-duration arms only: EQ cannot equalise a variable-length arm
    for r in res:
        for o in (then_o, else_o):
            iv = o.dur.get(r, Interval(0, 0))
            if iv.hi is None or iv.lo != iv.hi:
                raise QtError("E-ELAB-EQ-VARIABLE-ARM", f"EQ arm has variable duration on {r}",
                              node.loc, hint="use policy sync or exp, or make the arm fixed-length")
    # 2. wait = worst-case latency across all operands for the consumer tier on these resources
    missing: set[str] = set()
    w = 0
    for vi in ops:
        lat = ctx.contract.latency(src=vi.src, dst="branch", tier=ctx.tier_for(vi, res))
        if lat.iv.hi is None:
            missing.add(lat.key)
        else:
            w = max(w, lat.iv.hi)
    d = {r: max(then_o.dur.get(r, ZERO).hi, else_o.dur.get(r, ZERO).hi) for r in res}
    meas_res = {vi.resource for vi in ops}
    def pad(arm: Out) -> Stmt:
        extra = [ctx.delay(r, d[r] - arm.dur.get(r, ZERO).hi, synth="eq-pad", origin=node.nid)
                 for r in res if d[r] > arm.dur.get(r, ZERO).hi]
        return ctx.seq([arm.stmt, *extra])
    prefix = [ctx.barrier(sorted(set(res) | meas_res), synth="eq-sync", origin=node.nid),
              *( [ctx.delay(r, w, synth="eq-wait", origin=node.nid) for r in res] if w else [] )]
    out_stmt = ctx.seq([*prefix, ctx.if_(node.cond, pad(then_o), pad(else_o), policy=EQ, origin=node.nid)])
    dur = {r: Interval(w + d[r], w + d[r]) for r in res}      # outcome- and latency-independent from the barrier on
    return Out(out_stmt, dur, env.after(out_stmt, dur), frozenset(missing))
```

Synthesised delays are marked `declared=True` (exempt from O4a) and carry the tag `synth`. They are real program statements: `EqualizeBranches` re-emits them as Qiskit `delay` instructions.

What the elaboration guarantees and what it does not:

- It guarantees the arms have equal per-resource duration and that each arm resource waits until at least `hi` after the measurement end. It does not guarantee that the result has arrived by then: that is the **no-stall obligation O2b**, checked later. If the contract's `hi` is too small, or the measurement's own tier is wrong, O2b fails.
- The idle cost of EQ is `(w - theta) + (d - d_taken)` per resource, with `theta` the realised latency. It is not a constraint; the verdict reports its maximum as `policy_cost` (Section 13.2) for hypothesis H5.
- If any `hi` is unbounded the wait cannot be computed. Elaboration returns the key in `Out.missing`, uses `w = lo` as a placeholder so graph construction can continue, and the verdict for every obligation depending on that latency is UNKNOWN naming the key.

### 8.3 SYNC(Δ, G) (synchronise at join)

Each arm runs as soon as the result arrives. A runtime join resynchronises all resources afterwards, at a cost taken from the contract.

```python
def elab_if_sync(node: If, env: Env, ctx: ElabCtx) -> Out:
    then_o = elab(node.then_, env, ctx); else_o = elab(node.else_ or ctx.empty(node), env, ctx)
    res = sorted(set(then_o.dur) | set(else_o.dur))
    cost = ctx.contract.sync_cost(n=len(res), tier=ctx.join_tier(res))      # a Latency (contingent), may be unbounded
    join = ctx.join(res, cost_key=cost.key, origin=node.nid)                # node kind "join"; dispatch adds contingent weight
    stmt = ctx.seq([ctx.if_(node.cond, then_o.stmt, else_o.stmt, policy=node.policy, origin=node.nid), join])
    ...
```

- No padding, no wait. Arms start at `max(resource ready, valid(cond))` (the dispatch rule of the personality).
- The `Join` statement is a full barrier over every resource touched by either arm. Its dispatch time is `max over resources of arm end`, plus the join cost as a contingent latency `lambda` in `[lo, hi]`.
- The policy's `Δ` and `G` become **obligations** (O7 and per-resource gap variation), not constraints. If the contract has no `[sync]` cost, `lambda` is unbounded and every obligation depending on it is UNKNOWN naming the missing field. That tells vendors which number to publish.
- Personalities that perform their own join (IBM's block model, QUA's implicit align) take the join behaviour from the personality rather than inserting a `Join`: the policy is still `sync`, but `ctx.join` returns an empty statement and the personality dispatch supplies the edges.

### 8.4 EXP (exposed timeline)

The ARTIQ model. The programmer owns the cursor.

- No padding, no wait, no join. The elaborator keeps the explicit `Delay` statements as written; they are how the programmer restores slack.
- It marks each timed-output statement (`Gate`, `Measure` gate-window, TTL pulse) with `commit=True`. The graph builder turns every such statement into a `commit` node whose stamped time comes from the cursor chain (Section 9.4.3), and the obligation generator emits **O1** for each.
- After a conditional whose arms advance the cursor differently, the cursor value depends on the outcome. That is legal under EXP (safe-only guarantee). The label-guarded cursor edges express it.

### 8.5 Q1 `set_cond`: per-instruction condition modelling (finding F16)

On Q1 the condition is evaluated before **every** real-time instruction. If false, the RT core waits `else_time` ns instead of executing that instruction. A "then" arm of `n` conditional RT instructions with durations `a_1..a_n`, executed under condition `p`, therefore contributes

- `sum(a_i)` when `p` is true;
- `n * else_time` when `p` is false.

The "else" arm is a second conditional block under the inverted condition (the Q1 operators include NOR, NAND and XNOR; **[verify]**), with its own `else_time`.

```python
def elab_q1_setcond(node: If, env: Env, ctx: ElabCtx) -> Out:
    A = ctx.rt_instrs(node.then_)           # list[(nid, dur_dt)] conditional RT instructions of the then-arm
    B = ctx.rt_instrs(node.else_)           # same for the else arm
    eA, eB = ctx.q1_else_times(node)        # chosen by program or defaulted: else_time per block
    # Per-instruction time on each outcome:
    #   p true : A_i takes a_i ; B_j is skipped -> eB per instruction
    #   p false: A_i is skipped -> eA per instruction ; B_j takes b_j
    t_true  = sum(d for _, d in A) + len(B) * eB
    t_false = len(A) * eA + sum(d for _, d in B)
    ...
    return Out(... dur={"rt": Interval(min(t_true, t_false), max(t_true, t_false))} ...)
```

Consequences:

- The elaborator does not pad. It reports the **per-instruction** timeline as label-guarded dispatch edges (Section 9.4.2). The two totals `t_true` and `t_false` are equal only when instruction counts and durations align. When they do not, the EQ-determinism obligation (O7 with `Δ = 0`) fails with a counterexample naming the two outcomes and the difference.
- `EqualizeBranches` for Q1 does not insert one big `wait`. It searches for a rewriting that makes `t_true == t_false` while keeping `else_time` per instruction: adding dummy RT instructions (a `wait` of the shorter arm's duration) so that instruction counts match, and choosing `eA`, `eB` as the common per-instruction duration where all instructions in the corresponding arm have equal duration. If no such rewriting exists (for example one arm has a single 100 ns play and the other has three 40 ns plays and counts cannot be matched without splitting an atomic instruction), the pass reports `E-ELAB-Q1-NOT-EQUALISABLE` instead of producing something incorrect.
- Why it matters (portability finding): a program equalised by total duration on another backend can diverge on Q1. That is a concrete H4 instance.

### 8.6 Loops

| Construct | Strategy | Threshold |
| --- | --- | --- |
| `for i in [0, n)`, `n <= L` | unroll; each copy gets fresh proposition names (`c0@m17#i3`) | `L = 64` default, configurable |
| `for`, `n > L` | **summarise by periodic cut**: check one iteration as a window whose end is a full join (Section 9.7); if all window-cut conditions hold, total duration is `n` times the window's duration interval; otherwise UNKNOWN naming the failed condition | |
| `while` with cap `N`, `N <= L` | unroll to `N` iterations; iteration `j` exists only under label "no success in iterations `< j`"; after iteration `N-1` the exhaust handler runs under label "no success in any iteration" | |
| `while`, `N > L` | summarise the same way (one iteration window plus exhaust) | |
| RUS with `timing.pmin` | add the three-part verdict (Section 13.5) | |

Fresh proposition names per iteration are essential. Without them a solver would believe iteration 3's outcome is known during iteration 1, and a derived condition in iteration 3 would wrongly share a proposition with iteration 1.

```python
def unroll_for(node: For, env: Env, ctx: ElabCtx) -> Out:
    outs, e = [], env
    for i in range(node.n):
        e_i = e.with_iter(i).bind(node.var, EConst(i))
        o = elab(node.body, e_i, ctx)
        outs.append(o); e = o.env.pop_iter()
    return Out(ctx.seq([o.stmt for o in outs]), sum_dur(outs), e, union_missing(outs))
```

A capped `while` is analogous. Iteration `j`'s condition is the derived proposition `"cond@w#ij"` over the measurement of iteration `j`, and its label is the conjunction of the negations of earlier successes.

### 8.7 Blocking calls and deadlines

- `Call(blocking=True)` is bound by `timing.call` to a `[domain_call]` entry with WCET and RTT. If either is unbounded the call's latency is unbounded and dependants are UNKNOWN. Elaboration records the call; the dispatch adds a `call` node after the classical issue resource's previous node, a contingent latency `WCET + RTT` (a single variable with interval `[wcet_lo + rtt_lo, wcet_hi + rtt_hi]`, provenance the weaker of the two), and orders later classical operations after the call end.
- `Within(D, anchor, body)` becomes an **obligation O3**, not an edge: for every resource that the body uses, the first operation of the body must start at most `D` after `valid(anchor)`. The elaborator only records the body's first operations per resource (`first_ops: dict[resource, nid]`) in the elaborated program's metadata (`mode = "all_started"` default; `timing.within <dur> <bit> mode=first` selects the earliest only).

### 8.8 Outputs of elaboration

`ElabProgram` is itself valid TQ, so it can be printed back to OpenQASM 3 for inspection (`qtiming explain --elaborated`). The `EqualizeBranches` Qiskit pass uses exactly this: it runs EQ elaboration and re-emits a circuit with explicit `delay` and `barrier` instructions, so downstream passes such as dynamical-decoupling insertion see fixed windows.

```python
@dataclass(frozen=True, slots=True)
class ElabProgram:
    body: Stmt
    derived: tuple[Derived, ...]           # derived propositions with expressions
    first_ops: Mapping[int, Mapping[str, int]]   # within nid -> resource -> first-op nid
    missing: frozenset[str]                # contract keys needed but unbounded
    policy_map: Mapping[int, Policy]       # effective policy per branch / loop nid
    contract_sha256: str
```

### 8.9 Idempotence

Elaborating an already-elaborated program changes nothing: synthesised statements carry `synth` tags and elaboration treats them as ordinary delays and barriers, with no branch left to rewrite (every `If` has `policy` set to the elaborated marker `EQ_ELAB` or its SYNC/EXP counterpart). A property test checks it (Section 16.2).

---

## 9. The labelled timed event graph (LTEG) and dispatch semantics

The LTEG is the single intermediate representation every verification tier reads. Its nodes are time-points; its **dispatch edges** define when each node happens; its contingent latency variables model the uncertainty nature chooses; its labels say under which outcomes a node or edge exists. Obligations (Section 10) are separate objects that refer to nodes and are only checked, never used to place events.

### 9.1 Dispatch semantics

For a fixed outcome assignment ω (values of all bit propositions) and a fixed latency realisation θ (a real number `theta_i` in `[lo_i, hi_i]` for each contingent latency variable), define node existence and time recursively over the acyclic graph:

```text
exists(v)  iff  omega satisfies label(v)  and  v is the origin or some in-edge of v is active
active(e)  iff  omega satisfies label(e)  and  exists(src(e))
t(origin)  = 0
t(v)       = snap_v( max over active in-edges e of v of ( t(src(e)) + w(e) ) ),     for every existing v != origin
```

where an edge weight `w(e)` is either an integer constant (dt) or a latency variable `theta_i`, and `snap_v` is the identity unless the personality declares a grid for `v` (`snap = g`), in which case `snap_v(x) = g * ceil(x / g)` (hardware that starts an event at the next cycle boundary, such as ARTIQ coarse timestamps). This is the **dispatch time** of `v`: each event happens as soon as its last active predecessor allows, which is what the hardware does for resource ordering, joins, and result-triggered branches. It is deliberately a maximum, not a set of difference constraints (finding F2).

Properties used later:

- The dispatch time function is monotone non-decreasing in every `theta_i` and in every constant weight.
- A node's time is an affine function of the `theta` variables on each branch of the max; Tier 1 keeps the max of affine terms.
- Two nodes with the same dominator and rigid (single-in-edge) paths between them have a difference that is independent of everything above the dominator; Tier 1 exploits this.

### 9.2 Data structures (`graph/lteg.py`)

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Union
from qtiming.core.labels import Label, Prop
from qtiming.core.provenance import Prov

NodeKind = Literal["origin", "start", "end", "valid", "join", "issue", "exec", "cursor", "commit", "call", "align"]

@dataclass(frozen=True, slots=True)
class LatVar:
    """One contingent latency OCCURRENCE (fresh per unrolled iteration and per consumer tier)."""
    id: int
    key: str                    # contract key, e.g. "ff.default"
    occurrence: str             # e.g. "ff.default@m17#i0->n42"
    lo: int                     # dt
    hi: int | None              # dt; None = unbounded
    prov: Prov

Weight = Union[int, LatVar]

@dataclass(frozen=True, slots=True)
class Node:
    id: int
    kind: NodeKind
    nid: int                    # origin AST node (for reports)
    resource: str | None        # "q3", "rt:s0", "cpu", "elem:resonator", "cursor"
    label: Label                # outcomes under which this point exists
    obs: Prop | None = None     # proposition observed here (valid-points)
    snap: int | None = None     # grid g in dt: t = g * ceil(max / g); None = no snapping

@dataclass(frozen=True, slots=True)
class DEdge:
    src: int
    dst: int
    w: Weight
    label: Label                # outcomes under which the edge is active (in addition to src existing)
    tag: str                    # rule that created it, e.g. "ibm.arm-start", "q1.rt-chain"

class LTEG:
    nodes: list[Node]
    edges: list[DEdge]
    lats: list[LatVar]
    derived: dict[Prop, "Derived"]
    origin: int
    in_edges: dict[int, list[int]]          # node id -> edge indices
    out_edges: dict[int, list[int]]
    topo: list[int]                         # cached topological order
    meta: "GraphMeta"                       # personality, contract hash, window id, cut info
```

Storage is plain arrays plus index maps. A typical benchmark has a few hundred nodes; arrays are faster and simpler to debug than a general graph library (`networkx` is used only for visualisation).

### 9.3 Construction rules common to all personalities

| Program element | Nodes | Dispatch edges |
| --- | --- | --- |
| gate `U` on resources `R`, duration `d` | `start_U`, `end_U` | `end(prev on r) -> start_U` weight 0 for each `r in R`; `start_U -> end_U` weight `d` |
| delay `d` on `R` | `start`, `end` | as a gate with duration `d`, `declared=True` |
| barrier over `R` | `join` | `end(prev on r) -> join` weight 0 for each `r`; each resource's next op depends on `join` |
| measurement into `c` | `start_M`, `end_M`, `valid_c` (obs = `c@m#i`) | gate rule; `end_M -> valid_c` weight a fresh `LatVar` for the tier |
| derived condition | `valid_cond` (obs = `cond@n#i`) | `valid_operand -> valid_cond` weight 0 for each operand: the condition is observed at the last operand |
| guarded statement (inside an `if` arm) | all nodes labelled `label ∧ literal` | edges labelled likewise |
| join after `if` | `join` (label of the enclosing context) | `arm_end(r) -> join` weight 0, active only under the arm's label; one edge per arm and resource |
| declared delay | as delay | the node is marked declared (exempt from O4a) |
| blocking call | `call_start`, `call_end` | `call_start -> call_end` weight a `LatVar` (WCET plus RTT); later classical ops depend on `call_end` |

Personalities add or replace rules for the elements where hardware behaviour differs (branch start, join, commit, cursor, queue). The common rules fix the resource-ordering behaviour: an operation on a resource starts when the previous operation on that resource ends, and an operation on several resources starts when all have finished. Those are max edges in the dispatch semantics, not `>=` obligations.

### 9.4 Per-personality dispatch rules

Each personality is specified in `docs/personality-spec/<name>.md`; the table below is the normative summary the graph builder and the executor both implement independently. Parameters that are not documented are named, with their default and provenance, so no behaviour is a hidden guess.

#### 9.4.1 IBM (restricted, block model)

| Element | Dispatch rule | Parameter |
| --- | --- | --- |
| gate, delay, measure | common rules; measure variant (`std`, `mid`) selects the `Target` duration | |
| feedforward | `end_M -> valid_c` weight `theta_ff` in `[lo, hi]` of latency `ff` for the tier | contract `ff.*` |
| `if` block start | one node `bstart`; edges `valid_cond -> bstart` weight 0 and `end(prev on r) -> bstart` weight 0 for every resource `r` of either arm (`block_start = "all_resources"`); the whole block starts when the result is valid AND every arm resource is ready | `block_start` in `{all_resources, per_resource}`, default `all_resources`, `vendor` |
| arm execution | per-resource chains from `bstart` under the arm's label | |
| block end (pad) | `join_behavior = "pad_to_longest_block"`: an unlabelled edge `bstart -> bend` of weight `Dmax = max(Dthen, Delse)` (arm duration = the longest per-resource chain), plus arm-end edges; so `t(bend) = t(bstart) + Dmax` for every outcome | `join_behavior`, default `pad_to_longest_block`, `vendor`, documented only for the old fast-path stack (qiskit-ibm-runtime 0.39 and earlier) |
| block end (restart) | `join_behavior = "restart_at_join"`: only arm-end edges into `bend`, so `t(bend)` is the arm's actual end (outcome dependent) | calibrated from `scheduler_timing` (Section 18) |
| late events | none at run time; violations are job-validation failures (lint) | |
| O1 | not applicable (no exposed commit model) | |

Under EQ elaboration (barrier plus wait of `hi`) the `ready` edges dominate: `t(bstart) = t(barrier) + hi` for every `theta_ff <= hi`, so the block start does not depend on `theta_ff`. Under SYNC no wait is inserted and `t(bstart) = t(valid_cond)` varies with `theta_ff`; obligation O7 then bounds that variation.

#### 9.4.2 Q1 (predicated, RT queue)

Each sequencer has two resources: the classical Q1 core `q1:s` and the real-time core `rt:s`.

| Element | Dispatch rule |
| --- | --- |
| Q1-core instruction `i` | issue chain: `issue_i` with edge `issue_{i-1} -> issue_i` weight `cost_i` from `[issue_cost]` (taken or not taken for jumps; deprecated compare-and-jump forms cost one extra ALU instruction) |
| RT instruction `k` (play, acquire, wait, upd_param, ...) | `exec_k` on `rt:s`; rigid chain `exec_{k-1} -> exec_k` weight `dur_{k-1}`; the RT core does **not** wait for the Q1 core |
| queue back-pressure | edge `exec_{k-32} -> issue_k` weight 0 (the Q1 core stalls when 32 RT instructions are pending): a dispatch edge, because the hardware stalls rather than fails |
| `set_cond` conditional RT instruction `k` | two edges guarded by the condition literal: executed (`exec_{k-1} -> exec_k` weight `dur_{k-1}` under the label where instruction `k-1` ran) and skipped (weight `else_time` where it was skipped): the chain weight out of an instruction depends on whether that instruction was executed or skipped |
| acquisition result | `end_acq -> valid_c` weight `theta_net` in `[212, 239] ns` (`trigger.network`), plus `path.opip.base` and the RTP adder where the path requires them |
| condition evaluation | the RT core evaluates the condition at `exec_k`; no wait for `valid_c`. This creates obligation **O2a**: `exec_k - valid_c >= 0` for every conditional instruction |
| sequencer join (`wait_sync`) | a `join` node over the participating sequencers' RT cores; issue chains join at their own sync point |
| sequencer halt | not a dispatch edge: underflow is obligation O1: `exec_k - issue_k >= 0`, where `issue_k` is the time instruction `k` becomes available to the RT core (end of its Q1 issue) |

In words: the RT timeline is rigid and the checker verifies that the Q1 core always stays ahead of it, and that the trigger-network result is always valid when the RT core consults it.

#### 9.4.3 ARTIQ (exposed cursor)

Two timelines: the **cursor** (`now_mu`, the timestamp stamped on outgoing events) and the **CPU wall clock** (when the kernel code actually runs).

| Element | Dispatch rule |
| --- | --- |
| `delay(d)` / `delay_mu(d)` | cursor edge `cursor_prev -> cursor_new` weight `d` |
| output event `e` (TTL pulse, DDS set, ...) | `commit_e` node on the cursor chain: `t(commit_e)` = stamped timestamp `T_e`; for pulses with duration, the end event is on the same chain |
| `with parallel` / `with sequential` | parallel: each branch starts at the same cursor value; the join node is `max` of branch ends (cursor chain) |
| CPU execution | wall-clock chain: `cpu_{j-1} -> cpu_j` weight `cost_j` (`issue_cost.cpu_issue`) |
| issuing event `e` | `issue_e` on the CPU chain at the point where the kernel executes the statement |
| input read (`count`, `timestamp_mu`, `gate_*`) | the gate window advances the cursor by its length (cursor edge). The CPU receives the value at `cpu_after = max(cpu_before + cost, T_gate_end + theta_in2cpu)`: two in-edges, so the CPU blocks until the event data is available. The cursor is not advanced to the wall clock: **negative slack** arises naturally |
| `at_mu(t)` | cursor jumps to `t`: an edge from origin with weight `t` |
| late events | none in dispatch; they are obligations: O1 underflow (`T_e - issue_e >= commit_lead`), O5 sequence, collision, busy |

Under the fixed dispatch, `T_e` does **not** move when the CPU is late. That is exactly why ARTIQ underflows, and why a free-time-point model would be unsound (Appendix A).

#### 9.4.4 QUA (resync, implicit aligns)

Resources are quantum elements (and the FEM or core they live on).

| Element | Dispatch rule |
| --- | --- |
| `play`, `wait`, `measure` on element `e` | common rules on resource `elem:e` |
| deterministic `align(e1..en)` | `join` node, `end(prev on e_i) -> join` weight 0; no extra latency (compiled into waits) |
| non-deterministic `align` or implicit align | as above, plus an `align` node after the join with weight `theta_align` in the tier's interval (`align.same_fem`, `align.cross_fem`, `align.cross_chassis`): the unpublished "few cycles" gap |
| implicit align at the start of `for_`, `while_`, `if_`, `else_`, `switch_` | added for participating elements unless `skip_implicit_align`; deterministic or non-deterministic per whether the preceding durations are static |
| implicit align for broadcast ops and for `measure()` results read by another core | always added (not suppressible) with tier chosen by the topology |
| conditional `play` | equal-length wait on the false path (EQ native for a single operation) |
| `if_`/`else_` with different contents | arms run per element; **no implicit join after the block**; element end times become label dependent; the user must `align` afterwards |
| `strict_timing_` | a non-deterministic align with non-zero uncertainty is a compile error (lint `E-LINT-QUA-STRICT`); with `not-strict-timing` it is a warning and the gap stays |

### 9.5 Invariants checked after construction (`graph/invariants.py`)

| ID | Invariant | On violation |
| --- | --- | --- |
| I1 | Acyclic: the edge set has a topological order | `E-GRAPH-CYCLE`: builder bug (or an unrolled loop mistake) |
| I2 | Label well-formedness: `label(e)` implies `label(src(e))` and `label(dst(e))` (literal-subset check) | `E-GRAPH-LABEL` |
| I3 | Definedness: for every node `v` and every outcome satisfying `label(v)`, at least one in-edge is active (checked by SAT over the node's labels, or structurally) | `E-GRAPH-LABEL` |
| I4 | Causality: every label-guarded edge `e` mentioning proposition `p` is either (a) reactive: `valid(p)` is an ancestor of `src(e)`, so the decision cannot precede the observation, or (b) predicated: the builder has registered an **O2a** obligation `t(src(e)) - t(valid(p)) >= 0`. A guarded edge satisfying neither is a builder error | `E-GRAPH-CAUSAL` |
| I5 | Each `LatVar` is used by exactly one edge occurrence (fresh per iteration and tier) | `E-GRAPH-LATVAR` |
| I6 | All constant weights are integer dt; every proposition appearing in a label is either a bit proposition with a `valid` node or a `Derived` entry | `E-GRAPH-PROP` |
| I7 | Window cut rules (Section 9.7) hold for every cut | `E-GRAPH-CUT` |

I4 is condition (iii) of the DMO definition ("causality") expressed structurally. Reactive personalities satisfy it by construction; predicated ones (Q1) satisfy it only via the O2a obligation, which is how the checker catches stale reads.

### 9.6 Size

Each gate adds two nodes, each measurement three, each unrolled iteration a copy of its body. A 50-operation circuit with 6 measurements has about 120 nodes. Edges are about twice the nodes. Per-obligation verification cost is controlled by restricting to the **cone of influence**: the ancestors of the obligation's nodes, plus the nodes whose labels are needed (Section 11.7).

### 9.7 Windowing and cut rules (finding F26)

QEC and RUS programs are long and repetitive. The builder supports **windows**: the program is split at **cuts**, each window is verified separately, and the verdicts are combined.

A cut is legal at node `J` only if all of the following hold. The builder checks them and refuses to cut otherwise (`E-GRAPH-CUT`).

1. **Full join.** `J` is a join node with an in-edge from the last node of every resource that is live after the cut, so every later node's time is determined by `t(J)` and by later constants and latency variables only.
2. **Dominator cut.** Every dispatch edge entering a node after `J` either starts at `J` or at another node after `J`. No dispatch edge crosses the cut from before `J` to after `J` except through `J`.
3. **No obligation crosses the cut.** Every obligation has all its nodes on the same side. Cross-cut obligations (a `within` that spans rounds, O4a over the cut, a lane-ordering constraint across the cut, O1 where the classical issue chain crosses the cut) block the cut or are re-expressed relative to `J` when that is exact.
4. **Canonical personality state at the cut.** The state the personality carries across must be summarised by `t(J)`: Q1's RT queue content (cut only after the queue is known drained, or carry a summary node), ARTIQ's SED lane state (drained or carried explicitly), classical stream position. If the state is not canonical the cut is refused.
5. **Grid residue.** For O8 the absolute time of `J` modulo each grid must be known; the window summary carries `t(J) mod g` (usually 0 when `J` is aligned by construction).

Window analysis: window `k` is verified with `J_k` as origin (time 0). Because every window obligation is a function of differences of node times within the window and all of those differences are independent of `t(J_k)` (dispatch is shift invariant), the verdict for window `k` holds for every start time. The program verdict is the conjunction of window verdicts, with assumptions unioned and the maximum over windows reported as the margin. The duration interval of each window (as hull over `(ω, θ)`) is reported so total duration can be summed. Soundness of this composition is theorem target T4 (Section 15). A flag `--no-window` verifies the whole program for comparison, and the differential tests compare the two on every benchmark small enough for both (Section 16.5).

---

## 10. Obligations

An obligation is a small, named, independently checkable claim about the LTEG. It points at nodes, carries the label under which it applies, lists the latency variables it depends on, and states whether it is hard. Obligations are checked against the fixed dispatch of Section 9.1. They are never added to the graph as scheduling constraints (principle 8). Generating them one by one, instead of as one giant query, gives precise messages and lets the dispatcher route cheap obligations to cheap tiers.

### 10.1 Model (`oblig/model.py`)

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Union
from qtiming.core.labels import Label
from qtiming.core.provenance import Assumption

Code = Literal["O1", "O2a", "O2b", "O3", "O4", "O4a", "O5", "O6", "O7", "O8", "O9"]

@dataclass(frozen=True, slots=True)
class Diff:                 # t[x] - t[y]  (<= | >=)  c       (c in dt)
    x: int; y: int; op: Literal["<=", ">="]; c: int

@dataclass(frozen=True, slots=True)
class Variation:            # max - min over all executions where the guard holds, of (t[x] - t[y]), is <= bound
    x: int; y: int; bound: int

@dataclass(frozen=True, slots=True)
class Mod:                  # t[x] is a multiple of g, plus residue
    x: int; g: int; residue: int = 0

@dataclass(frozen=True, slots=True)
class Events:               # O5: a concrete event list in SUBMISSION order, checked by the personality's rules
    kind: Literal["sed", "collision", "busy", "net_occupancy", "count"]
    items: tuple[tuple[int, str, int], ...]      # (commit node id, channel, issue node id)
    params: tuple[tuple[str, int], ...]

Check = Union[Diff, Variation, Mod, Events]

@dataclass(frozen=True, slots=True)
class Obligation:
    code: Code
    nid: int                          # origin AST node it protects (for reports)
    guard: Label                      # outcomes under which it must hold
    check: Check
    deps: frozenset[int]              # LatVar ids in the cone of influence
    assumptions: frozenset[Assumption]
    hard: bool                        # discharged only by cyc/cert evidence
    severity: Literal["safety", "advisory"]
    message: str
```

Two orthogonal flags:

- `severity = "safety"` failures make the verdict REFUTED. `"advisory"` failures (O4a only, plus lint warnings) are reported as findings and never change the verdict.
- `hard` controls evidence: a hard obligation proved under any assumption weaker than `cyc` is only PROVED-UNDER (Section 5.2).

### 10.2 The obligation table

| Code | Plain meaning | Formal check over the fixed dispatch | Tier | Provenance handling | Severity |
| --- | --- | --- | --- | --- | --- |
| O1 | **No underflow.** Every timed output is committed early enough | for each commit node `e` with issue node `i_e`: `t(e) - t(i_e) >= L` where `L = commit_lead` (dt, rounded up); Q1: `t(exec_k) - t(issue_k) >= 0` | 0, 1, 2 | the classical issue chain's latencies and `issue_cost` classes are assumptions | safety |
| O2a | **Result valid when consulted** (predicated personalities, stale-read safety) | for each guarded edge registered by invariant I4(b): `t(src) - t(valid(p)) >= 0` | 0, 1, 2 | the feedback latency `hi` | safety |
| O2b | **No stall** (EQ determinism): the branch is not delayed by the arrival of the result | `t(bready) - t(valid(p)) >= 0` where `bready` is the resource-ready node of the arm start | 1, 2 | feedback latency `hi` | safety (EQ branches only) |
| O3 | **Deadline** | for each `within[D]` and each resource `r` in its body: `t(first_r) - t(valid(anchor)) <= D` | 1, 2 | feedback latency; hard if the box is `timing.hard` | safety |
| O4 | **No unplanned gap.** A gap on a resource whose length varies with (ω, θ) breaks compile-time DD and phase tracking | for each consecutive op pair `(p, n)` on resource `r` with `g = t(start_n) - t(end_p)`: `Variation(start_n, end_p, G_r)`, i.e. `max g - min g <= G_r` over executions where both exist | 1, 2 (two-copy) | all latencies in the cone | safety |
| O4a | **Absolute idle bound** (optional) | `t(start_n) - t(end_p) <= G_abs` unless the gap is covered by a declared delay | 0, 1, 2 | | advisory, off by default |
| O5 | **Capacity** | personality rules, Section 10.5 | 0 or 2 | | safety |
| O6 | **Blocking call fits** | named group: for every committed event or branch after a blocking call `c`, the O1 and O2a instances that include the call's contingent latency; the parametric statement is `slack >= WCET_hi + RTT_hi` | 1, 2 | WCET and RTT intervals | safety |
| O7 | **Join determinism** | for each branch join `J` with reference node `ref` (the barrier before the branch): `Variation(J, ref, Δ_eff)` with `Δ_eff = 0` for EQ, `Δ` for SYNC, none for EXP; for SYNC also per-resource `Variation(join, end_r, G)` | 1, 2 | join cost `lambda` interval | safety |
| O8 | **Grid** | for each event whose time is program-fixed (no latency variable in its cone) and has no `snap`: `Mod(x, g_class)`; events with `snap` satisfy it by construction | 0, 2 | grid values from the Target or contract | safety |
| O9 | **Loops** | capped loop: worst-case duration `N*u + u_exhaust`; periodic-cut loops: the window cut rules hold for the iteration; slack after an iteration `>=` slack before (the loop-carried O1 margin does not shrink) | 0, 1, 2 on one iteration window | | safety |

O2a, O2b, O3, O4, O7 are the obligations that express the DMO definition: O2b and O7 are latency-independence ((ii) in the DMO definition), O2a is causality ((iii)), and every obligation together is safety ((i)).

### 10.3 Why O4 is a variation check (finding F6)

v1 used `G = 0` as the default and flagged every non-zero idle. A non-zero gap that is the same in every execution is harmless for compile-time dynamical decoupling and for phase tracking: the compiler knows its length. What breaks those tools is a gap whose length depends on data. O4 therefore asks that `max g - min g` over all executions be at most `G_r` (default 0). A stall caused by a late feedback result is a varying gap, so O4 also flags EQ programs whose wait is too short, independently of O2b. Absolute idle length is the optional advisory O4a.

The two-copy encoding in Tier 2 (Section 11.5) makes the quantifier over executions explicit: there exist `(ω, θ)` and `(ω', θ')` with `g(ω, θ) - g(ω', θ') > G_r`.

### 10.4 Hard versus advisory evidence

An obligation is hard if the contract marks it (for example a fault-tolerance reaction deadline) or the box carries `timing.hard`. A hard obligation proved while resting on an assumption weaker than `cyc` gets the result PROVED-UNDER and the report names the assumption that blocked PROVED. A non-hard obligation proved under assumptions is also PROVED-UNDER (the common case); PROVED requires an empty assumption set or only `cyc`/`cert` assumptions.

### 10.5 O5 capacity in detail (finding F17)

O5 differs by personality. All of it is checked on **committed events in submission order**, because that is how the hardware sees them.

#### ARTIQ

Quantities: `lanes` (default 8, gateware `sed_lanes`), `coarse_mu` (typically 8 mu, 125 MHz). For an event stamped `T` (mu): `coarse = T // 8`, `fine = T % 8`. `now` is the wall-clock coarse time at submission, from the issue node.

Rules (documented behaviour):

1. **Sequence error.** Coarse timestamps must strictly increase within a lane. If the new event's timestamp is not greater than the previous one on the current lane (or the lane is nearly full), the SED moves to the next lane. If every lane holds an event with time at or after the new one, the event is dropped with a sequence error. The assignment is deterministic from reset unless `sed_spread_enable` is set.
2. **Collision.** Same channel, same coarse timestamp, different fine timestamp (or the same timestamp without replace behaviour): the later event is discarded.
3. **Busy.** The channel is still executing a multi-cycle event: the event is discarded.
4. Sequence, collision and busy errors **discard the event and log** (visible through `artiq_coremgmt log`); they raise nothing. Underflow and overflow raise.

Reference model (shared by Tier 0 evaluation and by the executor's own independent copy; the two are written separately and tested against the same golden cases):

```python
def sed_simulate(events, lanes=8, spread=False):
    """events: list of (submit_coarse_now, channel, T_mu, busy_mu) in SUBMISSION order.
    Returns list of (index, kind) for dropped events. PARAMETERS NOT PUBLISHED (nearly-full rule, FIFO depth)
    are exposed as contract fields; unknown ones are ignored and the verdict lists them as assumptions."""
    top = [None] * lanes; cur = 0; drops = []
    by_slot = {}                           # (channel, coarse) -> fine, for collision
    busy_until = {}                        # channel -> mu
    for k, (now_c, ch, T, busy) in enumerate(events):
        coarse, fine = divmod(T, 8)
        # lane assignment (sequence error)
        placed = False
        for step in range(lanes):
            l = (cur + step) % lanes
            pending = top[l] is not None and top[l] > now_c         # entries already executed free the lane
            if not pending or coarse > top[l]:
                top[l] = coarse; cur = l; placed = True; break
        if not placed: drops.append((k, "sequence")); continue
        if (ch, coarse) in by_slot and by_slot[(ch, coarse)] != fine:
            drops.append((k, "collision")); continue
        if T < busy_until.get(ch, -1):
            drops.append((k, "busy")); continue
        by_slot[(ch, coarse)] = fine; busy_until[ch] = T + busy
    return drops
```

Verification form: Tier 0 evaluates `sed_simulate` per scenario when the event times are program-fixed. When event times depend on latency variables, Tier 2 uses the symbolic version in `smt_o5.py`: lane tops are real variables, the current lane an integer, each step an `If` chain; the number of events is capped (default 64), above which the result is UNKNOWN. The symbolic encoding is a mechanical transcription of `sed_simulate`; a differential test compares them on random inputs (Section 16.6).

Note the correction to v1: eight events in one coarse slot is not by itself a violation; non-increasing timestamps within lanes, collisions and busy channels are.

#### Q1

- **RT queue.** The Q1 core stalls when 32 RT instructions are pending; that is a dispatch edge (Section 9.4.2), not a violation. Underflow is O1.
- **Trigger-network occupancy.** After a trigger is sent, the network is occupied until 252 ns later. A second trigger issued inside the window is a violation: `Events(kind="net_occupancy")`, check `t(trigger_2) - t(trigger_1) >= 252 ns` (rounded up) for every pair in submission order. Contract keys `trigger.network_busy`.
- **Count.** Instruction counts relevant to `set_cond` blocks are a lint (static).

#### IBM

Static counts only (no timing): instructions per qubit (26.8 M), broadcast budget. These are lint rules (Section 6.6) elevated to obligations of kind `Events(kind="count")` when the estimate can only be obtained after elaboration (unrolled loops are not allowed on IBM, so it is rare).

#### QUA

None numeric. Compile-time checks (`strict_timing_`) are lint.

### 10.6 Obligation generation (`oblig/generate.py`)

```python
def generate(g: LTEG, prog: ElabProgram, c: Contract, pers: Personality) -> list[Obligation]:
    obs: list[Obligation] = []
    obs += o1.generate(g, c, pers)              # commit nodes and issue nodes registered by the personality
    obs += o2.generate(g, prog)                 # O2a from invariant I4(b) registrations; O2b for EQ branches
    obs += o3.generate(g, prog, c)              # from prog.first_ops
    obs += o4.generate(g, c)                    # consecutive pairs per resource
    obs += o5.generate(g, c, pers)
    obs += o6.generate(g, prog, c)
    obs += o7.generate(g, prog)
    obs += o8.generate(g, c)
    obs += o9.generate(g, prog, c)
    return [with_cone(o, g) for o in obs]       # fills deps and assumptions from the cone of influence
```

`with_cone` computes the ancestors of the obligation's nodes (plus the nodes needed by labels) and collects the `LatVar` ids and the `Assumption` set from them. This is what restricts both the solver input (Section 11.7) and the verdict's assumption list to what the obligation actually used.

### 10.7 Lint (static, no solver)

| ID | Rule | Severity |
| --- | --- | --- |
| L1 | unbounded `while`; missing exhaust handler | error |
| L2 | policy incompatible with the backend class (Section 7.6) | REFUTED kind `policy-incompatible` |
| L3 | IBM restriction violations (Section 6.6) | error |
| L4 | required contract field missing (`Contract.missing`) for an obligation present in the program | UNKNOWN naming the field |
| L5 | annotation references an unknown bit, or `within` anchor never written | error |
| L6 | `timing.cut` requested where the cut rules fail | warning |
| L7 | placeholder or `vendor` latency used by a hard obligation | note |
| L8 | `Switch` on a backend without switch support | error |

---

## 11. Verification: solver tiers 0, 1 and 2

Verification decides, for each obligation, whether it holds for **every** outcome assignment ω and **every** latency realisation θ under the fixed dispatch. Three tiers: Tier 0 evaluates exactly when no latency is involved, Tier 1 proves cheaply with a sound abstraction and never refutes, Tier 2 is exact and produces counterexamples. The controllability algorithms of Section 12 are a different module and are never used here.

### 11.1 Dispatcher (`solve/dispatcher.py`)

```python
def verify(g: LTEG, o: Obligation, cfg: SolveCfg) -> Result:
    cone = cone_of_influence(g, o)                         # sub-LTEG
    if not o.deps:                                         # Tier 0: no contingent latency in the cone
        r = tier0(cone, o, cap=cfg.tier0_scenario_cap)     # exact: PROVED or REFUTED(omega) or TOO_MANY
        if r.kind != "too_many": return r
    elif cfg.use_tier1:
        r = tier1(cone, o)                                 # sound: PROVED or ESCALATE (never REFUTED)
        if r.kind == "proved": return r
    unbounded = [lv for lv in cone.lats if lv.hi is None]
    r = tier2(cone, o, timeout_ms=cfg.timeout_ms, unbounded=unbounded)
    return r                                               # PROVED | REFUTED(witness) | UNKNOWN(reason)
```

Rules:

1. Tier 0 applies when the cone has no `LatVar`. It enumerates outcome scenarios over the propositions appearing in labels within the cone (at most `tier0_scenario_cap`, default 4096). Above the cap, the obligation goes to Tier 2 (which treats propositions symbolically).
2. Tier 1 applies when the cone has latency variables. It may only prove. If its bounds do not imply the obligation, it escalates.
3. Tier 2 is exact. SAT yields a concrete `(ω, θ)` and, after replay, REFUTED. UNSAT is a proof. A timeout is UNKNOWN. If the cone contains an unbounded latency (`hi = None`), a SAT result is **not** a refutation: the missing number could make the obligation hold, so the result is UNKNOWN naming the key, with the witness recorded as "fails if `hi >= theta*`".
4. Two-execution obligations (`Variation`) go to Tier 1 (spread of bounds) and then Tier 2 with the product encoding.
5. Tier 3 is never called from here (import-linter contract `synthesis-isolated`).

### 11.2 Tier 0: concrete evaluation (`solve/concrete.py`)

```python
from fractions import Fraction

def evaluate(g: LTEG, omega: Mapping[Prop, bool], theta: Mapping[int, Fraction]) -> dict[int, Fraction]:
    """Dispatch times of every existing node. Exactly the semantics of Section 9.1."""
    val = _derived_values(g, omega)                          # evaluate Derived.expr from bit outcomes
    omega = {**omega, **val}
    t: dict[int, Fraction] = {g.origin: Fraction(0)}
    for v in g.topo:
        if v == g.origin: continue
        node = g.nodes[v]
        if not _sat(node.label, omega): continue             # node does not exist
        best: Fraction | None = None
        for ei in g.in_edges[v]:
            e = g.edges[ei]
            if e.src not in t or not _sat(e.label, omega): continue
            w = Fraction(e.w) if isinstance(e.w, int) else theta[e.w.id]
            cand = t[e.src] + w
            best = cand if best is None or cand > best else best
        if best is None:                                      # invariant I3 violated: builder bug
            raise QtError("E-GRAPH-LABEL", f"node {v} exists but has no active in-edge")
        if node.snap: best = node.snap * -((-best) // node.snap)     # ceil to grid; Fraction floor-div
        t[v] = best
    return t

def tier0(cone, o, cap):
    props = relevant_props(cone, o)                          # bit propositions occurring in cone labels / guard
    if 2 ** len(props) > cap: return Result.too_many()
    for assignment in product([False, True], repeat=len(props)):
        omega = dict(zip(props, assignment))
        if not _sat(o.guard, {**omega, **_derived_values(cone, omega)}): continue
        t = evaluate(cone, omega, theta={})
        if not holds(o.check, t): return Result.refuted(omega=omega, theta={}, times=t)
    return Result.proved(assumptions=o.assumptions)
```

Tier 0 is exact and is also the engine used to replay solver counterexamples in the evaluation harness. It is **not** a controllability notion: for each scenario it evaluates the one dispatch the hardware would perform (finding F4).

### 11.3 Tier 1: interval abstraction (`solve/interval.py`)

Goal: prove most obligations cheaply and soundly. Never refute.

**Affine-max forms.** The time of a node is represented as a maximum of affine terms in the latency variables, `max_i (c_i + sum_j a_ij * theta_j)` with constant `c_i` (Fraction) and integer coefficients `a_ij`. Edge addition adds a constant or one `theta`. A join of in-edges takes the union of the term lists.

**Must and may labels.** For an obligation with guard `L_o`:

- an edge is **must-active** if `L_o` implies its label and its source's label; **may-active** if its label and its source's label are each consistent with `L_o`;
- `Fmax[v]` uses all may-active in-edges (over-approximates the max: used for upper bounds);
- `Fmin[v]` uses only must-active in-edges (under-approximates the max: used for lower bounds; if there is none, the lower bound falls back to 0, because times are non-negative).

Both are sound for every outcome consistent with `L_o`.

**Bounds on a difference.** Let `ubound(a)` and `lbound(a)` be the maximum and minimum of an affine term over the box `theta_j in [lo_j, hi_j]` (a sum of per-variable extremes; infinite if a coefficient meets an unbounded end).

```python
def diff_upper(Fx_max, Fy_min, box) -> Fraction | None:
    """upper bound of t_x - t_y:  t_x <= max_i a_i ,  t_y >= b_j for ANY j  =>  t_x - t_y <= max_i (a_i - b_j)."""
    best = None
    for b in Fy_min:
        cand = max(ubound(a - b, box) for a in Fx_max)        # affine subtraction cancels shared thetas
        best = cand if best is None or cand < best else best
    return best

def diff_lower(Fx_min, Fy_max, box) -> Fraction | None:
    """lower bound of t_x - t_y:  t_x >= a_i for ANY i , t_y <= max_k b_k  =>  t_x - t_y >= min_k (a_i - b_k)."""
    best = None
    for a in Fx_min:
        cand = min(lbound(a - b, box) for b in Fy_max)
        best = cand if best is None or cand > best else best
    return best
```

The cancellation of shared latency variables inside `a - b` is what recovers correlations: in `t_branch - t_valid = (E + hi) - (E + theta) = hi - theta`, the common base `E` disappears. Without it the interval analysis would lose the proof of Appendix A.

**Controlling size.** Terms dominated by another (`lbound(b - a) >= 0` over the box) are dropped. If more than `K = 32` terms remain, the form collapses to a single constant term (`ubound` for max forms, `lbound` for min forms), which is sound and loses correlations. A node with `snap = g` is replaced by constants `g*ceil(lb/g)` and `g*ceil(ub/g)` (monotonicity of ceil).

**Deciding the obligation.**

| Check | Proved when |
| --- | --- |
| `Diff(x, y, "<=", c)` | `diff_upper <= c` |
| `Diff(x, y, ">=", c)` | `diff_lower >= c` |
| `Variation(x, y, B)` | `diff_upper - diff_lower <= B` |
| `Mod`, `Events` | not handled (escalate) |

The margin reported in the verdict (`c - diff_upper` and so on) is the Tier 1 margin when Tier 1 proved the obligation, otherwise the Tier 2 optimum (Section 11.4).

### 11.4 Tier 2: exact SMT with Z3 (`solve/smt.py`)

Logic: QF_LRA for time and latency (finding F27), Booleans for propositions, and `IsInt`/`ToInt` for grid and snapping (mixed linear integer-real arithmetic). Latency variables are reals in `[lo, hi]`. The encoding is exact for the bounded graph: it has a model if and only if some `(ω, θ)` violates the obligation.

```python
import z3
from fractions import Fraction

def RV(x) -> z3.ArithRef:
    f = Fraction(x); return z3.RealVal(f"{f.numerator}/{f.denominator}")

class Encoder:
    """Encodes the dispatch semantics of one copy of the universe (omega, theta, t)."""
    def __init__(self, g: LTEG, tag: str = ""):
        self.g, self.tag = g, tag
        self.bit = {p: z3.Bool(f"b{tag}:{p}") for p in g.bit_props}
        self.der = {p: z3.Bool(f"d{tag}:{p}") for p in g.derived}
        self.th = {lv.id: z3.Real(f"th{tag}:{lv.id}") for lv in g.lats}
        self.t = {n.id: z3.Real(f"t{tag}:{n.id}") for n in g.nodes}
        self.pre = {n.id: z3.Real(f"m{tag}:{n.id}") for n in g.nodes}
        self.ex = {n.id: self.label(n.label) for n in g.nodes}      # node existence = its label

    def prop(self, p): return self.bit[p] if p in self.bit else self.der[p]
    def lit(self, l):  return self.prop(l.prop) if l.pos else z3.Not(self.prop(l.prop))
    def label(self, L): return z3.And([self.lit(l) for l in L]) if L else z3.BoolVal(True)

    def wexpr(self, w):                                              # constant or latency variable
        return RV(w) if isinstance(w, int) else self.th[w.id]

    def constraints(self) -> list[z3.BoolRef]:
        g, cs = self.g, []
        for lv in g.lats:                                            # latency boxes (reals)
            cs.append(self.th[lv.id] >= RV(lv.lo))
            if lv.hi is not None: cs.append(self.th[lv.id] <= RV(lv.hi))
        for p, d in g.derived.items():                               # derived propositions are exact functions of bits
            cs.append(self.der[p] == self.expr(d.expr))
        cs.append(self.t[g.origin] == 0)
        for v in g.topo:
            if v == g.origin: continue
            node = g.nodes[v]
            terms = []                                               # (active, value) for every in-edge
            for ei in g.in_edges[v]:
                e = g.edges[ei]
                act = z3.And(self.label(e.label), self.ex[e.src])
                terms.append((act, self.t[e.src] + self.wexpr(e.w)))
            pre = self.pre[v]
            # max: pre is >= every active term, and equals one of them (when the node exists)
            cs += [z3.Implies(act, pre >= val) for act, val in terms]
            cs.append(z3.Implies(self.ex[v], z3.Or([z3.And(act, pre == val) for act, val in terms])))
            if node.snap:                                            # t = g * ceil(pre / g) ; ceil(y) = -floor(-y)
                cs.append(self.t[v] == RV(node.snap) * -z3.ToReal(z3.ToInt(-pre / RV(node.snap))))
            else:
                cs.append(self.t[v] == pre)
        return cs

    def expr(self, e):                                               # core Expr -> z3 (booleans; registers as bit-vectors)
        ...                                                          # EBit -> bit var; EBin("xor") -> z3.Xor; eq/lt on registers via BitVec built from bits

def violated(enc: Encoder, c: Check, guard: Label) -> z3.BoolRef:
    t, ex = enc.t, enc.ex
    base = z3.And(enc.label(guard))
    if isinstance(c, Diff):
        both = z3.And(base, ex[c.x], ex[c.y])
        gap = t[c.x] - t[c.y]
        bad = gap > RV(c.c) if c.op == "<=" else gap < RV(c.c)
        return z3.And(both, bad)
    if isinstance(c, Mod):
        return z3.And(base, ex[c.x], z3.Not(z3.IsInt((t[c.x] - RV(c.residue)) / RV(c.g))))
    raise NotImplementedError

def tier2(cone: LTEG, o: Obligation, timeout_ms: int, unbounded: list[LatVar]) -> Result:
    s = z3.Solver(); s.set("timeout", timeout_ms)
    if isinstance(o.check, Variation):                                # two copies of the universe (Section 11.5)
        a, b = Encoder(cone, "a"), Encoder(cone, "b")
        s.add(a.constraints() + b.constraints())
        s.add(z3.And(a.label(o.guard), a.ex[o.check.x], a.ex[o.check.y]))
        s.add(z3.And(b.label(o.guard), b.ex[o.check.x], b.ex[o.check.y]))
        s.add((a.t[o.check.x] - a.t[o.check.y]) - (b.t[o.check.x] - b.t[o.check.y]) > RV(o.check.bound))
        encs = (a, b)
    else:
        enc = Encoder(cone); s.add(enc.constraints()); s.add(violated(enc, o.check, o.guard)); encs = (enc,)
    r = s.check()
    if r == z3.unsat:   return Result.proved(assumptions=o.assumptions)
    if r == z3.unknown: return Result.unknown(reason=s.reason_unknown(), window=cone.meta.window_id, k=len(cone.bit_props))
    return _from_model(s.model(), encs, o, unbounded)

def _from_model(m: z3.ModelRef, encs, o, unbounded) -> Result:
    def q(v):                                                         # exact rational from a model value
        val = m.eval(v, model_completion=True)
        return val.as_fraction()                                      # RatNumRef -> Fraction (QF_LRA values are rational)
    cex = [Counterexample(
        omega={p: bool(z3.is_true(m.eval(b, model_completion=True))) for p, b in e.bit.items()},
        theta={i: q(v) for i, v in e.th.items()},
        times={i: q(v) for i, v in e.t.items() if z3.is_true(m.eval(e.ex[i], model_completion=True))},
        obligation=o) for e in encs]
    if unbounded:                                                      # missing number: not a refutation
        return Result.unknown(reason=f"fails if {', '.join(lv.key for lv in unbounded)} is large enough", witness=cex)
    return Result.refuted(cex)
```

Notes:

- **Max encoding.** `pre >= val` for each active term and `Or(active and pre == val)` for existence. Together they say `pre` equals the maximum of the active terms. A node whose label is false is unconstrained; every use of `t[v]` is guarded by `ex[v]`.
- **Existence.** `ex[v]` is the node's own label. Edge activity is `label(e) and ex[src]`, which matches Section 9.1.
- **Rational counterexamples.** Models of QF_LRA assign rational values. `as_fraction()` gives exact `Fraction`s, which the executor uses unchanged (finding F27). A counterexample therefore lies strictly inside the real latency box when that is where the violation is.
- **Counterexample for `Variation`.** The result carries two executions; the report shows both and their gap difference.
- **Parametric margin.** After PROVED, the margin and the largest safe latency come from Z3 `Optimize` on the same encoding: maximise `gap` for a `<=` check to obtain the worst-case gap, hence margin `c - max gap`. For "largest safe `hi`" the contract value is replaced by a Real parameter `H` in the encoding and the query is `maximize H` subject to the obligation holding for all `theta in [lo, H]`; since this is a quantified query, it is solved by bisection on the integer `dt` with repeated Tier 2 calls (each call is a plain satisfiability query). The result is reported in ns.
- **Scenario enumeration (optimisation).** For small `k` (at most 12 propositions in the cone), the dispatcher can split the query by assignments of the most frequent label propositions and solve the cubes in a process pool. This is only a speed-up inside Tier 2, not a different semantics.

### 11.5 Two-execution encodings and O5

**O4 and O7 (Variation).** `max - min <= B` over executions where the guard holds is equivalent to "no pair of executions has `x - y` differing by more than `B`". The product encoding above asserts both executions satisfy the dispatch constraints and the guard, and the negated bound. Using fresh variable tags (`a:` and `b:`) keeps them independent. The two copies share nothing, not even the program inputs, which is the right quantification: unpredictability is across all runs.

**O5 (ARTIQ lanes).** Section 10.5. The symbolic encoder models each lane's last coarse timestamp as a real variable, the current lane as an integer, and each submission as a `z3.If` chain over lanes. Collisions are pairwise: for each pair of events on one channel, `And(ToInt(Ti/8) == ToInt(Tj/8), Ti - 8*ToInt(Ti/8) != Tj - 8*ToInt(Tj/8))` under both existing. Busy: `T_j < T_i + busy_i` for `i` before `j` in time order on the same channel. Capped at 64 events.

### 11.6 Soundness arguments (sketches; theorem targets in Section 15)

1. **Tier 0.** Exact by construction. It is a direct evaluation of Section 9.1; the only risk is the builder, which is covered by differential tests against the independent executor.
2. **Tier 1.** For every `(ω, θ)` consistent with the guard and every node `v` existing there, `t(v)` is at most the maximum over `Fmax[v]` terms and at least the maximum over `Fmin[v]` terms. Proof by induction on the topological order using monotonicity of `+`, `max` and `ceil`. `diff_upper` and `diff_lower` then follow from `t_y >= b_j` and `t_x >= a_i` for any single term, and from term-wise interval bounds. Hence a proved obligation holds for every execution (theorem T1).
3. **Tier 2.** The constraint set is satisfiable with a given `(ω, θ, t)` if and only if `t` is the dispatch time function for `(ω, θ)`, on existing nodes (theorem T2): the max encoding is equivalent to the recursive definition. Thus UNSAT of the negated obligation proves it, and SAT yields a real violating execution (modulo unbounded latency, handled as UNKNOWN).
4. **Cross-check.** A SAT model is replayed in the executor, which implements the personality independently. A mismatch is `I-REPLAY-MISMATCH`, never a verdict.

### 11.7 Complexity, caching, parallelism

- **Cone of influence.** Each obligation is solved on the ancestors of its nodes plus the nodes whose labels it needs. Most obligations touch a small part of the graph.
- **Tier 0:** `O(2^k * E)` for `k` relevant propositions; Tier 1: `O(E * T^2)` with `T <= 32` terms; Tier 2: NP-hard in the number of Boolean propositions in general, but QF_LRA with a max structure is solved in milliseconds for the benchmark sizes expected (hundreds of nodes); the measured behaviour is the content of H3.
- **Cache.** Key = SHA-256 of the canonical serialisation of `(cone, obligation check, guard, solver config)`. Obligations from different windows or identical loop iterations hit the cache.
- **Pool.** `concurrent.futures.ProcessPoolExecutor` over obligations (default `os.cpu_count()` minus one); a per-obligation timeout and a global budget; results are deterministic regardless of completion order (sorted by obligation id).
- **Early exit.** `--first-failure` stops at the first REFUTED safety obligation; `--all` continues to collect every failure.

---

## 12. Synthesis and controllability module (Tier 3)

Tier 3 lives in `qtiming/solve/synth/` and answers a different question from verification. Verification asks: "for every outcome and every latency, does **this program's dispatch** satisfy the obligations?" Tier 3 asks: "could **any** dispatcher, or any choice of compile-time delays or stretch values, make the program safe?" It is complete and full-featured but is **never used to prove the program's own safety** (principle 8, import-linter contract `synthesis-isolated`; finding F1).

### 12.1 What it is used for

| Use | Question answered |
| --- | --- |
| `qtiming repair` | Which delays or stretch values would make a REFUTED program safe, and is any such repair possible at all? |
| Policy-feasibility claims for the paper | Is Δ-DMO with a given Δ achievable by some dispatcher on this program and contract? (binary search over Δ) |
| Necessary-condition check (theorem T6) | If the relaxed network is not dynamically controllable, no dispatch of any personality can make the program safe: report "unfixable by delays; change policy or program" |
| Cross-validation | On rigid encodings (tree-shaped dispatch) Tier 3 must agree with Tier 2 (theorem target T5); disagreement is a bug in one of them |
| Oracle testing of the algorithms themselves | Prob-in-Ctrl and CSTNU Tool benchmarks (Section 12.7) |

### 12.2 Relaxation: from LTEG to a temporal network (`synth/relax.py`)

The relaxed network `N_geq(P)` is built from the same LTEG but forgets that dispatch is a maximum that fires as early as possible:

- every dispatch edge `u -> v` with constant weight `w` becomes the requirement `t_v - t_u >= w` (a lower-bound requirement only: an executor is free to wait longer);
- every dispatch edge with a latency variable becomes a **contingent link** `(u, v, [lo, hi])` with `v` the contingent end;
- every obligation of the form `Diff` becomes a requirement constraint; `Variation` becomes a pair of requirement constraints against fresh executable copies (spread constraint);
- labels are kept for the CSTNU case; observation nodes are the `valid` nodes.

Any fixed dispatch of the program is one execution strategy of `N_geq(P)`. Therefore: **if the program is safe under its own dispatch, `N_geq(P)` is dynamically controllable** (theorem T6). The converse fails, because `N_geq` lets a strategy delay events that the hardware never delays. This is the precise sense in which controllability is a necessary but not sufficient condition, and why v1's use of it as the verification criterion was unsound.

### 12.3 STN consistency and the negative-cycle witness (`synth/stn.py`)

Distance-graph convention used throughout this section ("convention E"): an edge `u -> v` with weight `w` encodes `t_v - t_u <= w`. A lower bound `t_v - t_u >= w` is the edge `v -> u` with weight `-w`. An STN is consistent iff its distance graph has no negative cycle.

```python
from fractions import Fraction
INF = None

def bellman_ford(n: int, edges: list[tuple[int, int, Fraction, str]]):
    """Virtual source 0-weight to every node. Returns (dist, None) or (None, cycle_edges)."""
    dist = [Fraction(0)] * n          # virtual source: every node starts at 0
    pred: list[tuple[int, str] | None] = [None] * n
    last = -1
    for _ in range(n):
        last = -1
        for (u, v, w, tag) in edges:
            if dist[u] + w < dist[v]:
                dist[v] = dist[u] + w; pred[v] = (u, tag); last = v
        if last == -1:
            return dist, None
    # a relaxation still happened in round n: walk back n steps to land on the cycle
    v = last
    for _ in range(n): v = pred[v][0]
    cyc, x = [], v
    while True:
        u, tag = pred[x]; cyc.append((u, x, tag)); x = u
        if x == v: break
    return None, list(reversed(cyc))
```

Each edge keeps its `tag` (obligation code or dispatch rule plus source `nid`), so the cycle maps to a human sentence such as "the deadline at line 12 (O3) and the wait inserted by EQ at line 14 cannot both hold". Complexity is `O(N*E)`. Floyd-Warshall (`O(N^3)`) computes the minimal network on small windows and is used by repair to read off feasible delay ranges.

### 12.4 Strong controllability (Vidal-Fargier reduction, `synth/sc.py`) (finding F3)

**Definition.** An STNU is *strongly controllable* (SC) if there is a single assignment of times to the executable time-points, chosen without knowing any contingent duration, that satisfies every constraint for every `theta` in the contingent boxes.

**Not** the reduction "replace each contingent link by a requirement edge `[lo, hi]`": that checks pseudo-controllability, which is unsound for SC. The correct reduction rewrites every constraint that touches a contingent end-point onto the executable activation point, taking the worst case over the box.

Let `C` be the contingent end of link `(A, C, [lo, hi])`, so `C = A + theta` with `theta in [lo, hi]`, `A` executable. Constraints are `t_Y - t_X <= w` (convention E) with `X`, `Y` executable or contingent end-points.

| Constraint | Must hold for all `theta` | Worst case | Rewritten (all executable) |
| --- | --- | --- | --- |
| `X - C <= w`  (`X` executable) | `X <= C + w` | `C` minimal: `A + lo` | `X - A <= w + lo` |
| `C - X <= w`  (`X` executable) | `C <= X + w` | `C` maximal: `A + hi` | `A - X <= w - hi` |
| `C1 - C2 <= w` (two different links) | `C1 <= C2 + w` | `C1` max, `C2` min | `A1 - A2 <= w - hi1 + lo2` |
| `X - Y <= w` (both executable) | unchanged | | unchanged |

The first two rows: for "`X - C <= w`", `X` must not be too late relative to `C`, and `C` can be as early as `A + lo`; for "`C - X <= w`", `C` must not be too late relative to `X`, and `C` can be as late as `A + hi`. The network over the executable points with the rewritten constraints is an ordinary STN; it is consistent iff the STNU is SC. A negative cycle in it maps back to a witness: which constraints, and at which extreme of which `theta`.

*Normal form.* Activation points must be executable. A contingent end that is the activation of another link (a chain) is expressed as a sum `theta1 + theta2` and handled by worst-casing each term; the exporter instead inserts a support node joined by equality edges so that every activation is executable (the same fix the CSTNU Tool needs, Section 12.6).

**Worked mini-example.** `A` executable; contingent `C in [A + 20, A + 50]` (`lo = 20`, `hi = 50`); `X` executable with
- (a) `X >= C`, i.e. `C - X <= 0`;
- (b) `X <= C + D`, i.e. `X - C <= D`, with `D = 10`.

Rewrite: (a) `C - X <= 0` becomes `A - X <= 0 - 50 = -50` (`X >= A + 50`). (b) `X - C <= 10` becomes `X - A <= 10 + 20 = 30` (`X <= A + 30`). The two conflict: the cycle `A -> X` (weight 30) and `X -> A` (weight -50) has weight `-20`. In general the cycle weight is `D - (hi - lo)`, so the network is SC iff `hi - lo <= D`. Here `30 > 10`, so not SC. With `D = 30` the cycle has weight 0 and `X = A + 50` works for every `theta`: the schedule waits the worst case, which is exactly EQ's behaviour and its idle cost.

Dynamic controllability is strictly weaker here: `X` can fire at the moment `C` is observed (`X = C`), which satisfies (a) and (b) for every `D >= 0` because `C - C = 0`. Reactive dispatch needs no wait; that is the trade between EQ (SC-like, pays idle) and SYNC or EXP (DC-like, no wait, timeline varies).

### 12.5 STNU dynamic controllability (`synth/stnu_dc.py`, `rul.py`, `bruteforce_dc.py`)

**Definition.** An STNU is *dynamically controllable* (DC) if there is an execution strategy that decides when to fire each executable point using only the past (including the observed durations of contingent links that have already ended) and satisfies every constraint whatever the contingent durations are. SC implies DC implies weak controllability.

**Plan of implementation (three layers, each validated against the next):**

1. `bruteforce_dc.py`. A game solver for tiny integer networks (at most 7 points, horizon at most 12 dt). Integer ticks; at each tick the executor chooses which executable points fire now, nature chooses which contingent ends occur now (respecting `[lo, hi]` from their activation), the executor observes the outcome after the tick; the executor wins if all constraints hold when everything has fired. It is exponential and exists only as an independent oracle for the other two layers (restricting to integer strategies is assumed valid for integer networks **[verify against the literature before using it as ground truth]**).
2. `stnu_dc.py`: Morris (2014), `O(N^3)`. The labelled-distance-graph propagation with ordinary, upper-case and lower-case edges, implemented from the paper (CPAIOR 2014, DOI 10.1007/978-3-319-07046-9_33). **This document deliberately does not reproduce the rule table**: a transcription error in a plan is worse than a pointer. Task P8.3 transcribes it from the paper, writes the rules as a table in `docs/theory/dc-rules.md` with convention E stated, and the module is flagged `unverified` until the full oracle suite passes (621 networks, Section 12.7). While unverified, `qtiming synth --dc` delegates to the CSTNU Tool bridge and prints a warning.
3. `rul.py` (optional, after layer 2 passes): RUL-minus (Cairo, Hunsberger, Rizzi, TIME 2018), complexity `O(MN + K^2 N + K N log N)` with `M` edges, `N` points, `K` contingent links. Same oracle suite, plus the speed benchmark. The improvements of Hunsberger and Posenato (AAAI 2022, "Speeding up RUL-") and FD_STNU (Information and Computation 2023, available inside the CSTNU Tool) are read for reference only.

Output on failure: the semi-reducible negative cycle with the contingent durations it fixes at their extremes (`theta*` per link). Because DC failures concern strategies, not single executions, this is reported as an explanation, not as a replayable counterexample (replayable counterexamples come only from verification, Section 13.3).

CSTNU (conditional) dynamic controllability: PSPACE-complete in general for CSTN (Cairo and Rizzi). v2 does **not** implement it natively; it is available only through the CSTNU Tool bridge, on windows with few propositions.

### 12.6 CSTNU Tool bridge (`synth/cstnu_tool.py`) (finding F19)

Facts about the tool (v7.1, released 2026-09-08; 7.2 is unreleased): Java; LGPL-3.0 with CC0 parts; reads GraphML via its `TCGraphMLReader`; running `java -jar` opens the GUI editor, so batch checks must call the `Checker` main class with `java -cp <jar> <main class>`; since v6.6 the STNU checker **rejects contingent links in sequence** (a contingent node as the activation point of another link) and links sharing an activation node.

Rules for the bridge:

1. **Subprocess only.** Never vendored, never linked, never imported in-process (licence isolation and crash isolation). The jar is downloaded by `artifact/fetch_cstnu.sh`, pinned by SHA-256 in `tests/oracle/cstnu.lock`, and verified before every run.
2. **Export.** `export_graphml(relaxed_network)` produces nodes for every executable point (kind normal), every contingent end (kind contingent end), and, for conditional windows, observation nodes with their proposition letter; requirement edges as `value` edges; contingent links as lower-case and upper-case pairs.
3. **Support nodes.** For every contingent link whose activation point is not a fresh executable node, or which shares its activation node with another link, the exporter creates a support node `S` and zero-length requirement edges (`S - A = 0` as two edges) and uses `S` as the activation of the link. A unit test exports every network used in Section 12.7 and checks that the tool accepts it.
4. **Invocation.**

```python
cmd = ["java", "-Xss64m", "-cp", str(JAR), CHECKER_MAIN,      # CHECKER_MAIN = the Checker class named in the 7.1 jar manifest/README [verify]
       "-t", "STNU", str(path)]                                # option names re-read from the 7.1 README in task P8.6
r = subprocess.run(cmd, capture_output=True, text=True, timeout=cfg.cstnu_timeout_s, check=False)
```

5. **Timeout and failure.** Default 60 s. A timeout or crash is UNKNOWN for the Tier 3 query, never a pass. A format error is reported with the offending GraphML snippet.
6. **Parse.** Success and DC/not-DC status from the checker output; on failure the negative-cycle report is mapped back to LTEG nodes through the node-name table written during export.
7. **Proposition letters.** The tool uses single-letter propositions; windows with more propositions than the tool supports (26 letters **[verify]**) are refused with a message to split the window.

### 12.7 Oracles and benchmark sets

| Oracle | Content | Use |
| --- | --- | --- |
| HEATlab Prob-in-Ctrl (MIT, Python) | 452 DC and 169 non-DC STNUs (621 total) | gate for `stnu_dc.py` and `rul.py`: exact agreement on every network |
| CSTNU Tool v7.1 | reference DC checker | agreement on all exported windows and on the generated random networks |
| Posenato `STNUBenchmark2020`, `CSTNUBenchmark2018`, 2025 diamond sets | larger STNU and CSTNU instances | scaling and agreement tests (nightly) |
| `bruteforce_dc.py` | tiny integer networks | three-way agreement (own DC, CSTNU Tool, brute force) on generated networks |

There is no PyPI package for STNU DC checking. Python implementations on GitHub (HEATlab/Prob-in-Ctrl, nrealus/stnu-conflicts, yuemning/dc-checking) are used as test references only, with their licences respected.

### 12.8 `qtiming repair` (`repair/suggest.py`, `repair/patch.py`)

Counterexample-guided repair of a REFUTED program:

```text
repeat up to K times (default 20):
    verdict = verify(program, contract)
    if verdict is PROVED or PROVED-UNDER: emit patch, stop
    cex = first safety counterexample
    first ask Tier 3: is N_geq(P) DC with the obligations?      # fixable at all by delays?
        if not: report "no delay can fix this: change the policy or the program", stop
    shortfall = how much the violated obligation misses by in cex           # exact Fraction, rounded UP to dt
    choose an insertion point:
        O1: before the violating commit on the cursor/RT chain; O3: nowhere (a delay makes it worse; suggest policy change);
        O2b: increase the EQ wait; O7/O4: pad the shorter arm on the offending resource
    program = program + Delay(point, shortfall)         # recorded as a patch hunk
```

Every candidate is **re-verified** with the same Tier 0/1/2 pipeline before it is shown, so a suggested patch is itself checked, not trusted. Output: a unified diff (for OpenQASM 3 text) or a Qiskit snippet, plus the verdict of the patched program and its added idle cost. The ARTIQ example of Appendix A gets the suggestion "insert `delay` of at least `theta_hi + issue_cost + commit_lead`".

### 12.9 Rigid encodings and cross-validation (theorem target T5)

`synth/rigid.py` detects **rigid** graphs: every non-origin node has exactly one active in-edge in every scenario (tree-shaped dispatch; no max with two live arguments), constant weights except latency variables, and no snapping. For a rigid graph the encoding as an STNU `N_rigid(P)` uses **equality** requirements for constant dispatch edges (two inequalities), contingent links for latency variables, and the obligations as requirement constraints. The theorem target: `DC(N_rigid(P) + obligations)` holds iff the obligations hold for the dispatch under every `(omega, theta)` (the only strategy is the dispatch itself). A property test generates random rigid graphs, runs Tier 2 and Tier 3 (`bruteforce_dc` and CSTNU Tool), and requires agreement. For non-rigid graphs only the one-way implication T6 is claimed.

---

## 13. Verdicts, counterexamples, reports

A verdict is a structured, serialisable object. It states the result, the assumptions it rests on, margins, policy cost, and, for REFUTED, replayed counterexamples.

### 13.1 Verdict lattice and combination

| Verdict | Meaning | Produced when |
| --- | --- | --- |
| PROVED | every safety obligation holds for all `(omega, theta)`, and every assumption used is `cyc` or `cert` (or none) | contract with cycle-counted or certified numbers on the used paths |
| PROVED-UNDER | all safety obligations hold, assuming the listed latencies are true bounds (any assumption weaker than `cyc`, any placeholder, or a hard obligation blocked by weak evidence) | the common case |
| REFUTED | at least one safety obligation fails for a concrete `(omega, theta)` **that was replayed in the executor and reproduced**; or a policy-incompatible request | witness found and replayed |
| UNKNOWN | a tier timed out, a needed bound is missing (`hi = None`), or the window was refused | names the missing field or window |

Order: REFUTED < UNKNOWN < PROVED-UNDER < PROVED. The program verdict is the minimum over obligation results.

```python
def combine(results: list[ObResult], prog: ElabProgram, contract: Contract) -> Verdict:
    if any(r.kind == "refuted" and r.obl.severity == "safety" for r in results): worst = REFUTED
    elif prog.missing or any(r.kind == "unknown" for r in results):               worst = UNKNOWN
    else:
        assumptions = combine_all(r.assumptions for r in results if r.kind == "proved")
        blocked = [r for r in results if r.obl.hard and not can_discharge(True, r.assumptions)]
        weak = assumptions and (blocked or any(not a.prov.cls.may_discharge_hard or a.prov.meta_placeholder
                                               for a in assumptions))
        worst = PROVED_UNDER if weak else PROVED
    return Verdict(worst, assumptions=sorted(assumptions), weakest=weakest(assumptions), ...)
```

### 13.2 JSON report (numbers from Appendix A)

```json
{
  "verdict": "PROVED-UNDER",
  "contract": {"name": "ibm_heron", "sha256": "<contract hash>", "target_snapshot": "ibm_kingston:<hash>"},
  "assumptions": [
    {"latency": "ff.default", "lo_ns": 0, "hi_ns": 600, "prov": "vendor",
     "source": "IBM blog, 2025-11-19", "placeholder": false}
  ],
  "weakest_class": "vendor",
  "obligations": [
    {"code": "O2b", "nid": 41, "result": "proved", "tier": 1},
    {"code": "O3",  "nid": 41, "result": "proved", "tier": 1, "margin_ns": 2400}
  ],
  "max_safe": {"ff.default.hi_ns": 3000},
  "policy_cost": {"eq_idle_ns_max": 600},
  "time_ms": 38
}
```

`max_safe` is the largest value of the named contract bound for which every obligation still holds **with the program re-elaborated** (Section 11.4, bisection); it is therefore consistent with finding F9. `policy_cost` is the maximum over `(omega, theta)` of EQ-inserted idle (wait minus realised latency plus pad), for H5.

### 13.3 Counterexamples

```python
@dataclass(frozen=True, slots=True)
class Counterexample:
    omega: Mapping[Prop, bool]            # measured bits; derived propositions are recomputed by the executor
    theta: Mapping[str, Fraction]         # latency OCCURRENCE -> rational value in dt
    obligation: str                       # code, e.g. "O1"
    nid: int                              # origin AST node and its loc
    event_time: Fraction                  # where the violation happens, dt
    shortfall: Fraction                   # how late / how much short, dt
    second: "Counterexample | None" = None   # Variation obligations: the second execution
```

Because latencies are physical reals, `theta` is rational (for example `theta_ff = 1203/2 dt`), and the executor takes `Fraction`s unchanged. The report prints values in ns with the exact fraction available in JSON.

### 13.4 Minimisation

Before reporting, the witness is shrunk with Tier 0's `evaluate` as the checker (cheap, exact):

```python
def minimise(g, cex, o):
    # 1. propositions: try flipping each; a proposition is relevant if flipping changes the verdict of the check
    relevant = {p for p in cex.omega if not still_violates(g, o, {**cex.omega, p: not cex.omega[p]}, cex.theta)}
    # 2. latencies: replace each theta_i by lo, hi or a simple rational (midpoint rounded to 1/8 dt) if the violation persists
    theta = dict(cex.theta)
    for i in sorted(theta, key=lambda k: -abs(theta[k] - mid(g, k))):
        for cand in (lo(g, i), hi(g, i), simple(theta[i])):
            if still_violates(g, o, cex.omega, {**theta, i: cand}): theta[i] = cand; break
    return Counterexample(omega={p: cex.omega[p] for p in relevant}, theta=theta, ...)
```

Propositions not in `relevant` are shown as "don't care". Latencies not involved in the violation are listed once as "any value in its interval".

### 13.5 Repeat-until-success verdict (`verdict/rus.py`) (finding F23)

For a capped loop: body duration `T`, cap `N`, exhaust handler duration `T_exh`, declared lower bound on per-iteration success probability `p_min`, `q = 1 - p_min`. Three numbers:

```latex
\mathrm{WCET}_{\text{cap}} = N\,T + T_{\text{exh}},\qquad
\mathbb{E}[T_{\text{cap}}] \le T\,\frac{1-q^{N}}{p_{\min}} + q^{N}\,T_{\text{exh}},\qquad
\Pr[\text{exhaust}] \le q^{N}
```

The expected-time expression is `E[T] = T*E[min(G, N)] + q^N T_exh` with `G` geometric, which is non-increasing in `p`; so evaluating at the declared lower bound `p_min` is an upper bound.

**Deadline miss.** If a deadline `D` encloses the loop and `T_post` is the worst-case duration of the work after the loop that must also finish before `D`, let `m = floor((D - T_post) / T)` be the number of complete iterations that fit. The deadline is missed only if the loop needs more than `m` iterations, so `Pr[miss] <= q^min(m, N)` (and `= 1` if `m < 0`). If `m >= N` the loop always finishes within the cap in time, and the only remaining miss is the exhaust path: `Pr[miss] <= q^N` if `N*T + T_exh + T_post > D`, else 0.

```python
from fractions import Fraction
def rus_verdict(T, N, T_exh, p_min: Fraction, D=None, T_post=Fraction(0), eps: Fraction | None = None):
    q = 1 - p_min
    out = dict(wcet=N*T + T_exh,
               expected_ub=T*(1 - q**N)/p_min + q**N*T_exh,
               p_exhaust_ub=q**N)
    if D is not None:
        m = (Fraction(D) - T_post) // T                      # floor division of Fractions
        out["m"] = m
        out["p_miss_ub"] = Fraction(1) if m < 0 else (q**N if m >= N and N*T + T_exh + T_post > D
                                                      else (Fraction(0) if m >= N else q**m))
    if eps is not None:                                      # cap needed for tail probability eps: smallest n with q**n <= eps
        n = 0
        while q**n > eps: n += 1
        out["n_star"] = n
    return out
```

Corrected illustration (illustrative numbers; `p_min = 1/2`, `T = 2 us`, `eps = 10^-6`, `D = 10 us`):

| Quantity | Value |
| --- | --- |
| `n*` (smallest `n` with `q^n <= 10^-6`) | 20 (`2^-20 = 9.54e-7`) |
| `WCET_cap` at `N = 20` | `40 us + T_exh` |
| `E[T_cap]` at `N = 20` | `4 us * (1 - 2^-20) + 2^-20 * T_exh`, about 4 us |
| `Pr[exhaust]` | `2^-20`, about `9.5e-7` |
| `Pr[miss]` with `T_post = 2 us` | `m = floor((10 - 2)/2) = 4`, `q^4 = 6.25%` (this reproduces the research report's "(1-p)^4, about 6%") |
| `Pr[miss]` with `T_post = 0` | `m = 5`, `q^5 = 3.125%` (v1's formula, which ignored post-loop work) |

All arithmetic is exact (`Fraction`); only display rounds. The hard check "worst case fits in `D`" fails here (`40 us > 10 us`), the probabilistic check passes or fails by the miss probability and its stated assumption `p_min` (a declared parameter: its provenance is `vendor` or user-declared and appears in the assumption list).

### 13.6 Report rendering

- **Terminal** (`render_text.py`): verdict line; assumptions table (key, interval in ns, class, source, placeholder flag); failing obligations with source excerpts (from `loc`) and the numeric shortfall; an ASCII timeline of the counterexample (one row per resource, time axis in ns, branch arms marked), for example:

```text
t(ns)      0        1000       2000       3000
q0 (meas)  |MMMMMMMM|
cpu               |.....read.....|issue x
cursor     ..........................|x@T=2310
                                  ^ underflow: committed 250 ns late (O1, line 14)
```

- **JSON** (`render_json.py`): Section 13.2, plus a `counterexamples` array.
- **SARIF 2.1.0** (`render_sarif.py`): one `result` per failing or unknown obligation. `ruleId` is the obligation code (`V-O1`, ...) or lint code; `level` is `error` for REFUTED safety, `warning` for UNKNOWN and advisory, `note` for assumptions; `locations` come from `loc` of the origin `nid`; `message.text` is the plain-language explanation; `properties` carries the counterexample and the contract hash; `partialFingerprints` is a hash of `(code, nid, contract sha)` so CI deduplicates across runs.
- **HTML timeline** (`render_html.py`): static page with an inline SVG, one row per resource, both executions for `Variation`, hover text with node ids. Generated from the executor trace of the replay so it shows exactly what the executor did.

---

## 14. Reference executor

The reference executor is a deterministic discrete-event interpreter of the elaborated TQ program. Given an outcome assignment `omega` and a latency realisation `theta`, it produces a timestamped trace or a list of violations. It is the **independent second implementation** of each personality's dispatch specification (principle 9): it shares only `core` types (AST, labels, time, naming helpers) and the loaded `Contract` with the checker, never graph, obligation or solver code (import-linter contract `executor-independence`). Agreement between executor and checker is therefore real evidence.

### 14.1 Engine (`exec/engine.py`)

- **Time.** `Fraction`, in dt. No floats.
- **State.** Per-resource clocks `clock[r]`, classical store `sigma` (bit proposition to bool), result-valid times `valid[prop]`, personality state (cursor and CPU clock for ARTIQ; Q1 core clock and RT queue for Q1; block state for IBM; align state for QUA).
- **Event queue.** For personalities with concurrent timelines (ARTIQ cursor vs CPU, Q1 core vs RT core), a binary heap keyed `(time, sequence number)`; the sequence number makes ties deterministic. Single-timeline parts are executed in program order.
- **No quantum state.** Only timing is tracked. Outcomes come from `omega`, so no amplitudes are simulated (fidelity is a non-goal).
- **Names.** Proposition and latency-occurrence names come from `core/ids.py` helpers (`bit_prop(reg, idx, meas_nid, iter_path)`, `lat_occurrence(key, meas_nid, iter_path, consumer_nid)`), so a counterexample produced by the checker addresses exactly the same variables in the executor. These helpers only build strings; no semantics is shared.

```python
class Engine:
    def __init__(self, prog: ElabProgram, contract: Contract, personality: "ExecPersonality", oracle: "Oracle"): ...
    def run(self) -> "ExecResult":
        self.pers.start(self)
        self._exec(self.prog.body, ctx=Ctx(path=(), guard=True))
        return ExecResult(trace=self.trace, violations=self.violations, drops=self.drops,
                          times=self.node_times)          # times keyed by (nid, path, tag) for replay comparison

    def _exec(self, s: Stmt, ctx: Ctx) -> None:
        match s:
            case Gate() | Delay():
                start = max(self.clock[r] for r in resources(s))
                self.advance(s, start, start + s.dur)
            case Measure():
                start = max(self.clock[q] for q in (res_of(s)))
                end = start + s.dur
                prop = bit_prop(s.cbit, s.nid, ctx.path)
                self.sigma[prop] = self.oracle.outcome(prop)
                theta = self.oracle.latency(lat_occurrence(self.lat_key(s), s.nid, ctx.path, None), self.lat_iv(s))
                self.valid[prop] = end + theta
                self.advance(s, start, end)
            case If():
                self.pers.on_branch(self, s, ctx, self._cond_value(s, ctx))   # personality decides arm start / join
            case Seq():
                for x in s.stmts: self._exec(x, ctx)
            case For() | While() | Call() | Within():
                ...
```

### 14.2 Oracles (`exec/oracle.py`)

| Oracle | Behaviour | Use |
| --- | --- | --- |
| `Fixed(omega, theta)` | replays a counterexample; unspecified latencies take the interval midpoint, unspecified bits `False`, and the executor records which defaults it used | replay of every REFUTED |
| `Random(seed)` | outcomes by seeded coin; latencies uniform on a rational grid of step 1/8 dt inside `[lo, hi]` | property tests, differential runs |
| `Extreme(strategy)` | every latency at `lo` or `hi`; strategy `adversarial` tries all `2^K` vertex assignments (K small) or a greedy hill climb that tracks which vertex maximises each obligation's gap | stress tests; exact for the vertex lemma (Section 15, T10) |
| `Exhaustive(k_max, K_max)` | every `omega` over the relevant bits times every vertex of the latency box | exact ground truth for H2 on small programs |

### 14.3 Personality hooks

Each personality implements `start`, `on_branch`, `on_join`, `on_commit`, `on_late`. All behaviour comes from `docs/personality-spec/<name>.md`; undocumented behaviour is a constructor parameter, never a hidden guess.

| Hook | IBM | Q1 | ARTIQ | QUA |
| --- | --- | --- | --- | --- |
| `on_branch` | single `if`/`else`; block starts at `max(valid(cond), clock of every arm resource)` (`block_start = all_resources`); arm runs | the Q1 core issues `set_cond`; for every conditional RT instruction the RT core executes it (duration) if the condition holds, else waits `else_time`; the condition is read from the trigger-network state at that instant | the kernel's classical code runs on the CPU clock; the taken arm's real-time statements are stamped from the cursor; no waiting | implicit align at block start for participating elements (deterministic or with a sampled align gap); arms run per element |
| `on_join` | `pad_to_longest_block`: block end is `start + max(arm durations)`; `restart_at_join`: block end is the arm's actual end | none (equal by construction when instruction counts and durations align; otherwise totals differ and the executor reports the difference) | none (the programmer's delays decide); `with parallel` joins at the max of branch cursors | none after the block; end times are label dependent |
| `on_commit` | not modelled (static schedule) | RT instruction enters the 32-entry queue; the Q1 core stalls if the queue is full; the RT core consumes at its timeline | event enters the RTIO FIFO via the 8 SED lanes with its stamped timestamp | not modelled |
| `on_late` | job-validation failure is a lint, not a runtime event | queue empty when the RT core needs its next instruction: `SEQUENCE_PROCESSOR_RT_EXEC_COMMAND_UNDERFLOW`, sequencer **halts** (run stops, violation `underflow-halt`) | underflow or overflow: **raise** (violation `underflow`, run stops); sequence, collision and busy: event is **dropped and logged** (a `SilentDrop`, the event vanishes from the trace of effects) | gap under `strict_timing_`: compile error (lint); otherwise the gap is part of the timeline |

### 14.4 ARTIQ personality in detail (finding F17)

```python
class ArtiqPersonality(ExecPersonality):
    def __init__(self, contract):
        self.lanes = contract.capacity["lanes"]; self.coarse = contract.capacity["coarse_mu"]
        self.commit_lead = contract.commit_lead              # Fraction or None (unknown: violations of this kind are not decidable -> UNKNOWN in harness)
        self.top = [None] * self.lanes; self.cur = 0; self.by_slot = {}; self.busy_until = {}

    def on_commit(self, eng, ev):                            # ev: channel, T (cursor stamp), busy, issue time (CPU clock now)
        slack = ev.T - eng.cpu_clock
        if self.commit_lead is not None and slack < self.commit_lead:
            eng.violate("underflow", ev, shortfall=self.commit_lead - slack); eng.halt(); return   # RTIOUnderflow raised
        coarse, fine = divmod(ev.T, self.coarse)
        now_c = eng.cpu_clock // self.coarse
        # sequence error (lane assignment)
        for step in range(self.lanes):
            l = (self.cur + step) % self.lanes
            pending = self.top[l] is not None and self.top[l] > now_c
            if (not pending) or coarse > self.top[l]:
                self.top[l] = coarse; self.cur = l; break
        else:
            eng.drop("sequence", ev); return                 # discarded and logged, not raised
        if self.by_slot.get((ev.channel, coarse), fine) != fine:
            eng.drop("collision", ev); return
        if ev.T < self.busy_until.get(ev.channel, -1):
            eng.drop("busy", ev); return
        self.by_slot[(ev.channel, coarse)] = fine; self.busy_until[ev.channel] = ev.T + ev.busy
        eng.emit(ev)
```

This is intentionally written separately from the symbolic and reference versions in `solve/` (Section 10.5). Both are checked against the same golden cases (`tests/personality/artiq/`). Parameters that the documentation does not fix (nearly-full rule, FIFO depth, `sed_spread_enable` behaviour) are constructor arguments, and the executor refuses to run with an unspecified parameter that matters for the program unless the user passes `--assume`.

### 14.5 Result types

```python
@dataclass(frozen=True, slots=True)
class Violation:
    kind: Literal["underflow", "underflow-halt", "stale-read", "stall", "deadline", "gap", "capacity", "grid", "sync-spread"]
    nid: int; t: Fraction; shortfall: Fraction | None; detail: str

@dataclass(frozen=True, slots=True)
class SilentDrop:
    kind: Literal["sequence", "collision", "busy"]; nid: int; t: Fraction; channel: str

@dataclass(frozen=True, slots=True)
class ExecResult:
    trace: tuple[TraceEvent, ...]; violations: tuple[Violation, ...]
    drops: tuple[SilentDrop, ...]; times: Mapping[tuple, Fraction]
```

Program-level properties that are not hardware faults (deadline from `within`, stall of an EQ arm by a late result, spread across runs) are computed by the executor from its own trace using the annotations in the AST: `deadline` (start of each first body op minus the anchor valid time), `stall` (arm start later than resource-ready because the result arrived later), `gap` (per-resource idle). For `Variation` obligations the harness (`verdict/replay.py`) runs the executor twice with the two executions of the counterexample and compares.

### 14.6 API

```python
res = execute(prog_elab, contract, oracle=Fixed(omega, theta), personality="artiq")
res.trace       # list of (t_dt, resource, op, nid)
res.violations  # list[Violation]
res.drops       # silent drops (ARTIQ)
```

`replay(verdict_counterexample, prog, contract)` returns whether the executor reproduces the **same obligation failure at the same node**. The checker calls it before reporting any REFUTED; a mismatch is `I-REPLAY-MISMATCH` and the counterexample is withheld.

### 14.7 q1simulator cross-check (`exec/q1sim_bridge.py`)

q1simulator (a public Q1 core simulator that models the RT buffer and aborts on underrun) is used as an external check of the Q1 personality for a **supported subset** of programs: straight-line and `set_cond` programs of RT instructions (`play`, `acquire`, `wait`, `upd_param`) with fixed latencies. The bridge lowers the TQ subset to Q1ASM text, runs the simulator in a **separate virtual environment on Python 3.12 or newer**, and compares underflow or no-underflow against the executor and against the checker's O1. Agreement on the subset is reported as an independent validation; programs outside the subset are not cross-checked. The simulator is a test-time tool, never a runtime dependency.

---

## 15. Theory track

The implementation is paired with a short formal development. This section states definitions, what is a theorem target, and what is conjecture. Statuses: **[defn]**, **[proved-sketch]** (an argument is given here and must be written out), **[target]** (a statement to prove), **[conjecture]**, **[cited]**.

### 15.1 Semantics

Fix a program `P`, a contract `C` (with its personality) and a dispatch specification `D_C`.

- `Omega_P`: outcome assignments consistent with `P` (assignments to bit propositions).
- `Theta_C`: latency realisations admitted by `C`: one real `theta_i in [lo_i, hi_i]` per latency occurrence.
- `exec_C(P, omega, theta)` is either a trace of timestamped events or a violation, computed by the dispatch rules of Section 9 (equivalently, by the executor of Section 14).
- `t_e(omega, theta)`: dispatch time of event `e`.

### 15.2 Definitions over fixed dispatch **[defn]**

```latex
\textbf{Safe}(P,C):\quad \forall\omega\in\Omega_P,\ \forall\theta\in\Theta_C:\ \mathrm{exec}_C(P,\omega,\theta)\ \text{has no violation}.

\textbf{DMO}(P,C):\quad \textbf{Safe}(P,C)\ \wedge\
 \big[\forall\omega,\ \forall\theta,\theta'\in\Theta_C:\ \mathrm{tr}(P,\omega,\theta)=\mathrm{tr}(P,\omega,\theta')\big]\ \wedge\
 \big[\text{causality: no dispatch decision precedes the observation it depends on}\big].

\Delta\textbf{-DMO}(P,C):\quad \textbf{Safe}\ \wedge\ \text{causality}\ \wedge\
 \forall e,\omega,\theta,\theta':\ |t_e(\omega,\theta)-t_e(\omega,\theta')|\le\Delta_e.

\textbf{Safe-only}:\quad \textbf{Safe}\ \wedge\ \text{causality}.
```

Causality is invariant I4 (Section 9.5), plus the obligation O2a for predicated personalities. These replace the research report's definitions: the quantifiers range over executions of the **fixed** dispatch of the personality, not over schedules.

### 15.3 Correction to the research report's conjectures **[defn, with justification]**

The report conjectured that EXP safety is equivalent to dynamic controllability of the encoded network, and that DMO is a hybrid SC/DC notion. As stated those are false in general: dynamic controllability asks whether some strategy exists, and a strategy may delay an event that the hardware never delays. The correct relation is:

- **Verification** (this tool): a universal check over `(omega, theta)` of the fixed dispatch.
- **Controllability** (Tier 3): existence of a dispatcher or of compile-time delays.
- **T5** (rigid encodings) and **T6** (necessary condition) below say exactly when they coincide and in which direction they imply each other.
- For specifications that leave freedom (stretch, `box`, `within` with no fixed implementation) strong or dynamic controllability is the right question about compile-time or runtime freedom, and is what `qtiming repair` and `qtiming synth` answer.

### 15.4 Theorem targets

| ID | Statement | Status and proof route |
| --- | --- | --- |
| T1 | **Tier 1 soundness.** If Tier 1 proves obligation `o`, then `o` holds for every `(omega, theta)` | **[proved-sketch]** induction over topological order with `Fmax`/`Fmin` (Section 11.6); mechanise in Lean if time allows |
| T2 | **Tier 2 exactness.** The Section 11.4 constraint system is satisfiable with `(omega, theta, t)` iff `t` is the dispatch time function of `(omega, theta)`; so UNSAT proves and SAT yields a violating execution | **[proved-sketch]**; the max encoding is equivalent to the recursive definition; write it out |
| T3 | **EQ implies DMO.** If every branch is EQ, loops are bounded or capped, calls have bounded latency, and O2a, O2b, O7 (with `Delta_eff = 0`) hold for every branch, then `P` is DMO | **[proved-sketch]**: remove all `valid` nodes from the graph; O2b says no `valid` node is ever the maximiser at an arm start, so event times equal the times in the valid-free graph, which contain no `theta`; hence trace equality over `theta`; outcome independence comes from O7 |
| T4 | **Windowed composition.** If a cut `J` satisfies the five cut rules of Section 9.7, then the obligations of the whole program hold iff they hold in every window analysed with `J` as origin | **[target]**; proof uses shift invariance of dispatch under the cut rules (all in-edges after the cut originate at `J`), no cross-cut obligations, canonical personality state; check with the whole-vs-window differential test (Section 16.5) |
| T5 | **Rigid equivalence.** For rigid graphs (tree-shaped dispatch) `DC(N_rigid(P) + obligations)` iff all obligations hold for all `(omega, theta)` | **[target]**; the only strategy is the dispatch itself; strong controllability is strictly stronger (fails whenever a rigid node depends on a contingent end with `lo < hi`); validated by property test (Section 12.9) |
| T6 | **Necessary condition.** If `P` is safe under its dispatch then `N_geq(P)` with the obligations is dynamically controllable | **[proved-sketch]**: the dispatch is a strategy of `N_geq(P)` that uses only observed information (causality, I4) |
| T7 | **Delta-DMO from SYNC.** If branches are SYNC with O7 bounds `Delta_k`, then `P` is Delta-DMO with `Delta_e = sum of Delta_k` over joins before `e` on its path; a join that re-anchors to an absolute point restarts the sum | **[target]** (carried over from the research report; now over fixed dispatch) |
| T8 | **Conformance.** For every personality, graph evaluation `evaluate(G, omega, theta)` and the executor agree on all event times and violations | **[target for one personality]**, **[tested]** for all: differential harness (Section 16.5); mechanising IBM-EQ in Lean is optional |
| T9 | **Strong controllability reduction.** The Vidal-Fargier rewrite (Section 12.4) is correct | **[cited]** (Vidal and Fargier; CEUR Vol-2509); re-derived in `docs/theory/sc.md` and tested against brute force |
| T10 | **Vertex lemma.** In a graph without snap nodes, for any two nodes `x, y` and fixed `omega`, `t_x - t_y` attains its maximum and its minimum over the latency box at a vertex of the box. Hence for `Diff` and `Variation` obligations a violation exists iff one exists with every `theta_i in {lo_i, hi_i}` | **[proved-sketch]**: each latency occurrence enters any path term with coefficient 0 or 1, so `t_x` and `t_y` are each convex piecewise-linear with slopes in `{0, 1}` in every single `theta_i`, hence `t_x - t_y` has slope in `{-1, 0, 1}`, and slope changes only by `t_x` (0 to 1) or `t_y` (0 to 1); no sign change from `+` to `-` or from `-` to `+` can occur, so there is no strict interior extremum along any coordinate; apply coordinate by coordinate. **Fails with snap nodes** (ceil breaks the argument), so the exhaustive oracle is exact only for snap-free graphs |

T10 justifies two practical things: the `Extreme` and `Exhaustive` oracles are exact ground truth for snap-free programs (H2), and counterexample minimisation may move `theta` to interval endpoints without losing the violation (Section 13.4). It also gives a precise form to the report's statement that "most refutations need only interval endpoints".

### 15.5 Proved versus conjecture, summarised

Proved by construction or cited: SC reduction, STN consistency characterisation, RUL complexity. Proof sketch present here: T1, T2, T3, T6, T10. Targets requiring a real proof: T4, T5, T7, T8. Conjecture withdrawn: "EXP safety iff DC" (false as stated). Nothing in the tool's soundness depends on T4, T5, T7: windowing can be disabled, Tier 3 is off the verification path, and Delta-DMO is a reported property.

### 15.6 Optional mechanisation

Lean 4 (preferred, for the finite-graph and arithmetic lemmas) or Agda (to build on the GRAMPUS artifact): T2 (max encoding), T1, T3 for the IBM-EQ fragment. Not on the critical path. Rule: nothing in the plan waits for it.

---

## 16. Testing and verification

The tool's value is that PROVED can be trusted, so testing is organised around catching false proofs. Layers 1 to 5 plus personality conformance and mutation testing; the soundness differential (H1) runs in CI.

| Layer | What it tests | Tool | Volume | Runs |
| --- | --- | --- | --- | --- |
| 1. Unit | each module: rounding by role, provenance combination, label algebra, loader, annotation parsing, Bellman-Ford, SC rewrite, RUS arithmetic, SED model | pytest | about 500 tests | every commit, under 1 min |
| 2. Golden | end-to-end verdicts on the benchmark suite match stored expectations; text, JSON, SARIF snapshots | pytest + YAML | about 60 programs x 4 contracts | every commit |
| 3. Property | invariants over random programs and contracts | hypothesis | 2,000 examples per property in CI; 100,000 nightly | commit + nightly |
| 4. Differential | checker versus independent executor (H1, H2); Tier 2 versus Tier 0; windowed versus whole; Tier 3 versus Tier 2 on rigid graphs | custom harness | N randomised and extreme runs per program (N pre-registered) | nightly |
| 5. Oracle | own DC solvers versus CSTNU Tool, Prob-in-Ctrl, brute force | subprocess + Python | 621 networks plus every exported window | nightly |
| 6. Personality conformance | graph builder and executor on the specification's worked examples | pytest | per personality | every commit |
| 7. Mutation | tests kill mutants in `solve/` and `oblig/` | mutmut | monthly; target score at least 85% before submission | monthly |

### 16.1 Layer 1 specifics

Unit tests that directly pin the corrected findings: `ns_to_dt` for every role at boundary values (3000 ns, 3001 ns, 3003 ns at dt = 4); loader errors for non-multiple durations and for `msigma` without `hi`; `Interval.__add__` keeps no provenance but `combine` keeps all assumptions; Q1 contract reproduces the 388 ns example (`149 + 239`); policy compatibility table has a test per cell; RUS table of Section 13.5 reproduced exactly; `sed_simulate` golden cases (strictly increasing within a lane, wrap to the next lane, all lanes busy gives a sequence drop, collision, busy).

### 16.2 Layer 3: the properties (corrected, finding F9)

1. **Soundness.** If `check(P, C)` is PROVED or PROVED-UNDER, then for every sampled and extreme `(omega, theta)` within `C`, `execute(P, C, omega, theta)` has no violation.
2. **Witness validity.** If REFUTED with `(omega, theta)`, then `execute` with that pair reproduces the same obligation failure at the same node.
3. **Monotonicity for a fixed elaborated program.** Fix an elaborated program `E`. Shrinking any latency interval of the contract **without re-elaborating** `E` never turns a proved obligation into a refuted one (the set of executions only shrinks). **Elaboration-dependent monotonicity is not a property.** A regression test records a counterexample to it: on a contract where EQ waits to `hi`, a smaller `hi` arms the arms earlier, leaves less issue slack, and can create an O1 underflow that the larger `hi` avoided.
4. **Provenance monotonicity.** Upgrading the provenance class of an assumption never moves a verdict down the order REFUTED < UNKNOWN < PROVED-UNDER < PROVED.
5. **Tier agreement.** (a) Tier 0 equals Tier 2 on obligations with no latency variables. (b) Tier 1 PROVED implies Tier 2 UNSAT. (c) Tier 2 SAT implies executor replay reproduces. (d) On rigid graphs Tier 3 agrees with Tier 2 (T5). (e) Vertex lemma: for snap-free graphs, Tier 2 SAT iff the exhaustive vertex enumeration finds a violation (T10).
6. **Elaboration idempotence.** `elab(elab(P)) == elab(P)`.
7. **Round trip.** `load(dump(c)) == c` for OpenQASM 3 and QPY with `timing.*` annotations.
8. **Cone invariance.** The verdict of an obligation on its cone of influence equals the verdict on the full graph.
9. **Window equivalence.** On programs small enough for both, windowed and whole-program verdicts are equal (T4).
10. **Rounding soundness.** For any ns value and role, the dt result is on the sound side (never admits a value outside the stated bound).
11. **Tier 1 containment.** For random `(omega, theta)`, the evaluated `t_x - t_y` lies inside the Tier 1 bounds.
12. **Determinism.** The verdict is independent of process-pool scheduling and of dictionary order.
13. **Minimisation preserves the violation.**
14. **Vertex minimisation.** When no snap node is present, minimisation can always reach an endpoint-only `theta`.

### 16.3 Random program generator

A hypothesis strategy builds well-typed TQ programs plus matching contracts. Dimensions: 1 to 8 qubits; 0 to 6 measurements; `if` nesting up to depth 3 (zero on IBM-like contracts); bounded loops up to 4 iterations; capped `while` up to cap 4; random policy per branch; random derived conditions (single bit, parity, comparison) respecting the backend lint; random gate durations (multiples of dt); latency intervals in `[0, 2000]` dt with random provenance classes; `within` annotations with random deadlines; for ARTIQ-like programs random cursor delays and event channels. Separate strategies produce **rigid** graphs (for T5) and **snap-free** graphs (for T10). Shrinking yields minimal failing programs that become golden tests automatically.

### 16.4 Exhaustive ground truth (H2)

For programs with at most 10 relevant bit propositions and at most 6 latency variables, the executor's `Exhaustive` oracle enumerates every outcome assignment and every vertex of the latency box. For snap-free programs this is exact (T10). It yields the true set of violated obligations, from which the false-alarm rate (checker says REFUTED or UNKNOWN, but no reachable violation) and the miss rate (must be zero) are computed. Programs with snap nodes additionally sample interior points on a rational grid and are labelled "sampled" in the results.

### 16.5 Differential harness

```text
for each program P, contract C:
    v = check(P, C)
    if v in {PROVED, PROVED-UNDER}:
        run executor N times with Random(seed), plus Extreme(adversarial) and, where small, Exhaustive
        assert no violation (H1)
    if v is REFUTED:
        assert replay reproduces (witness validity)
    compare windowed vs whole-program verdict where both are feasible (T4)
    compare Tier 1 / Tier 2 / Tier 0 verdicts where more than one applies
```

Every disagreement is a bug in the builder, a tier or the executor, and is triaged by shrinking with hypothesis. A passing run of this harness over all benchmarks and the pre-registered number of random programs is the gate for H1.

### 16.6 O5 differential

`sed_simulate` (reference), the executor's ARTIQ personality, and the symbolic `smt_o5` encoding are compared on random event lists: all three must agree on the set of dropped events and their kinds.

### 16.7 Layer 5: oracle tests

- Prob-in-Ctrl: 452 DC and 169 non-DC networks; the own DC checker must agree on all 621 (gate for P8).
- CSTNU Tool: random STNUs and CSTNs generated by hypothesis plus every window exported by the pipeline; the tool and the own checker must agree; any CSTNU Tool timeout counts as skipped, not passed.
- Posenato and 2025 diamond benchmark sets: nightly, agreement plus timing.
- Brute-force DC: tiny integer networks, three-way agreement.
- SC reduction versus brute-force SC (enumerate schedules over the executable points on a small grid).

### 16.8 Mutation testing

`mutmut` on `solve/` (excluding `synth/` initially) and `oblig/`. Every surviving mutant is a missing test and becomes a ticket. Target before submission: mutation score at least 85% on both packages. Mutants in `core/time.py` rounding and in `dispatch/` are also run (high value, small).

---

## 17. Benchmarks and evaluation

The suite has about 60 programs in nine families, each run against all four contracts and the three policies where the backend class allows them. Expected verdicts are stored in YAML. One command regenerates every table and figure from scratch.

### 17.1 Benchmark families

| Family | Programs | Why it is there | Main obligations |
| --- | --- | --- | --- |
| Teleportation and gate teleportation | 6 | canonical feedforward; fits IBM restrictions | O2a/b, O3, O4 |
| Active reset | 4 | simplest conditional; vendor latency claims exist | O2, O4 |
| Long-range CNOT / GHZ via measurement | 8 | many parallel conditionals, wide joins | O4, O7 |
| Repeat-until-success gate synthesis | 8 | capped loops, RUS verdicts | O9, O3 |
| Repetition code and small surface-code rounds (d = 3, 5) | 12 | rare correction branches, windowing | O2, O3, O5 |
| Magic-state injection with conditional S, `within[D]` | 6 | fault-tolerance reaction deadline (hard) | O3 (hard) |
| Lattice-surgery merge/split with patch-sync slack (after Maurya and Tannu) | 6 | sync policies | O7 |
| ARTIQ manual kernels in EXP form | 6 | negative slack, silent drops; not written by us | O1, O5 |
| Dynamarq programs (where available) | about 10 | external, reduces benchmark bias | all |

Each benchmark is a directory: `prog.qasm` or `prog.py`, `meta.yaml` (family, expected verdict per `(contract, policy)`, notes, licence of external sources), and an optional `ground_truth.json` from exhaustive enumeration (Section 16.4). Programs not written by us carry their licence and provenance in `meta.yaml`.

### 17.2 Hypotheses mapped to experiments

| Hypothesis | Experiment | Metric | Output |
| --- | --- | --- | --- |
| H1 Soundness | differential runs on all benchmarks plus the pre-registered number of random programs, per personality | executor violations on PROVED or PROVED-UNDER programs (must be 0) | table |
| H2 Precision | exhaustive enumeration on small programs (exact for snap-free programs, T10) | false-alarm rate (REFUTED or UNKNOWN with no reachable violation) | table |
| H3 Scalability | sweep circuit size and number of timing-relevant propositions per window; windowing on and off; tier mix | check time; fraction certified within the time limit; tier at which each obligation was resolved | scaling plot (log time vs size) |
| H4 Portability | same source on all 4 contracts | percentage of dynamic programs with differing verdicts; list of rejections by policy incompatibility; Q1 per-instruction divergences | verdict-matrix heatmap |
| H5 Policy cost | EQ vs SYNC on QEC and RUS families under IBM-like latencies | added idle (`policy_cost`, Section 13.2) as a percentage of program time | bar chart |
| H6 Hardware | IBM evidence (Section 18): inferred feedforward window and join behaviour vs the vendor 600 ns | inferred values vs claim; agreement within the pre-registered delta | fit plot or table |
| (headline) | provenance dependence | number of verdicts resting on non-certified numbers; placeholder count | single number |

Thresholds written as angle-bracket symbols in the research plan (N, x percent, y percent, s seconds, k, z percent, w percent, delta, sigma) are fixed in a pre-registration file committed before the evaluation runs.

### 17.3 Pre-registration (`prereg/prereg-2026.yaml`)

```yaml
version: 1
registered: <date>            # committed with an annotated git tag "prereg-1" BEFORE any evaluation run
git_commit: <hash of the code the evaluation will run>
contracts: {sha256: {...}}    # hashes of the contract files used
hypotheses:
  H1: {runs_per_program: 1000, random_programs: 10000, seeds: [1, 2, 3], threshold_violations: 0}
  H2: {max_props: 10, max_latencies: 6, false_alarm_rate_max: 0.10}
  H3: {time_limit_s: 60, coverage_min: 0.90, max_props_per_window: 12}
  H4: {min_differing_fraction: 0.30}
  H5: {max_extra_idle_fraction: 0.25}
  H6: {tolerance_ns: 100, spread_max_ns: 200}
analysis: {tests: ..., figures: ..., exclusions: none}
```

All numbers above are **illustrative placeholders to be replaced by the researcher and advisor before the tag**; the plan fixes the procedure (file, tag, hash of code and contracts), not the values. Any deviation after the tag is reported as a deviation in the paper.

### 17.4 Harness

```bash
qtiming-bench run --suite benchmarks/families --contracts all --policies eq,sync,exp \
                  --repeat 5 --timeout 60 --out results/<run-id>/
qtiming-bench report results/<run-id>/ --figures paper/figs/ --tables paper/tables/
qtiming-bench diff   --runs 10000 --seed 1 --out results/<run-id>/diff/        # H1 differential
qtiming-bench truth  --suite benchmarks/families --out benchmarks/families/     # exhaustive ground truth (H2)
```

- One row per `(program, contract, policy, repetition)` in Parquet, with git commit, contract hashes, Python, Qiskit, Z3 and JDK versions, CPU model and the tier that resolved each obligation.
- Timing: 5 repetitions, median and interquartile range; the machine specification is recorded.
- Figures: plain matplotlib scripts in `paper/figs/`, each reading only from the Parquet files. No hand-edited number enters the paper.
- Determinism: identical inputs give identical verdicts (property 12); only timings differ.

### 17.5 Outputs

Tables: verdict distribution per contract; H1 and H2 summaries; tier mix; assumption census (count of verdicts by weakest class); portability matrix. Figures: scaling plot, heatmap, policy-cost bars, evidence fit. A machine-readable `claims.json` maps each paper claim to the Parquet query that produces it, used by the artifact README (Section 19.2).

---

## 18. IBM evidence pipeline

The IBM contract has the weakest evidence of the four: the join behaviour for unequal arms is documented only for an older stack, and the feedforward value is a vendor figure. The evidence pipeline replaces guesses with measured parameters, starting with data that needs **no QPU time**.

### 18.1 Primary evidence: `scheduler_timing` from dry runs (decision D8)

Jobs submitted with `dry_run=True` are scheduled and validated but not executed; their metadata includes `scheduler_timing`, the scheduler's own timeline of the compiled job **[verify exact option name, availability and metadata schema against current qiskit-ibm-runtime documentation before building the collector]**. This provides, at zero QPU cost:

- the gap between a measurement's end and the start of the first instruction of a conditional block (the feedforward window as scheduled);
- the block durations for `if`/`else` with equal and unequal arms (does the scheduler pad to the longest block, or restart at the join?);
- differences between `measure` and `measure_2`;
- whether any dynamical-decoupling instructions appear inside feedforward windows (this settles finding F12 empirically instead of by assertion).

### 18.2 Collection (`experiments/ibm_dryrun/`)

```text
experiments/ibm_dryrun/
├── circuits.py        # parameterised circuit families (below)
├── submit.py          # builds, transpiles, submits with dry_run=True, stores raw metadata JSON + sha256
├── jobs/              # raw job metadata, one file per job (committed; this is the evidence)
├── README.md          # how to reproduce; account requirements; no secrets in the repo
```

Circuit families (each submitted per backend and per qubit placement):

1. `ff_base`: measure q0, `if` on it applying `x q1`; arms: then = x, else = empty.
2. `arms_equal`, `arms_unequal`: then-arm of length `a`, else-arm of length `b` for `(a, b)` in a small grid (including `a = b`), to detect padding versus restart.
3. `meas_variant`: the same with `measure` and with `measure_2`.
4. `placement`: measured qubit and consumer qubit on the same and on different regions (tier detection).
5. `two_branches`: two sequential `if` blocks (IBM allows several, not nested) to test whether blocks restart independently.

Reproducibility: every job file records backend name, `qiskit` and `qiskit-ibm-runtime` versions, transpiler options, circuit QPY hash, submission date, and the raw `scheduler_timing`. No credentials are stored. The collector refuses to run if it detects that `dry_run` is not honoured (a safeguard against spending QPU time).

### 18.3 Ingestion (`qtiming.evidence`, Section 7.7)

`qtiming evidence report jobs/*.json` prints observed feedforward windows and join behaviour per circuit family. `qtiming evidence ingest jobs/*.json --out evidence.patch.toml` produces a contract patch with provenance class `sched` (decision documented in Section 7.7: exact for those jobs, not a bound over all jobs; cannot discharge hard obligations). The patch sets:

- `ff.default` (and `ff.mid`, `ff.<tier>`): `lo = min`, `hi = max` over observed jobs, `n` recorded;
- `personality_params.ibm.join_behavior`: `pad_to_longest_block` if every unequal-arm job shows block durations equal to the longest arm, `restart_at_join` if every one shows actual arm durations; if mixed, the patch refuses to choose and reports the conflict;
- `personality_params.ibm.block_start`: from the observed start times of arm resources.

The IBM executor personality and the graph builder read these parameters, so evidence changes behaviour in both implementations at once, which the differential tests then exercise.

### 18.4 Optional redesigned phase probe (`experiments/ibm_probe/`) (finding F22)

Purpose: confirm physically that the scheduled timing equals the real timing, and measure whether the timeline diverges between outcomes. The v1 design swept delays 0 to 1000 ns. At a calibrated detuning of order a few kHz the accumulated phase `2*pi*df*t` at 100 ns is about a milliradian, far below shot noise at a few thousand shots. Redesign:

1. **Delay sweep into tens of microseconds** (illustrative points: 0, 5, 10, 20, 40 us) so that the accumulated phase is a measurable fraction of a radian (illustrative: `df = 5 kHz`, `t = 20 us` gives about 0.63 rad).
2. **Same-job standard Ramsey** on the spectator qubit with no branch, in the same job as the branch circuits, to measure `df` under the same calibration and drift.
3. **Branch circuits** as in v1: control measured mid-circuit, arm A one `x` on a third qubit, arm B a `delay[d]` plus `x`; spectator in superposition; post-select shots by the control's outcome and fit the Ramsey fringe per outcome subset.
4. **DD on and off.**
5. **Interpretation.** Phase difference between the outcome subsets, divided by `2*pi*df`, estimates the timeline difference between arms. Padded arms give no difference at any `d`; a diverging timeline gives a difference growing with `d`.
6. **Analysis.** Least-squares fringe fits with bootstrap confidence intervals; results stored with raw counts. Contract tagging: a measured value is entered as `mmax(n)` with `n` the number of independent runs and an explicit confidence interval, never as a certified bound.

Status: proposed method, untested, optional. It is run only after the dry-run evidence exists, and only the combinations the dry run could not settle.

### 18.5 Budget (finding F30)

| Item | Value |
| --- | --- |
| Primary evidence (dry runs) | no QPU time |
| IBM Open Plan | 10 minutes of QPU time per rolling 28 days **[verify]**; ibm_kingston available on the Open Plan |
| One-time opt-in | 180 minutes for 12 months, requires a non-trial account that has used 20 minutes **[verify]** |
| Optional probe, circuit count | illustrative: 5 delays x 8 phases x 2 DD settings plus Ramsey controls, about 100 circuits |
| Optional probe, shots | illustrative: 2,000 per circuit |
| Optional probe, QPU time | estimate before running: submit 10 circuits with `dry_run=True` and read the estimated duration from the metadata **[verify availability]**, then scale; run in one batched job if it fits a single allowance, otherwise split across allowance periods |
| Stored data | raw counts JSON, fitted parameters, job ids, in `experiments/ibm_probe/` |

### 18.6 What each outcome means for the project

- **Padded (scheduler and probe agree):** set the IBM personality to `pad_to_longest_block` with `sched` or `mmax(n)` provenance from the data.
- **Diverging:** set `restart_at_join`; the portability finding (H4) strengthens; the EQ policy on IBM then relies on explicit delays (the elaborator already inserts them).
- **Inconclusive:** keep the documented fast-path padding behaviour, tagged `vendor`, and report the inconclusive result in the threats to validity.

Either clean outcome is publishable as a short empirical note; the dry-run data alone already improves the IBM contract.

---

## 19. Packaging, CI, artifact, documentation, ecosystem, CLI

### 19.1 Packaging

```toml
# pyproject.toml (excerpt)
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "qtiming"
requires-python = ">=3.10"
license = {text = "Apache-2.0"}
dependencies = ["pydantic>=2,<3", "tomli>=2; python_version<'3.11'"]

[project.optional-dependencies]
qiskit = ["qiskit>=2.3,<2.7", "openqasm3>=1.0,<2"]
z3     = ["z3-solver>=4.13"]
synth  = ["z3-solver>=4.13"]          # CSTNU Tool is an external jar, fetched by script
bench  = ["pyarrow", "pandas", "matplotlib"]
dev    = ["pytest", "pytest-xdist", "pytest-cov", "hypothesis", "mutmut", "ruff", "mypy", "import-linter"]
docs   = ["mkdocs-material"]

[project.scripts]
qtiming = "qtiming.cli.main:main"
qtiming-bench = "qtiming.cli.main:bench_main"

[project.entry-points."qiskit.transpiler.plugin"]   # optional pass-manager stage plug-in
...
```

The default install (`pip install qtiming`) gives the core, contract loader, elaboration, graph, Tier 0 and Tier 1. `pip install "qtiming[qiskit,z3]"` gives the complete verification pipeline. A missing optional dependency produces a clear message naming the extra, not an import error.

### 19.2 CI (GitHub Actions)

| Job | Trigger | Steps | Budget |
| --- | --- | --- | --- |
| `lint` | every push | ruff, `mypy --strict` on `core/ solve/ graph/ oblig/`, import-linter (all five contracts) | 2 min |
| `test` | every push | layers 1, 2, 3, 6 on Python 3.10, 3.12, 3.14 (3.11 and 3.13 weekly), Linux plus macOS plus Windows smoke | 8 min |
| `qiskit-compat` | weekly | tests against Qiskit 2.3, 2.6.2 and Qiskit main (allowed to fail with a report) | 10 min |
| `oracle` | nightly | fetch CSTNU Tool v7.1 jar and verify SHA-256; Prob-in-Ctrl submodule; layer 5 | 25 min |
| `diff` | nightly | layer 4, 100,000 hypothesis examples, per personality | 60 min |
| `q1sim` | nightly | separate Python 3.12 venv, q1simulator cross-check | 10 min |
| `mutation` | monthly | mutmut on `solve/`, `oblig/`, `core/time.py`, `dispatch/` | 3 h |
| `bench-smoke` | PRs touching `solve/`, `graph/`, `dispatch/` | 10 benchmarks, compare check time to main (fail above 25% regression) | 6 min |
| `docs` | push to main | build mkdocs, link check | 4 min |
| `release` | tag `v*` | sdist and wheel to PyPI (trusted publishing); Docker image to GHCR (amd64 and arm64); Zenodo webhook | 20 min |

### 19.3 Artifact

```text
artifact/
├── Dockerfile          # python:3.12-slim + JDK 21; pinned requirements.lock; CSTNU Tool jar by SHA-256
├── vm/build.sh         # Ubuntu 24.04 VM recipe, for committees that prefer a VM
├── fetch_cstnu.sh      # downloads v7.1, checks SHA-256 (never vendored)
├── smoke.sh            # under 30 min: install, 10 benchmarks, 1 counterexample replay, 1 evidence ingest
├── core.sh             # under 8 h: every table and figure from cached IBM data
├── full.sh             # everything, including the 100,000-example soundness run
└── README.md           # claim -> command -> expected output, from claims.json
```

Cached IBM evidence (raw `scheduler_timing` files and probe counts) ships as data so reviewers never need hardware access or credentials. Docker and VM images are built in CI and the smoke script is run inside them.

### 19.4 Documentation site (mkdocs-material)

Pages: quickstart; the contract specification (this document's Section 7, with the four instances and their sources); the annotation reference; "how to write a contract for your lab"; one tutorial per benchmark family; personality specifications (`docs/personality-spec/`); theory notes (`docs/theory/`, including the DC rule table and SC derivation); verdict and report reference; FAQ ("why not UPPAAL", "why is my verdict PROVED-UNDER", "why does O4 not flag fixed idle").

### 19.5 Ecosystem integration

- **Qiskit passes** (`qtiming.qiskit_pass`): `TimingCheck` (analysis pass; writes the `Verdict` into the pass manager's property set under `"qtiming_verdict"`), `EqualizeBranches` (transformation pass using EQ elaboration), `StripTimingAnnotations`. A preset pass-manager stage plug-in adds them with one line.

```python
from qiskit.transpiler import PassManager
from qtiming.qiskit_pass import TimingCheck, EqualizeBranches, StripTimingAnnotations
pm = PassManager([EqualizeBranches(contract="q1.toml"),
                  TimingCheck(contract="q1.toml", fail_on="refuted"),
                  StripTimingAnnotations()])
```

- **Qiskit ecosystem listing** once v0.2 works (submitted as a new project).
- **Standards outreach:** contract vocabulary shared with the OpenQASM TSC and QDMI discussions after the first paper.
- **Citation:** `CITATION.cff` with ORCID; Zenodo concept DOI in the README; version DOI cited in each paper. The repository is public from early November 2026 under Apache-2.0 so the six-month public history JOSS requires starts immediately.
- **Semantic versioning;** the contract schema has its own version (`qtiming-contract/0.2`) so contracts evolve independently of code; the loader supports the previous schema for one minor version with a migration tool.

### 19.6 CLI reference

| Command | Purpose | Key options |
| --- | --- | --- |
| `qtiming check PROG --contract C` | verify; exit code by verdict | `--policy {eq,sync,exp}`, `--format {text,json,sarif,html}`, `--out FILE`, `--assume KEY=LO:HI[:CLASS]`, `--timeout S`, `--first-failure`, `--no-window`, `--no-tier1`, `--strict-proved` (treat PROVED-UNDER as failure), `--jobs N`, `--target BACKEND_OR_SNAPSHOT` |
| `qtiming explain PROG --contract C` | print the elaborated program, graph summary, obligations | `--elaborated`, `--graph dot`, `--obligations` |
| `qtiming lint PROG --contract C` | front-end and static lint only | `--format sarif` |
| `qtiming replay CEX.json PROG --contract C` | replay a counterexample in the executor | `--trace`, `--format html` |
| `qtiming synth PROG --contract C` | Tier 3: consistency, SC, DC, repair feasibility | `--sc`, `--dc`, `--cstnu`, `--delta-search` |
| `qtiming repair PROG --contract C` | counterexample-guided delay suggestions (re-verified) | `--max-iters`, `--diff` |
| `qtiming contract validate|show|diff|patch` | contract tooling | `--target` |
| `qtiming evidence report|ingest JOBS...` | IBM evidence | `--out` |
| `qtiming-bench run|report|diff|truth` | evaluation harness | Section 17.4 |

Exit codes: `0` PROVED or PROVED-UNDER (unless `--strict-proved`), `1` REFUTED, `2` usage error or lint error, `3` UNKNOWN, `4` internal error (including replay mismatch). SARIF output integrates with GitHub code scanning and editors.

---

## 20. Build sequence

Phases are ordered by dependency, not by calendar. Each phase ends in a **gate**: a command (or small set of commands) whose output decides pass or fail, plus exit criteria. Nothing in a later phase starts its deliverables until the gates of the phases it depends on have passed, except where a stream is marked parallel. There are no hour or week estimates by design.

### 20.1 Phase list

#### P0: Bootstrap

- **Deliverables.** Repository skeleton from Section 4.1 (empty packages, `py.typed`), `pyproject.toml` with extras, `.importlinter` (five contracts), ruff and mypy configuration, pytest configuration with the test directory layout, pre-commit, GitHub Actions `lint` and `test`, Apache-2.0 `LICENSE`, `NOTICE`, `CITATION.cff`, `CONTRIBUTING.md`, `docs/` stub, `artifact/` stub, `prereg/` stub, `docs/personality-spec/` stubs.
- **Gate.** `ruff check . && mypy --strict src/qtiming/core && lint-imports && pytest -q` all green on the skeleton; CI green on Python 3.10, 3.12, 3.14.
- **Exit.** A new clone installs with `pip install -e ".[dev]"` and the gate commands pass.

#### P1: Core data model

- **Deliverables.** `core/time.py`, `core/provenance.py`, `core/labels.py`, `core/ast.py`, `core/errors.py`, `core/ids.py` as in Section 5, with unit tests.
- **Gate.** `pytest tests/unit/core -q` including: the rounding-by-role table at boundary values; the rounding soundness property (hypothesis); provenance combination and `can_discharge` tests; label algebra tests; `mypy --strict src/qtiming/core`; `lint-imports` (core imports stdlib only).
- **Exit.** Every finding F7, F8, F14 (data-model part), F29 has a unit test that fails on the v1 behaviour.

#### P2: Contract

- **Deliverables.** `contract/schema.py`, `loader.py`, `compat.py`, the four instance files with per-instance README (sources, placeholders), `target_import.py` (Qiskit-dependent, with an offline snapshot fixture), SHA-256 canonicalisation, `--assume` overrides.
- **Gate.** `qtiming contract validate src/qtiming/contract/instances/*.toml`; `pytest tests/unit/contract -q` including: the Q1 consistency fixture (`149 + 239 = 388 ns`), missing-field tests (UNKNOWN markers, not defaults), the policy-compatibility table (one test per cell), msigma and pctl `hi` rules, Target-versus-contract conflict error.
- **Exit.** All four contracts load; placeholders are flagged; every number in the instance files has a source string.

#### P3: Front end (parallel with P4)

- **Deliverables.** `frontend/qiskit_fe.py`, `qiskit_expr.py`, `annotations.py`, `serialise.py`, `stretch.py`, `lint.py`, `qasm3_fe.py`, and the `StripTimingAnnotations` pass.
- **Gate.** `pytest tests/unit/frontend tests/golden/frontend -q`: annotation round trips through QASM3 and QPY (including a circuit carrying a second annotation namespace); `expr` conditions (parity, comparison, boolean); `Var`/`Store`; `else`; `SwitchCaseOp` rejected on IBM; `BoxOp` with `Duration` and `Stretch`; `measure_2`; the two front ends produce equal ASTs on the shared fragment; IBM lint goldens.
- **Exit.** The teleportation benchmark of Appendix A loads from Qiskit, QPY and OpenQASM 3 text and yields the same AST.

#### P4: Personality specifications (parallel with P3)

- **Deliverables.** `docs/personality-spec/{ibm,q1,artiq,qua}.md`: normative dispatch rules (Section 9.4), named parameters with defaults and provenance, and **hand-computed golden traces** (worked examples with exact times) stored in `tests/personality/<name>/golden/*.yaml`.
- **Gate.** Advisor review checklist signed (each unpublished behaviour is a named parameter; each documented behaviour cites its source); `pytest tests/personality --collect-only` finds at least 6 golden cases per personality.
- **Exit.** The specification is frozen; later changes go through the decision log.

#### P5: Reference executor

- **Deliverables.** `exec/engine.py`, `oracle.py`, `state.py`, `trace.py`, the four personalities, the executor's own `sed_simulate`, replay API, `q1sim_bridge.py`.
- **Gate.** `pytest tests/personality -q -k executor` (all golden traces reproduced exactly with `Fraction` times); `lint-imports` (executor independence); q1simulator cross-check passes on the supported subset in its separate venv.
- **Exit.** The executor can run any elaborated program under `Fixed`, `Random`, `Extreme`, `Exhaustive` oracles. (P5 needs the AST from P1 and contracts from P2; elaboration is not required if tests build elaborated programs directly.)

#### P6: Elaboration and graph builder

- **Deliverables.** `elab/*` (EQ, SYNC, EXP, Q1 set_cond, loops by unrolling and capped `while`, calls, within), `graph/lteg.py`, `builder.py`, `invariants.py`, `dispatch/{ibm,artiq,q1,qua}.py`, `graph/export.py`.
- **Gate.** `pytest tests/personality -q -k graph` (same golden traces, from the graph side); invariants I1 to I7 hold on all benchmark-shaped programs; **first differential run**: `pytest tests/differential/test_graph_vs_executor.py -q` on 1,000 generated programs per personality: `evaluate(G, omega, theta)` equals the executor's event times exactly.
- **Exit.** T8 (conformance) is tested for all four personalities; elaboration idempotence holds.

#### P7: Obligations, Tier 0, Tier 1, verdicts (basic)

- **Deliverables.** `oblig/*` (O1 to O9, O4a, lint rules), `solve/concrete.py`, `interval.py`, `dispatcher.py`, `verdict/model.py` and the lattice, policy-compatibility rejections.
- **Gate.** Appendix A.1 to A.5 reproduced: `qtiming check benchmarks/families/teleportation/tp_basic --contract ibm_heron --policy eq` gives PROVED-UNDER with margin 2400 ns and max safe `ff` of 3000 ns (Tier 1 proved; the max-safe query uses bisection and so completes at P8); property tests 1 (soundness, Tier 0/1 only), 8, 10, 11 pass.
- **Exit.** Tier 1 never reports REFUTED (asserted by test).

#### P8: Tier 2 SMT, counterexamples, replay

- **Deliverables.** `solve/smt.py`, `smt_o5.py`, `cache.py`, `pool.py`; counterexample extraction with rational values; `verdict/minimise.py`; replay through the executor; parametric margins and max-safe by bisection.
- **Gate.** Appendix A.6 reproduced: the ARTIQ variant is REFUTED with O1 underflow, the counterexample replays to `RTIOUnderflow` at the same event; the free-time-point STN encoding of the same program (kept as a test fixture `tests/fixtures/free_stn_false_proof.py`) reports "consistent", demonstrating the false proof; H1 smoke: `qtiming-bench diff --runs 1000 --seed 1` shows zero violations on PROVED or PROVED-UNDER; vertex-lemma test (exhaustive vertex enumeration agrees with Tier 2 on snap-free programs); O5 triple agreement (`sed_simulate`, executor, symbolic).
- **Exit.** Every REFUTED is replayed; replay mismatch is `I-REPLAY-MISMATCH` and withheld.

#### P9: Reports, RUS, CLI

- **Deliverables.** `verdict/render_*`, `verdict/rus.py`, `cli/*`, SARIF and HTML timeline, exit codes.
- **Gate.** `pytest tests/golden/reports -q` (text, JSON, SARIF snapshots; SARIF validated against the 2.1.0 schema); the RUS table of Section 13.5 reproduced exactly; end-to-end `qtiming check` on all four contracts for the teleportation family.
- **Exit.** CLI reference of Section 19.6 is implemented and documented.

#### P10: Windowing and summarised loops

- **Deliverables.** `graph/window.py` (cut finder enforcing the five rules), window summaries, periodic-cut loop summarisation, `--no-window`.
- **Gate.** `pytest tests/differential/test_window_vs_whole.py -q`: equal verdicts on every program where both are feasible; cut-refusal tests (cross-cut obligation, non-canonical queue state, missing join); H3 smoke on a 20-round repetition code.
- **Exit.** T4 has a written proof or a documented list of conditions under which windowing is disabled.

#### P11: Tier 3 synthesis and controllability

- **Deliverables.** `solve/synth/{stn,sc,stnu_dc,bruteforce_dc,cstnu_tool,relax,rigid}.py`, optional `rul.py`, `repair/*`.
- **Sub-tasks in order.** (1) STN plus witness; (2) SC rewrite plus brute-force SC test; (3) `bruteforce_dc`; (4) transcribe Morris 2014 rules into `docs/theory/dc-rules.md` and implement `stnu_dc.py`; (5) Prob-in-Ctrl harness; (6) CSTNU Tool bridge with the pinned v7.1 jar (read the 7.1 README for the main class and options); (7) relaxation, rigid detector, T5 property test; (8) `qtiming repair`; (9) optional RUL-minus.
- **Gate.** `pytest tests/oracle -q`: agreement on all 621 Prob-in-Ctrl networks; three-way agreement on generated networks; T5 property test passes; `qtiming repair` fixes the ARTIQ example of Appendix A and the patched program is re-verified PROVED-UNDER.
- **Exit.** `stnu_dc.py` flag `unverified` removed only after the gate passes.

#### P12: Qiskit passes

- **Deliverables.** `qiskit_pass/{timing_check,equalize,strip,plugin}.py`.
- **Gate.** `pytest tests/unit/qiskit_pass -q`: `TimingCheck` stores the verdict in the property set; `EqualizeBranches` output is re-verified (EQ obligations hold) on every EQ benchmark; `StripTimingAnnotations` idempotent and content-preserving; preset pass-manager plug-in works on Qiskit 2.6.2.
- **Exit.** Documented examples run in CI.

#### P13: Benchmarks and evaluation harness

- **Deliverables.** `benchmarks/families/*` (about 60 programs), external programs with licences, `ground_truth.json` generation, `qtiming-bench`, report generators, `prereg/` file, `claims.json`.
- **Gate.** `qtiming-bench run --suite benchmarks/families --contracts all --policies eq,sync,exp --repeat 5` completes; golden expectations match; `qtiming-bench truth` yields ground truth for all small programs; the pre-registration file is committed and tagged `prereg-1` **before** the evaluation run; the H1 full run reports zero violations (or the failure is reported and fixed with the test added).
- **Exit.** Tables and figures regenerate from Parquet with one command.

#### P14: IBM evidence pipeline (can start as soon as P2 and P3 exist; start early)

- **Deliverables.** `experiments/ibm_dryrun/*`, `evidence/*`, collected `jobs/*.json`, patched `ibm_heron.toml`, optional probe.
- **Gate.** `qtiming evidence ingest experiments/ibm_dryrun/jobs/*.json --out evidence.patch.toml` reproducibly yields the patch from the committed raw files; the patched contract changes both the graph builder and the executor (differential test re-run); the collector's `dry_run` safeguard test passes.
- **Exit.** The IBM personality's join behaviour is either calibrated or explicitly marked `vendor` with the inconclusive result recorded.

#### P15: Theory track (parallel from P1)

- **Deliverables.** `docs/theory/` write-ups: definitions, T1, T2, T3, T6, T10 proofs; T4, T5, T7 proofs or reduced statements; SC derivation; DC rule table; optional Lean artefacts.
- **Gate.** Advisor review; every theorem cited in the code comments exists in `docs/theory/` with a status.

#### P16: Artifact, docs, release

- **Deliverables.** `artifact/*`, mkdocs site, Docker and VM images, PyPI release, Zenodo record.
- **Gate.** `docker build -f artifact/Dockerfile . && docker run qtiming-artifact ./smoke.sh` completes in under 30 minutes on a laptop; `mkdocs build --strict`; `twine check`; tagged release with changelog.
- **Exit.** The artifact README maps each paper claim to a command and expected output.

#### P17: Pre-submission checks

- **Tasks.** (1) Focused arXiv sweep of quant-ph and cs.PL from October 2026 onward for new work on timing of dynamic circuits (named closest works: qlin 2611.19618, qconform 2610.10427, DART-Q 2605.09142, GRAMPUS "...with Measurement"); (2) read QaiJi IR full text; (3) read the TqCCS chapters; (4) re-verify every **[verify]** item in this document (list generated by `grep -n "\[verify" docs/plan`); (5) one-line checks of unverified claims about CoqQ, QWIRE, SQIR/VOQC, Silq, Qafny; (6) re-check IBM block-restart statement and LabOne Q padding; (7) mutation score target; (8) pre-registration deviation list.
- **Gate.** A written related-work delta memo and a closed **[verify]** list.

### 20.2 Critical path

```text
P0 -> P1 -> P2 -> { P3 || P4 } -> P5 -> P6 -> P7 -> P8 -> P9 -> P10 -> P13 -> P16 -> P17
```

P5 (executor) is placed before P6 (builder) deliberately: the executor is written from the personality specification first, so the builder cannot unconsciously copy it (principle 9). P8 (Tier 2) is the first point where REFUTED exists, and the soundness differential becomes meaningful. P11 (Tier 3) is **off** the critical path for soundness claims; it is on the critical path for `qtiming repair`, the policy-feasibility claims and the oracle-validated controllability results.

### 20.3 Parallelisable streams

| Stream | Phases | Depends on | Notes |
| --- | --- | --- | --- |
| A. Specification and executor | P4, P5 | P1, P2 | independent of the front end |
| B. Front end | P3 | P1, P2 | |
| C. Theory | P15 | P1 (definitions), later P6 (conformance), P10 (cuts) | writes continuously |
| D. Evidence | P14 | P2, P3 | data collection depends on account availability, so start the dry-run collection as early as P3 allows |
| E. Controllability algorithms | P11 steps 1 to 6 | P1 only (pure algorithms on abstract networks) | steps 7 and 8 need the LTEG (P6) and Tier 2 (P8) |
| F. Docs and artifact | P16 drafts | any | keep `smoke.sh` working from P0 on |

---

## 21. Risks, mitigations and decision log

### 21.1 Risks

| Risk | Likelihood | Impact | Mitigation | Fallback |
| --- | --- | --- | --- | --- |
| Builder and executor share a misunderstanding of a personality (both wrong the same way) | medium | false proofs that survive the differential test | written specification reviewed by the advisor; golden traces hand-computed from documentation; independent implementation (import-linter); q1simulator and (later) hardware evidence | restrict claims to "relative to the documented model"; report which parameters are undocumented |
| Bug in the Tier 2 encoding or Tier 1 abstraction | medium during development | false proofs | Tier 1 only proves; Tier 2 vs executor differential; vertex-lemma exhaustive oracle; mutation testing; cone invariance and tier agreement properties | disable Tier 1 (`--no-tier1`) to rely on Tier 2 alone |
| Own DC solver (Morris) has a bug | high during development | wrong repair or feasibility claims (not verification) | 621-network oracle, CSTNU Tool, brute force; flagged `unverified` until the gate | delegate to CSTNU Tool |
| Scenario blow-up (many relevant propositions) | medium | UNKNOWN on QEC benchmarks | windowing; cone of influence; caching; Tier 1 proves most | report UNKNOWN honestly; split by annotation |
| CSTNU Tool timeouts, format or option changes | medium | gaps in Tier 3 | pin v7.1 by SHA-256; 60 s timeout; read README at P11 step 6 | rely on own DC and brute force for small cases |
| Qiskit API churn (annotations, control flow) | medium | front end breaks | weekly compatibility job against Qiskit main; adapters isolated; pinned range for the artifact | pin a known-good Qiskit range |
| Vendor latencies unpublished or placeholder | certain | weak verdicts | provenance typing; max-safe parametric output; placeholders flagged | frame as a finding: what vendors must publish |
| IBM scheduler metadata schema differs from assumption | medium | evidence pipeline delayed | capture real files first; parser uses `extra="allow"` until schema is known | manual transcription of the few needed values |
| IBM behaviour changes (stack versions) | medium | contract stale | record runtime versions in evidence; contract carries evidence ids | re-run dry-run collection |
| Soundness proof of windowed composition fails | low to medium | weaker technical claim | prove the restricted case (full joins, canonical state) first | disable windowing; restrict benchmarks |
| "It is just STNU / just UPPAAL" reviewer objection | medium | positioning | Section 22: fixed-dispatch verification versus controllability is itself a contribution (F1); UPPAAL as an optional baseline back end | add UPPAAL baseline comparison |
| Closest-work movement (qlin, qconform, Aalborg, GRAMPUS with measurement) | medium | novelty narrows | pre-submission sweep (P17); claim only the precise statement of Section 22.2 | reposition on multi-vendor policies and provenance |
| False-alarm rate too high for Tier 1+2 on real programs | medium | usability | H2 measured; `--assume` for what-if; margins reported | tune obligations' defaults (O4 variation G) |
| Scope too large for one researcher | high | late artifact | strict phase gates; build order puts a trustworthy core first; streams are independent | ship the verification core (P0 to P10, P13, P16) and mark Tier 3 modules as experimental |

### 21.2 Decision log

| # | Decision | Chosen | Rejected | Reason | Finding or source |
| --- | --- | --- | --- | --- | --- |
| 1 | Core semantics | verification of a fixed dispatch (universal check over omega and theta) | STN consistency or DC as the safety criterion | free time-points delay events hardware never delays: false PROVED | F1, F2 |
| 2 | Time-defining structure | dispatch edges define times as max of in-edges; obligations only checked | all constraints as difference constraints | max is not a difference constraint; obligations must not move events | F2 |
| 3 | Where controllability lives | separate Tier 3 module, off the verification path, enforced by import-linter | using DC/SC in the checker | answers "could any dispatcher succeed", not "does this one" | F1, F5 |
| 4 | Strong controllability | Vidal-Fargier rewrite onto activation points | contingent-link-to-requirement-edge | that is pseudo-controllability, unsound for SC | F3 |
| 5 | Per-scenario STN | demoted to Tier 0 concrete evaluation | calling it strong controllability | schedule would depend on the scenario (weak controllability) | F4 |
| 6 | Research conjecture "EXP safe iff DC" | withdrawn; replaced by T5 and T6 | keeping it | false unless dispatch is rigid | F5 |
| 7 | Verification tiers | 0 concrete, 1 interval abstraction (proof only), 2 exact SMT | A/B/C1/C2/D controllability tiers | match the semantics; sound and complete for the bounded program | F28 |
| 8 | Latency domain in SMT | real-valued theta (QF_LRA), rational counterexamples | integers | latencies are continuous; integers miss counterexamples | F27 |
| 9 | Solver | Z3 | CVC5, custom | Python API, optimisation, `IsInt`, mature | |
| 10 | Unbounded latency in Tier 2 | SAT gives UNKNOWN naming the key, not REFUTED | treating hi = infinity as a refutation | a missing number is not a counterexample | F31 |
| 11 | O4 definition | variation of a gap across executions | absolute idle with G = 0 | flags every circuit | F6 |
| 12 | Absolute idle | optional advisory O4a, off by default | dropping it | some users want it | F6 |
| 13 | Rounding | by role (uncertainty outward; upper requirements down; lower requirements up; exact must be exact) | all lo down, all hi up | wrong direction for requirements | F7 |
| 14 | Provenance | structured record plus assumption set; weakest class as summary; msigma/pctl never give a bound | IntEnum minimum | loses sources; unsafe bounds | F8 |
| 15 | Provenance class for evidence | new class `sched` between `mmax` and `cyc`; cannot discharge hard obligations | `cyc` or `mmax` | a scheduler output is exact for a job, not a bound for all jobs | D8, F22 |
| 16 | Monotonicity property | only for a fixed elaborated program | monotonicity across elaborations | EQ waits depend on `hi` | F9 |
| 17 | Conditions | one derived proposition per condition evaluation, observed at the last operand | duplicating bodies per disjunct | scales; sound over-approximation | F13, F29 |
| 18 | Annotation bit references | strings | `Clbit` objects | not serialisable | F14 |
| 19 | Annotation carrier | `BoxOp` annotations with a `StripTimingAnnotations` pass | new OpenQASM syntax; leaving boxes in | round-trips today; IBM rejects box | F11 |
| 20 | IBM contract data | read dt, alignments, durations from `backend.target` | hard-coded numbers | per-backend values; `measure` and `measure_2` differ | F20 |
| 21 | IBM join behaviour | named parameter, default `pad_to_longest_block` tagged `vendor`, calibrated from `scheduler_timing` | assuming padding | documented only for the old stack | F21 |
| 22 | IBM primary evidence | `dry_run=True` `scheduler_timing` | phase-drift probe first | no QPU cost; probe SNR was too low | F22 |
| 23 | Q1 numbers | 212 to 239 ns trigger network, 252 ns busy, 149 ns base, 24 ns RTP, 388 ns example | 160/250/472 ns | not in current docs | F15 |
| 24 | Q1 `set_cond` | per-instruction `else_time` modelling; EQ native only when counts and durations align | one `else_duration` per branch | documented per skipped RT instruction | F16 |
| 25 | ARTIQ O5 | exact SED lane, collision, busy rules; drops are logged not raised | "more than 8 events per coarse slot" | not the hardware rule | F17 |
| 26 | QUA align gaps | contract intervals, `vendor`, flagged placeholders | inventing numbers silently | unpublished ("a few cycles") | F18 |
| 27 | CSTNU Tool | v7.1 jar, `java -cp` Checker class, support nodes, SHA-256 pin, subprocess only | JPype, vendoring, v7.2 | LGPL isolation; 7.2 unreleased; GUI on `-jar` | F19 |
| 28 | EQ implementation | barrier plus delay of `hi` plus arm padding; no-stall obligation O2b | requirement edge `>= hi` | on reactive hardware the program can only delay, not constrain | Section 8.2 |
| 29 | Obligation severity | `safety` (REFUTED on failure) versus `advisory` (finding only); `hard` orthogonal | hard/advisory as the only flag | separates evidence strength from consequence | Section 10.1 |
| 30 | Snap nodes | optional ceil-to-grid on dispatch nodes (ARTIQ coarse clock) | ignoring grids in dispatch | O8 and ARTIQ timestamps | Section 9.1 |
| 31 | Windowing | cuts only at full joins with five checked rules; no cross-cut obligations | arbitrary cuts | soundness of composition | F26 |
| 32 | Loop summarisation | periodic cut of one iteration window | invariant-only summarisation | reuses window soundness | Section 8.6 |
| 33 | Counterexamples | rational `theta`, minimised, replayed before reporting | integer or endpoint-only `theta` | exactness; vertex lemma allows endpoints when snap-free | F27, T10 |
| 34 | `within` semantics | every resource in the body must start in time (`all_started`), option `mode=first` | first resource only | conservative; matches reaction deadline intent | Section 8.7 |
| 35 | DC implementation plan | brute-force oracle, Morris 2014, optional RUL-minus; rule table transcribed from the paper in P11, not copied into this plan | reproducing rules from memory here | transcription risk | F1 (Tier 3), D12 |
| 36 | RUS formulas | exhaust term included; `m = floor((D - T_post)/T)`; exact `Fraction` | v1 formulas | inconsistent with the report's example | F23 |
| 37 | Python and Qiskit support | core 3.10 to 3.14; qiskit `>=2.3,<2.7` tested on 2.6.2 | 3.11 to 3.13 | Qiskit 2.6.2 requires 3.10 or newer | F10 |
| 38 | Contract schema version | `qtiming-contract/0.2` with migration from 0.1 | silently changing 0.1 | contract changes are semantic | Section 7 |
| 39 | Executor independence | specification first, executor built before the builder, import-linter forbids sharing | shared helper library | tautological agreement otherwise | principle 9 |
| 40 | Language | Python | Rust, OCaml | Qiskit ecosystem, reviewer accessibility, small graphs | v1 decision, kept |
| 41 | Mechanised proofs | optional | critical path | solo researcher | v1 decision, kept |
| 42 | Loops | bounded `for`, capped `while` | unbounded `while` | finite verdicts | v1 decision, kept |
| 43 | Contract format | TOML plus pydantic | YAML; extend `Target` | strict, human-editable; `Target` lacks latency | v1 decision, kept |
| 44 | Layering of `graph` and `dispatch` (P6) | `dispatch` imports `graph`: `oblig > dispatch > graph > elab` | peers `graph \| dispatch` | the personality builders subclass the common frontier builder; peers would need a second IR for edge specs | P6 ruling |
| 45 | Golden-case format (P4) | JSON with a small program DSL, hand-computed expected times | YAML | stdlib only, no new dependency, same review value | P4 ruling |
| 46 | Q1 model scope (P4) | one sequencer, qubits not distinguished, `barrier` is a no-op, arms hold RT instructions only | multi-sequencer `wait_sync` | needs the topology contract; named limit in `docs/personality-spec/q1.md` | P4 ruling |
| 47 | IBM `block_start = per_resource` (P4) | named parameter, refused by both stages | implementing it | no documented behaviour to pin it against | P4 ruling |
| 48 | Q1 EQ elaboration (P6) | wait of `hi` plus a check that both outcome totals are equal, else `E-ELAB-Q1-NOT-EQUALISABLE` | automatic dummy-instruction rewriting search | the rewriting search is an open design problem (plan 8.5); refusing is sound | P6 ruling |
| 49 | Obligation tier for O7 (P7) | Tier 1 proves the Appendix A.4 O7 (spread 0) | Tier 0 as in the A.4 table | the block start is `max(ready, valid)`, so theta is in the cone; same verdict | P7 ruling |
| 50 | Tier 2 not yet built (P7) | what Tier 1 cannot prove is UNKNOWN with the reason `Tier 2 not built`; only Tier 0 refutes | guessing a verdict | keeps PROVED sound; REFUTED from Tier 2 lands in P8 | P7 ruling |
| 51 | Unchecked obligation kinds (P7) | every verdict lists `not_checked`: O4a, O6, O8, O9, O7 for SYNC with a spread bound | silent omission | PROVED must never read as covering them | P7 ruling |
| 52 | Gate durations for non-Target contracts (P7) | `--assume durations.NAME=ns`; illustrative values only in the unofficial IBM fixture | inventing vendor numbers in shipped contracts | unpublished numbers stay absent | P7 ruling |
| 53 | q1simulator cross-check and advisor sign-off (P4, P5 gates) | not done: needs a separate Python 3.12+ venv and a person | claiming them | stated as open in the project status | P5 ruling |
| 54 | Replay of a witness that targets a later event (P8) | accepted when the executor HALTS on an earlier violation of the same kind | requiring the same node | RTIOUnderflow and the Q1 halt stop the run first; the program still fails under the witness | P8 ruling |
| 55 | Executor events added so witnesses are replayable (P8) | `bready` (IBM, QUA) and `fstart`/`fend` (QUA false-path wait); the program origin counts as time 0 | leaving them graph-only | replay compares executor times, so every node an obligation names must be an executor event | P8 ruling |
| 56 | O5 symbolic encoding and triple agreement (P8 gate) | not built: Tier 2 returns UNKNOWN for `Events` obligations | a partial encoding | `sed_simulate` (Tier 0) and the executor agree on goldens; the symbolic version is future work | P8 ruling |
| 57 | Parametric margins by `Optimize` (P8) | margins come from Tier 1 or Tier 0; `max_safe` is bisection over full re-checks | Z3 `Optimize` | bisection matches the plan's description; Tier 2 proofs report no margin | P8 ruling |
| 58 | `qtiming-bench diff` H1 smoke (P8 gate) | covered by `tests/property/test_soundness.py` (proved never violated, refuted always replays) | the bench CLI | the harness is P13; the property test is the same check on random programs | P8 ruling |
| 59 | SARIF schema for the P9 gate | the official OASIS `sarif-schema-2.1.0.json` is vendored in `tests/fixtures` and used with `jsonschema` (dev extra) | a hand-written structural check | the gate says "validated against the 2.1.0 schema" | P9 ruling |
| 60 | RUS verdict wiring (P9) | `verdict/rus.py` implements the 13.5 formulas exactly and reproduces the table; `check` does not call it yet | wiring it before `timing.pmin` reaches the elaborator | the front end parses `pmin` but loops are not carried through as RUS nodes; the formulas are tested stand-alone | P9 ruling |
| 61 | Report paths and fingerprints (P9) | paths in reports use `/`; SARIF `partialFingerprints` hash (code, nid, contract sha) | OS-specific paths | snapshots and CI deduplication must not depend on the machine | P9 ruling |
| 62 | HTML report (P9) | static page, inline SVG, no scripts, built from the replayed executor trace | an interactive viewer | meets 13.6; trivially safe to open from CI artifacts | P9 ruling |

---

## 22. Related work and positioning

### 22.1 Positioning table

| Work | What it does | What it does not do | Effect on claims |
| --- | --- | --- | --- |
| **qlin** (arXiv:2611.19618, 2026-11-14, R. Malarchick) | dynamic-circuit compiler with a replay-latency timing model (fixed `t_ff`, serial-controller block model); Lean-proved non-delaying rewrites; timing check on 66 outputs | no intervals or uncertainty, no deadlines or controllability, no multi-vendor policies, no counterexamples | closest work; must be cited and contrasted explicitly; read in full at P17 |
| **qconform** (arXiv:2610.10427, same author) | design-time pulse-program feasibility checker for QICK and Qblox | explicitly no branches and no loops | complementary; our scope starts where it stops |
| **q1asm-simulator** (overshiki, Haskell) | deterministic RT underflow detection for Q1ASM | no latency uncertainty, no policies, not an IR-level check | related tool; possible cross-check besides q1simulator |
| **DART-Q** (arXiv:2605.09142) | decoder deadline and EDF scheduling analysis by simulation | simulation not static proof; decoder side not program side | related for deadline framing |
| **GRAMPUS** (Adams, Bernardy, Perticone, Pope; arXiv:2510.03130) | graded linear type theory with durations; pulse schedules | currently no measurement or branching; a "...with Measurement" TYPES 2026 talk (May 2026, types2026.cse.chalmers.se/slides/47.pdf) shows work in progress | cannot claim "first duration type system"; the measurement-and-branch extension may appear before ours; track it |
| **TqCCS** (Fernandes, MSc, Minho 2019) | timed quantum process algebra with measurement | effect of time on states; no schedule verification, policies or contracts | cannot claim "first timed calculus with measurement" |
| **UPPAAL for quantum protocols** (Christensen et al., CAV 2026) | hand-built timed-automata models of protocols | no automatic IR extraction, no policies or contracts | possible baseline back end; Aalborg is a likely competitor |
| TIDE, QCORE, NVQLink, QuCtrl-BELL | runtime commit boundaries, deadline guards, blocking device calls, fixed feedback phases | no program semantics or static check | substrate our contract describes |
| TUM dynamic-circuit analyses (Fulginiti et al., arXiv:2605.28439, 2606.02018) | logical simplification and constant propagation | no timing | complementary |
| Riverlane control-stack DV (arXiv:2310.05229) | hardware block verification | no program-level deadlines | source of `cert` bounds |
| QaiJi IR (arXiv:2609.29305) | eight-layer IR with a "five-axis semantic contract" | abstract defines no durations, latency bounds, deadlines or timing checker | closest IR-level neighbour for the contract idea; abstract-level check only, read the full text |
| Quantum Orchestras (arXiv:2607.09605), qwp-ert (arXiv:2607.12532, 1911.11247) | untimed denotational semantics; expected runtime | no wall-clock time | baselines for RUS |
| QASM-TS (arXiv:2412.12578) | typed OpenQASM 3 parser | no timing | possible front-end helper |
| Lingua Franca, Giotto, PRET, FlexPRET | deterministic coordination, logical execution time, timed ISA | not quantum | theory we borrow (conditional determinism) |
| eQASM (Fu et al.) | timing-point ISA, issue-rate condition | hardware assumes, does not check | motivates O1 |
| CSTNU Tool, HEATlab Prob-in-Ctrl | (C)STNU DC checkers | not about programs | tools and oracles we use |

### 22.2 Novelty statement

**The first checker for dynamic circuits that verifies deadline, underflow and unpredictable-gap obligations under interval-valued, provenance-typed latencies against multiple vendor branch-timing policies, with replayable counterexamples.**

Supporting statements the paper may make, each tied to this document: (1) verification of a fixed controller dispatch rather than existence of a schedule, with a worked case where the latter gives a false proof (Appendix A); (2) a portable contract vocabulary with structured provenance and a verdict that lists its assumptions; (3) policies as dispatch specifications implemented twice and compared; (4) controllability (SC, DC) as a separate synthesis tool with a stated relation to verification (T5, T6).

Claims that must **not** be made: first timed semantics with measurement; first duration type system; first use of STNU in quantum compilation (to be checked in P17); that the checker models real hardware beyond the documented behaviour.

### 22.3 Pre-submission task

Focused arXiv sweep of quant-ph and cs.PL from October 2026 onward (queries on dynamic circuits, mid-circuit measurement, feedforward latency, timing verification, controllers, STNU, schedule verification), plus the named works above; update this table and the novelty statement; record the sweep date and queries in `paper/related-work-sweep.md`.

---

## 23. Appendix A: worked examples under the fixed-dispatch semantics

Two examples. A.1 to A.6 follow a teleportation-style correction on an IBM-like contract through every stage and end PROVED-UNDER with the correct numbers. A.7 to A.9 show an ARTIQ-like variant that is REFUTED under fixed dispatch, and place the free-time-point (STN or controllability) encoding next to it, to show why that encoding gives a false proof. All gate durations other than measurement and feedforward, and all ARTIQ numbers, are **illustrative**.

### A.1 Input and contract (IBM-like)

Program: measure `q1` into `c1`; then `if (c1) x q2`, inside a box annotated `@timing.policy eq` and `@timing.within 3000ns c[1]` (Section 6.4). A full teleportation circuit has two such corrections in sequence; one is enough to trace the machinery.

Contract values used (illustrative where marked): `dt = 4 ns`; `measure` 1660 ns = 415 dt (a vendor-reported value for one backend; the actual Target value differs per backend); feedforward `ff.default` in `[0, 600] ns` = `[0, 150] dt`, class `vendor` (the lower bound 0 is a placeholder, Section 7.3.1); `x` gate 32 ns = 8 dt (illustrative). `q2` is ready at time 0 (any earlier ready time only adds a term to the barrier's max and does not change the result as long as it is at most the measurement end).

### A.2 Elaboration (EQ, Section 8.2)

- Valid time of `c1` relative to the measurement start: `[415, 565] dt`.
- Arms: then = `x q2` (8 dt), else = empty (0 dt); `d = 8 dt` on `q2`.
- Elaborated: `barrier q1, q2; delay[150 dt] q2; if (c1) { x q2 } else { delay[8 dt] q2 }` (the barrier ties the wait to the measurement's end; the delay is `hi`).
- Synthesised statements are tagged `synth`; the user's first operation in the box is the `x` or its padding.

### A.3 Event graph (dispatch edges, Section 9)

| Node | Kind, resource | Label | Dispatch in-edges | Time (dt) |
| --- | --- | --- | --- | --- |
| n0 | origin | true | none | 0 |
| n1 | start M(q1) | true | n0, weight 0 | 0 |
| n2 | end M(q1) | true | n1, weight 415 | 415 |
| n3 | valid(c1), obs `c1@m2` | true | n2, weight `theta` (latency `ff.default`, `[0, 150]`) | `415 + theta` |
| n4 | barrier(q1, q2) | true | n2, weight 0; n0 (q2 ready), weight 0 | 415 |
| n5 | end of EQ wait on q2 (`bready`) | true | n4, weight 150 | 565 |
| n6 | block start | true | n5, weight 0 (ready); n3, weight 0 (valid) | `max(565, 415 + theta) = 565` for every `theta <= 150` |
| n7 | start X(q2) | `c1` | n6, weight 0 | 565 |
| n7' | start pad delay(q2) | `not c1` | n6, weight 0 | 565 |
| n8 | end of arm | join | n7 + 8 (label `c1`); n7' + 8 (label `not c1`) | 573 |

No obligation appears in this table: it contains only edges that define times (principle 8). Note that `theta` enters only through n3, and n3 never wins the max at n6.

### A.4 Obligations and tier dispatch

| Obligation | Check | Cone has latency variable? | Tier | Result |
| --- | --- | --- | --- | --- |
| O2b (no stall) | `t(n5) - t(n3) >= 0` | yes (`theta`) | Tier 1 | lower bound: `a = 565` from `Fmin[n5]`, `b = 415 + theta`; `lbound(565 - 415 - theta) = 150 - 150 = 0 >= 0`: proved |
| O3 (deadline 3000 ns = 750 dt) | `t(n7) - t(n3) <= 750` | yes | Tier 1 | `Fmax[n7] = {565, 415 + theta}`, `Fmin[n3] = {415 + theta}`; `diff_upper = max(ub(150 - theta), ub(0)) = 150`; `150 <= 750`: proved, margin `750 - 150 = 600 dt = 2400 ns` (worst case `theta = 0`) |
| O4 (gap variation, `q2`: n5 to n6) | `Variation(n6, n5, 0)` | yes | Tier 1 | `t(n6) - t(n5) = 0` for every `theta`: spread 0: proved |
| O7 (join determinism, EQ, `Delta = 0`) | `Variation(n8, n4, 0)` | no (cone excludes n3) | Tier 0 | `t(n8) - t(n4) = 158` in both scenarios: proved |

Tier 1 needed the cancellation of the shared base: `t(n5)` and `t(n3)` both contain 415 (the end of the measurement), so the difference is `150 - theta`, not an interval difference of two wide intervals.

### A.5 Verdict

PROVED-UNDER with assumption `ff.default: [0, 600] ns, vendor` (the lower bound is a placeholder). Margin on O3: 2400 ns. Maximum safe feedforward upper bound with the program re-elaborated: the wait becomes `hi`, the deadline obligation becomes `hi - theta <= 750 dt` with worst case `theta = lo = 0`, so `hi <= 750 dt = 3000 ns` (bisection in Tier 2 returns 3000 ns). EQ policy cost: `q2` idles 600 ns before the branch in every execution, plus a 32 ns pad on the else path. These numbers are the ones in the JSON of Section 13.2.

Why the margin is large: the deadline is measured from the result's own arrival, and EQ waits only `hi` after the measurement's end.

### A.6 What a changed contract does

If the contract's `hi` were 400 ns (100 dt) while the true latency could reach 150 dt: elaboration waits only 100 dt, `bready = 515`, `t(n6) = max(515, 415 + theta)`, which varies with `theta` above 100. O2b (`515 - 415 - theta >= 0`, lower bound `100 - 150 = -50`) fails in Tier 1, Tier 2 returns `theta = 150`, replay shows the arm stalled by 50 dt, and the verdict is REFUTED (`V-O2b`), with O4 also reporting the varying gap on `q2`. This is the case where the contract is wrong, found because the contract is explicit.

### A.7 ARTIQ-like variant: setup (illustrative numbers)

Contract: `dt = 1 ns` (mu). Input-to-CPU latency `in2cpu` in `[0, 600] ns` (placeholder supplied with `--assume latency.in2cpu=0:600:vendor`; ARTIQ publishes no number). CPU issue cost per statement `c = 150 ns` (illustrative). Commit lead `L = 100 ns` (illustrative; unpublished, supplied with `--assume timeline.commit_lead=100`). Late policy: underflow raises.

Program (policy `exp`): a gate window on an input channel ends at cursor time `T_in = 1000 ns`; the kernel reads the count (the CPU blocks until the data is available); if the count exceeds a threshold it emits a TTL pulse after `delay(500 ns)` on the cursor, and there is no further explicit delay.

### A.8 Side by side: two encodings of the same program

Dispatch graph (fixed-dispatch semantics, Section 9.4.3):

| Node | Rule | Time (ns) |
| --- | --- | --- |
| g0 origin | | 0 |
| g1 cursor at gate end `T_in` | origin, weight 1000 | 1000 |
| g2 CPU reaches the read | origin, weight 1000 (kernel timing, illustrative) | 1000 |
| g3 CPU has the data | `max(g2 + 0, g1 + theta)`, `theta in [0, 600]` | `1000 + theta` |
| g4 CPU issues the output | g3, weight 150 | `1150 + theta` |
| g5 output stamp `T_x` (cursor after `delay(500)`), label "count over threshold" | g1, weight 500 | 1500 |

**Encoding B (v2, fixed dispatch).** `T_x` is **defined** by the cursor chain: `T_x = T_in + 500 = 1500`, independent of `theta`. Obligation O1: `T_x - issue_x >= L`, i.e. `1500 - (1150 + theta) >= 100`, i.e. `theta <= 250`. Tier 1: `t(g5) - t(g4) = 350 - theta`, whose lower bound over `theta in [0, 600]` is `-250`, below the required `100`: not proved, escalate. Tier 2: SAT with `theta = 600`. Counterexample: `omega = {count over threshold: true}`, `theta_in2cpu = 600 ns`, event time 1500, slack `-250 ns` against a required `+100 ns`: **shortfall 350 ns**. Replay in the ARTIQ executor: the CPU clock is 1750 when the event is submitted, slack `1500 - 1750 = -250 < 100`: `RTIOUnderflow` raised at the same event. Verdict: **REFUTED, V-O1, late by 350 ns at `theta = 600`**. The report adds that the obligation holds only for `in2cpu <= 250 ns`.

**Encoding A (v1: free time-points, controllability).** `T_x` is a free variable constrained only by lower bounds that mimic "delay at least 500": `T_x >= T_in + 500` (v1's resource-order inequality), and the obligation `T_x - (T_in + theta + 150) >= 100` is just another constraint. Results:

| Question | Answer in the free encoding | Why |
| --- | --- | --- |
| Consistent (STN, `theta` free)? | yes | choose `theta = 0` and `T_x = 1500` |
| Weakly controllable? | yes | for each `theta` choose `T_x = max(1500, 1250 + theta)` |
| Dynamically controllable? | **yes** | `T_x` can be chosen after observing `theta`: `T_x = max(1500, 1250 + theta)` |
| Strongly controllable (Vidal-Fargier)? | yes | one choice `T_x = 1850` works for all `theta` (worst case `theta = 600`: `T_x >= 1000 + 600 + 150 + 100 = 1850`) |

So every notion of "some schedule exists" says the program is fine, and v1 would report PROVED or PROVED-UNDER. But the hardware stamps the event at the cursor (1500) and does not delay it: the program underflows when `theta > 250`. The free encoding answered a different question ("could a dispatcher make this safe?"), and the answer is yes: the schedule that works delays the output to 1850, i.e. a `delay` of at least 850 ns instead of 500 ns.

### A.9 How the two modules fit together

Verification (Tier 2) answers REFUTED for the program as written. Tier 3 then answers the controllability question and supplies the repair: `N_geq(P)` is DC and strongly controllable with `T_x >= 1850`, so `qtiming repair` proposes increasing the programmer's delay from 500 ns to `theta_hi + c + L = 600 + 150 + 100 = 850 ns`, re-verifies the patched program (O1: `1850 - 1750 = 100 >= 100`, holds at `theta = 600`; PROVED-UNDER on `in2cpu <= 600 ns`) and prints the diff. The suggested value is exactly what the SC reduction computes (Section 12.4), which is the cross-check of Tier 3 against Tier 2 on this rigid example (T5).

The regression test `tests/fixtures/free_stn_false_proof.py` encodes Encoding A and asserts that it reports "consistent, DC and SC", while `qtiming check` reports REFUTED on the same input. It is kept permanently as the executable form of finding F1.

---

## 24. Appendix B: traceability matrix (v1 to v2)

| v1 section | v2 section | Change |
| --- | --- | --- |
| 1 What we are building, scope | 2.1, 2.3 | complete scope; no reduced MVP; non-goals updated |
| 1 Engineering principles | 2.4 | added principles 8 (obligations never schedule) and 9 (dispatch defined once, implemented twice); principle 2 now "exact arithmetic" with real theta in the solver |
| 2 Architecture, pipeline | 3.1, 3.2, 3.3 | dispatch edges versus obligations; Tier 3 off the verification path; evidence stage added |
| 2 Pipeline stages table | 3.2 | modules renamed (`dispatch`, `solve.synth`, `evidence`, `repair`) |
| 2 Repository layout | 4.1, 4.2, 4.3 | full tree to files; executor independence |
| 2 Dependency policy | 4.4 | Python 3.10 to 3.14; Qiskit 2.6.2; CSTNU Tool 7.1; q1simulator Python 3.12+ (F10, F19, F32) |
| (none) | 4.5 | import-linter contracts |
| 3 Time primitives | 5.1 | rounding by role (F7); `Interval` without provenance |
| 3 `Prov(IntEnum)` | 5.2 | structured provenance, assumption sets, `sched` class (F8) |
| 3 TQ AST | 5.3 | added `Assign`, `Switch`, `variant` on `Measure`, string bit references (F13, F14) |
| 3 Labels | 5.4 | derived propositions; no disjunct duplication (F13, F29) |
| (none) | 5.5 | error codes |
| 4 Front end, 4.1 annotations | 6.4 | string bit names, `hard`, `cut`; serialisers; Strip pass (F11, F14) |
| 4.2 DAG walk | 6.1, 6.2, 6.3 | `expr`, `Var`, `Store`, `else`, `Switch`, `Box` expressions, `measure_2` (F13) |
| 4.2 stretch | 6.6 | minimal solution rule for under-determined stretch |
| 4.3 validation errors | 6.6, 10.7 | per-backend lint table (F21) |
| (none) | 6.7, 6.8 | `StripTimingAnnotations`; feedback tier map |
| 5 Contract, 5.1 schema | 7.1, 7.2 | schema 0.2: `target`, `topology`, `feedback_tier`, `personality_params`, variation-based `idle`; pydantic code |
| 5.2 compatibility | 7.6 | corrected for Q1 per-instruction `set_cond` |
| 5.3 instances | 7.3 | Q1 numbers replaced (F15); ARTIQ rules (F17); QUA aligns (F18); IBM from Target (F20) |
| 5.4 loader | 7.4, 7.5 | role-aware rounding; Target authoritative; missing fields give UNKNOWN (F31) |
| (none) | 7.7 | evidence ingestion |
| 6 Elaboration | 8 | elaboration inserts statements only; no constraints |
| 6.1 EQ | 8.2 | barrier plus delay `hi` plus padding; per-resource; O2b |
| 6.2 SYNC | 8.3 | join with contract cost; bounds become obligations |
| 6.3 EXP | 8.4 | cursor semantics; commit marking |
| (none) | 8.5 | Q1 `set_cond` per-instruction modelling (F16) |
| 6.4 loops | 8.6 | summarisation by periodic cut |
| 6.5 calls, within | 8.7 | `within` as obligation with per-resource first ops |
| 7 LTEG | 9 | rewritten: dispatch edges, contingent variables, obligations separate (F1, F2) |
| 7.1 structures | 9.2 | `DEdge`, `LatVar`, `snap` |
| 7.2 construction | 9.3, 9.4 | per-personality dispatch rules |
| 7.3 invariants | 9.5 | seven invariants; causality as I4 with O2a |
| 7.4 windowing | 9.6, 9.7 | five cut rules (F26) |
| 8 Obligations | 10 | O2 split (O2a, O2b); O4 redefined (F6); O4a; severity versus hard |
| 8.1 O5 | 10.5 | real ARTIQ rules (F17); Q1 network occupancy |
| 8.2 classical WCET | 9.4.2, 10.2 | issue chain as dispatch; O1 compares it to the RT chain |
| 8.3 hard versus advisory | 10.1, 10.4 | two orthogonal flags |
| 9 Solver tiers, 9.1 dispatch | 3.5, 11.1 | new tier rule (F28) |
| 9.2 Tier A STN | 12.3 | moved to Tier 3; Bellman-Ford corrected |
| (9.2 SC claim) | 12.4 | Vidal-Fargier reduction with worked example (F3) |
| 9.3 Tier B scenarios | 11.2 | Tier 0 concrete evaluation (F4) |
| 9.4 Tier C1 STNU DC | 12.5 | Tier 3; three layers; oracle-gated |
| 9.5 Tier C2 CSTNU | 12.6 | bridge with v7.1 facts (F19) |
| 9.6 Tier D SMT | 11.4, 11.5 | Tier 2 exact encoding with max, labels, real theta (F2, F27) |
| (none) | 11.3 | Tier 1 interval abstraction with must/may labels |
| 10 Verdicts, 10.1 | 13.1, 13.2 | combination code; JSON with consistent numbers (F24) |
| 10.2 counterexamples | 13.3, 13.4 | rational theta; minimisation via Tier 0 |
| 10.3 RUS | 13.5 | exhaust term, `T_post`, exact arithmetic (F23) |
| 10.4 rendering | 13.6 | SARIF fields specified |
| 11 Executor | 14 | independence enforced; personalities table corrected; oracles; ARTIQ code |
| 11.3 q1simulator | 14.7 | separate venv (F32) |
| 12 Testing | 16 | seven layers; corrected properties (F9); vertex lemma ground truth |
| 12.1 properties | 16.2 | property 3 restated |
| 13 Benchmarks | 17 | pre-registration procedure; `claims.json` |
| 14 IBM probe | 18 | dry-run primary evidence; redesigned optional probe (F22, F30) |
| 15 Packaging, CI, artifact | 19 | updated matrix; CLI reference; exit codes |
| 16 Build sequence, effort estimate | 20 | dependency-ordered phases with gates; no hour estimates |
| 16.2 what to cut first | removed | complete scope |
| 17 Risks, decision log | 21 | updated; every decision traceable to findings |
| (none) | 15 | theory track (T1 to T10) |
| (none) | 22 | related work and novelty statement (F25) |
| Appendix worked example | 23 | redone under fixed dispatch; false-proof side-by-side |
| Research report, "Encoding" and conjectures | 12, 15 | conjectures restated (F5) |
| Research report, contract vocabulary | 7 | extended |
| Research report, hypotheses H1 to H6 | 17.2, 17.3 | mapped to experiments; pre-registration |
| Research report, threats to validity | 21.1 | merged into risks |
| Research report, prior art | 22 | updated (F25) |

---

## 25. Appendix C: sources

URLs were gathered during the validation pass of 2026-11-17 or taken from the research report. A dagger marks paths reproduced from the validation notes or recalled without re-fetching during authoring; they must be re-checked in P17 (the **[verify]** list). Sources marked **unofficial** are not vendor documentation and are used only as test fixtures or hints, never as contract provenance above `vendor`.

### C.1 IBM and Qiskit

| Source | URL | Used for |
| --- | --- | --- |
| IBM Quantum docs: Execute dynamic circuits | https://quantum.cloud.ibm.com/docs/en/guides/execute-dynamic-circuits | IBM lint rules (F21), box and `if_test` limits |
| IBM Quantum docs: Dynamic circuits considerations / job limits | https://quantum.cloud.ibm.com/docs/en/guides/dynamic-circuits-considerations | broadcast budget, instruction limits (26.8 M per qubit) |
| IBM Quantum docs: job limits † | https://quantum.cloud.ibm.com/docs/en/guides/job-limits | job limits |
| IBM Quantum docs: OpenQASM 3 feature table † | https://quantum.cloud.ibm.com/docs/en/guides/qasm-feature-table | supported control flow |
| IBM Quantum docs: Circuit timing † | https://quantum.cloud.ibm.com/docs/en/guides/circuit-timing | delay, stretch, box on IBM |
| IBM Quantum docs: QPU information | https://quantum.cloud.ibm.com/docs/en/guides/qpu-information | measurement and gate durations (vendor) |
| IBM Quantum docs: Plans (Open Plan) † | https://quantum.cloud.ibm.com/docs/en/guides/plans-overview | Open Plan allowance (F30) |
| IBM blog: Open Plan announcement † | https://www.ibm.com/quantum/blog (page to be located in P17) | 180-minute opt-in details |
| IBM blog: utility-scale dynamic circuits (feedforward about 600 ns, 2025-11-19, vendor) | https://www.ibm.com/quantum/blog/utility-scale-dynamic-circuits | feedforward figure |
| Qiskit 2.1 release notes | https://quantum.cloud.ibm.com/docs/api/qiskit/release-notes/2.1 | `BoxOp` annotations, `Duration`/`Stretch`, qasm3 annotation handlers, QPY v15 |
| Qiskit 2.3 release notes † | https://quantum.cloud.ibm.com/docs/api/qiskit/release-notes/2.3 | Rust-native control flow |
| Qiskit 2.0 release notes | https://eu-de.quantum.cloud.ibm.com/docs/en/api/qiskit/release-notes/2.0 | removal of `qiskit.pulse` |
| qiskit on PyPI (2.6.2, 2026-11-05, Python >= 3.10) | https://pypi.org/project/qiskit/ | version and Python support (F10) |
| Qiskit `ConstrainedReschedule` | https://quantum.cloud.ibm.com/docs/api/qiskit/qiskit.transpiler.passes.ConstrainedReschedule | alignment padding |
| qiskit-ibm-runtime scheduling passes | https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/transpiler-passes-scheduling | scheduling behaviour |
| **Unofficial** Heron platform snapshot (dt = 4 ns, alignments = 1, measure and measure_2 durations per backend) | https://github.com/Oichkatzelesfrettschen/gororoba-quantum (docs/notes/ibm_heron_platform.md) | offline test fixture only (F20) |

### C.2 Other control stacks

| Source | URL | Used for |
| --- | --- | --- |
| ARTIQ manual: real-time I/O | https://m-labs.hk/artiq/manual/rtio.html | SED lanes, collision, busy, sequence, underflow rules (F17) |
| ARTIQ manual: core device | https://m-labs.hk/artiq/manual/getting_started_core.html | cursor and slack |
| Qblox: trigger network handling † | https://docs.qblox.com/ (page `trigger_handling.html`; exact path to be recorded in P17) | 212 to 239 ns, 252 ns, 149 ns, 24 ns, 388 ns example (F15) |
| Qblox: Q1 / Q1ASM documentation | https://docs.qblox.com/en/main/products/qblox_instruments/q1/index.html | instruction costs, `set_cond`, RT queue (F16) |
| Qblox: sequencer and LINQ-based feedback | https://docs.qblox.com/en/v2026.04.0/products/architecture/sequencers/linq_based_feedback.html | feedback paths, sequencer behaviour |
| Quantum Machines: Timing in QUA | https://docs.quantum-machines.co/latest/docs/Guides/timing_in_qua/ | implicit aligns, `strict_timing_`, flags (F18) |
| q1simulator on PyPI | https://pypi.org/project/q1simulator/ | Q1 cross-check (Python >= 3.12) |
| Zurich Instruments LabOne Q timing rules | https://docs.zhinst.com/labone_q_user_manual/concepts/sections_and_pulses/timing_rules | grids (reference) |
| QICK `asm_v2.py` | https://github.com/openquantumhardware/qick/blob/main/qick_lib/qick/asm_v2.py | assembler TODO on checks |

### C.3 Temporal networks and tooling

| Source | URL | Used for |
| --- | --- | --- |
| CSTNU Tool (v7.1, 2026-09-08; licences LGPL-3.0 and CC0 parts; download page) | https://profs.scienze.univr.it/~posenato/software/cstnu/ | oracle and bridge (F19) |
| HEATlab Prob-in-Ctrl (MIT) | https://github.com/HEATlab/Prob-in-Ctrl | 452 DC and 169 non-DC STNUs |
| Posenato benchmark sets (STNUBenchmark2020, CSTNUBenchmark2018, 2025 diamond sets) † | linked from the CSTNU Tool page above | oracle and scaling tests |
| nrealus/stnu-conflicts, yuemning/dc-checking | GitHub (names as recorded; use as test references only) | reference implementations |
| Cairo, Hunsberger, Rizzi, "Faster DC checking for STNUs" (TIME 2018, LIPIcs 2018.8) | https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.TIME.2018.8 | RUL-minus, complexity |
| Strong controllability and the Vidal-Fargier reduction (CEUR Vol-2509, paper 12) † | https://ceur-ws.org/Vol-2509/paper12.pdf | SC reduction (F3) |
| Morris, "Dynamic controllability and dispatchability relationships" (CPAIOR 2014) | https://www.doi.org/10.1007/978-3-319-07046-9_33 | O(N^3) DC algorithm |
| Morris, "A structural characterization of temporal dynamic controllability" (CP 2006) | https://doi.org/10.1007/11889205_28 | DC rules background |
| Hunsberger, DC-checking survey | https://www.cs.vassar.edu/~hunsberg/__papers__/springer-2015-acta.pdf | survey of algorithms |
| Hunsberger and Posenato, sound-and-complete DC for CSTNUs (TIME 2018.14) | https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.TIME.2018.14 | CSTNU DC |
| Hunsberger and Posenato, "Speeding up RUL-minus" (AAAI 2022); FD_STNU (Information and Computation 2023) | via the CSTNU Tool page | newer algorithms (reference only) |
| Cairo and Rizzi, CSTN DC is PSPACE-complete | https://arxiv.org/abs/1608.08545 | complexity |
| Comin and Rizzi, CSTN DC via mean-payoff games | https://arxiv.org/abs/1505.00828 | complexity |
| Dechter, Meiri, Pearl, temporal constraint networks | https://api.crossref.org/works/10.1016/0004-3702(91)90006-6 | STN |
| Sumic and Vidal, weak controllability of STNUs (TIME 2024 slides) | https://www.lirmm.fr/time2024/files/WeakControllabilityOfSTNUsTIME2024.pdf | weak controllability |
| Tsamardinos, Vidal, Pollack, CTP | https://deepblue.lib.umich.edu/items/f5521ccc-29ec-4bf9-ae3a-205216b63b82 | CSTN |

### C.4 Related work (Section 22)

| Source | URL |
| --- | --- |
| qlin (R. Malarchick, 2026-11-14) | https://arxiv.org/abs/2611.19618 |
| qconform (same author) | https://arxiv.org/abs/2610.10427 |
| DART-Q | https://arxiv.org/abs/2605.09142 |
| GRAMPUS (Adams, Bernardy, Perticone, Pope) | https://arxiv.org/abs/2510.03130 |
| GRAMPUS "...with Measurement", TYPES 2026 slides | https://types2026.cse.chalmers.se/slides/47.pdf |
| QaiJi IR | https://arxiv.org/abs/2609.29305 |
| Dynamarq (Shirgure et al.) | https://arxiv.org/abs/2604.03360 |
| Maurya and Tannu, synchronization for lattice surgery | https://arxiv.org/abs/2506.10258 |
| Quantum Orchestras | https://arxiv.org/abs/2607.09605 |
| qwp-ert (expected runtime), and runtime analysis of quantum programs | https://arxiv.org/abs/2607.12532 ; https://arxiv.org/abs/1911.11247 |
| QASM-TS 2.0 | https://arxiv.org/abs/2412.12578 |
| TUM dynamic-circuit analyses | https://arxiv.org/pdf/2605.28439 ; https://arxiv.org/pdf/2606.02018 |
| Riverlane control-stack design verification | https://arxiv.org/abs/2310.05229 |
| TIDE, QCORE, QuCtrl-BELL, NVQLink | https://arxiv.org/abs/2608.15173 ; https://arxiv.org/abs/2608.06875 ; https://arxiv.org/abs/2605.22433 ; https://arxiv.org/abs/2510.25213 |
| eQASM | https://ar5iv.labs.arxiv.org/html/1808.02449 |
| QubiC 2.0 and multi-FPGA synchronisation | https://arxiv.org/abs/2309.10333 ; https://arxiv.org/abs/2506.09856 |
| QICK | https://arxiv.org/pdf/2110.00557 |
| Aalborg UPPAAL quantum protocols (CAV 2026) | https://vbn.aau.dk/da/publications/analysis-and-verification-of-quantum-communication-protocols-in-u/ |
| TqCCS (Fernandes, Minho 2019) | https://repositorium.sdum.uminho.pt/bitstream/1822/80754/1/Vitor%20Emanuel%20Goncalves%20Fernandes.pdf |
| q1lens | https://pypi.org/project/q1lens/ |

### C.5 Language, physics and real-time systems (from the research report, still used)

OpenQASM 3 timing (https://openqasm.com/language/delays.html) and pulses (https://openqasm.com/language/pulses.html); Quil specification (https://quil-lang.github.io/); Gidney and Ekera (https://arxiv.org/abs/1905.09749); Google below-threshold QEC (https://arxiv.org/abs/2408.13687); Skoric et al. (https://arxiv.org/pdf/2209.08552); MERA (https://arxiv.org/abs/2511.10921); Lohstroh et al., deterministic coordination (https://par.nsf.gov/servlets/purl/10554371); Henzinger et al., Giotto (https://api.crossref.org/works/10.1109/JPROC.2002.805825); Lickly et al., PRET (https://www.cs.columbia.edu/~sedwards/papers/lickly2008predictable-tr.pdf); FlexPRET on Lingua Franca (https://drops.dagstuhl.de/storage/01oasics/oasics-vol128-ng-res2025/OASIcs.NG-RES.2025.1/OASIcs.NG-RES.2025.1.pdf); Wilhelm et al. WCET (https://api.crossref.org/works/10.1145/1347375.1347389); Li and Malik IPET (https://api.crossref.org/works/10.1145/217474.217570); Alur and Dill (https://doi.org/10.1016/0304-3975(94)90010-8); Kaminski et al., expected runtimes (https://api.crossref.org/works/10.1145/3208102).
