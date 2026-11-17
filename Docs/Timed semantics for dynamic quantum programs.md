# Writing a checkable rulebook for quantum time

**Bottom line.** The topic holds up, with modifications. Mid-circuit measurement and measurement-conditioned branching are now standard in cloud stacks, yet no standard, IR or published tool says what a branch does to time in a form a machine can check. OpenQASM 3 constrains branch durations only inside `defcal`. The Quil spec leaves `WAIT` and `JUMP-WHEN` timing "deliberately unspecified". Every controller resolves a branch in its own way: it pads, it resynchronises with an unbounded gap, or it exposes a cursor that underflows. The four parts of the proposal are a timed semantics, explicit branch-timing policies, a contract vocabulary and a static checker. As far as an extensive 2025–2026 sweep can show, none of the four exists in combined form. The closest neighbours bound what can be claimed: GRAMPUS has durations but no measurement, the Minho TqCCS thesis has a timed calculus with measurement but no schedule verification, and the Aalborg CAV 2026 work applies UPPAAL to quantum protocols. The necessity case needs reframing. Vendors already enforce timing at run time, statistical models predict dynamic-circuit fidelity well without any timing semantics, and on trapped ions idle error is about 30× below gate error. So raw idle fidelity is the weakest argument. The strong arguments are four: portability of timing intent, fault-tolerance reaction-time and lattice-surgery synchronisation deadlines, rarely-taken branches that cannot be tested empirically, and silent failures such as ARTIQ dropping events without an exception. One researcher can do the work in 12–24 months if it is built on CSTNU dynamic controllability rather than invented from scratch, if every latency figure is typed by its provenance, and if loops are scoped to bounded `for` plus capped repeat-until-success with expected-time bounds.

---

## Decision

### Verdict: GO, with five modifications

The proposal is **correctly framed as a semantics-plus-verification problem at the IR–control boundary**. It is **necessary for reasons other than the one most people would assume**. Its **novelty is real but narrow and must be claimed precisely**, and it is **feasible for one researcher** with the scoping below. The mapper direction from the earlier selected-problem report is out of scope at the user's explicit request, and nothing here depends on it.

| Criterion | Rating | Confidence | One-line justification |
|---|---|---|---|
| **Right framing** | 4/5 | High | The gap sits exactly where the notes put it: branch timing is unspecified at circuit level in OpenQASM 3 and Quil, and vendors fill it with incompatible ad hoc rules. Reframe the "why" (below). |
| **Necessity** | 3/5 now, 4/5 for FT | Medium | Runtime enforcement plus backend DD is "good enough" for single-vendor NISQ fidelity. Portability, FT deadlines, untestable rare branches and silent drops are strong and documented. |
| **Novelty, C1: timed semantics with MCM, branching, bounded loops, "deterministic modulo outcomes"** | Open | High-medium | GRAMPUS has no measurement. TqCCS (2019 MSc) has time plus measurement but targets the effect of time on states, not schedules. Quantum Orchestras and qwp-ert are untimed or abstract-cost. |
| **Novelty, C2: explicit branch-timing policies** | Partially covered in practice, not formalised | Medium | Q1ASM `else_duration`, QUA implicit align, ARTIQ's exposed cursor and IBM's block restart are policies in all but name. The contribution is formalising and comparing them, not inventing them. |
| **Novelty, C3: cross-layer timing-contract vocabulary** | Likely open | Medium | TIDE, QCORE and NVQLink are runtime or hardware mechanisms, not program-level contracts. QaiJi IR (arXiv:2609.29305, Sep 2026) has a "five-axis semantic contract" (data, semantics, lowering, runtime, verification) and records a classical-feedback model, but its abstract defines no durations, latency bounds or deadlines and no timing checker; it states it does not establish a physical feedback loop. Checked at abstract level, so read the full text before submission. |
| **Novelty, C4: static checker certifying no underflow / deadline miss / unplanned idle, or giving a counterexample** | Open | Medium-high | No static slack or deadline analysis found for ARTIQ, Q1ASM, QUA, eQASM or QICK. QICK's own assembler carries a TODO to add such checks. Riverlane verifies hardware, not programs. The Aalborg UPPAAL group is the most likely competitor. |
| **Feasibility (one researcher, 12–24 months, software plus optional cloud)** | 4/5 | Medium-high | Parsers, Qiskit `BoxOp` annotations, Z3 and a live CSTNU tool exist. The risks are vendor latency data, cloud opacity (IBM runs only `if_test`) and any attempt to mechanise the metatheory. |
| **Overall risk** | Moderate | — | Competitor movement (Aalborg), "it's just STNU" reviewer pushback, and missing certified latency bounds. All three are manageable. |

### The counter-evidence, and how it changes the framing

The case against the topic is credible and should appear in any paper's introduction.

**Vendors enforce timing at run time.** QUA inserts implicit aligns at every control-flow branch. It compiles deterministic aligns into precomputed waits and leaves only "a few cycles" of gap at non-deterministic ones ([QM, Timing in QUA](https://docs.quantum-machines.co/latest/docs/Guides/timing_in_qua/)). IBM's feedforward costs about 600 ns and is reported as approximately constant. IBM also inserts dynamical decoupling on the backend, so most users never see timing nondeterminism ([Shirgure et al.](https://arxiv.org/html/2604.03360v2)).

**Statistical models predict fidelity without timing semantics.** The Dynamarq framework predicts dynamic-circuit fidelity with R² of 0.86–0.91 on IBM Kingston and Pittsburgh, and 0.95 on the Helios-1E *emulator*, from structural features alone. Perturbing branch probabilities lowers R² by only about 5% ([arXiv:2604.03360](https://arxiv.org/html/2604.03360v2)).

**Idle error on ions is small.** In the same paper's noise models, IBM idle error is about 1e-4 against 2Q error of about 1e-3. The Helios model has idle error of about 2.5e-5 against 2Q error of about 8e-4, a ratio of about 0.03. Unplanned idle therefore costs little fidelity on ions ([arXiv:2604.03360](https://arxiv.org/html/2604.03360v2)).

**[Synthesis]** None of this refutes the topic, but it moves its centre of gravity. A paper that opens with "unplanned idle destroys fidelity" will meet a reviewer holding the Dynamarq R² and the Helios idle ratio. A paper that opens with the four arguments below is much harder to dismiss.

| Strong justification | Evidence |
|---|---|
| **Portability of timing intent** | The same OpenQASM 3 `if` means equal-length padding on Qblox, sync-with-gap on QUA, cursor-and-underflow on ARTIQ, and block restart on IBM. OpenQASM 3 constrains branch durations only inside `defcal` ([OpenQASM pulses](https://openqasm.com/language/pulses.html)). |
| **FT deadlines and synchronisation** | Resource estimates assume a 10 µs reaction time ([Gidney & Ekerå](https://arxiv.org/abs/1905.09749)). Lattice-surgery patches must be phase-aligned: passive idling can raise program-level logical error up to about 23× under linear accumulation, while active slack spreading cuts it up to 2.4× ([Maurya & Tannu](https://arxiv.org/abs/2506.10258)). |
| **Rare branches cannot be tested** | On IBM, QEC correction branches are taken only about 1–3% of the time, and about 0.1–0.3% in the Helios model ([arXiv:2604.03360](https://arxiv.org/html/2604.03360v2)). The timing of the branch that matters most is the one least exercised. |
| **Silent failures** | ARTIQ discards events on sequence, collision and busy errors. These "are not raised as exceptions and cannot be caught" ([ARTIQ RTIO](https://m-labs.hk/artiq/manual/rtio.html)). A timing bug can change the executed program with no visible error. |

### Recommended modifications

1. **Anchor the formal core in (C)STNU controllability** instead of a bespoke calculus. Measurement and feedforward latency become contingent links, and outcome bits become observation propositions. "Deterministic modulo outcomes" becomes a precise controllability notion. This brings a mature body of algorithms and a maintained tool (Posenato's CSTNU Tool) and pre-empts the "just STNU" objection by making the reduction a contribution.
2. **Type every latency by its provenance.** Use certified, cycle-bound, measured-max(n), percentile, mean±σ, or vendor claim. Hard obligations may be discharged only with the first two. Today no vendor publishes a certified worst case for any feedback path, so most verdicts will read "proved under these assumptions". Saying so is a feature.
3. **Scope loops honestly.** Support statically bounded `for`, plus `while` with an explicit iteration cap and an exhaust handler. Repeat-until-success (RUS) gets a three-part verdict: worst case under the cap, expected time, and tail probability. Exclude unbounded `while`.
4. **Make the late/violation policy part of the contract.** The options are raise, drop-and-log, delay-to-next-cycle, defer-to-next-round, halt and compile-error. Vendors disagree on exactly this, and a checker's job is to prove the late branch unreachable.
5. **Position against the Aalborg UPPAAL line explicitly.** The differences are automatic IR-level extraction, policy-aware semantics, a portable contract and dedicated counterexamples. UPPAAL can serve as a baseline back end instead of a rival.

A mechanised (Agda/Lean) GRAMPUS-style type theory with branching is optional and should not be on the critical path.

---

## Six clocks meet at one branch: the physics and timescales that set the budget

A dynamic program measures a qubit, waits for the classical result to travel and be decided on, and then plays different pulses depending on the outcome. Three durations govern that loop. Readout integration is the first. Classical feedforward latency (discrimination, transport, decision, pulse issue) is the second. The coherence time against which both are charged is the third. Their ratios differ by orders of magnitude across modalities, and so does what "timing correctness" means.

| Modality | Gate scale | Readout / MCM | Feedforward | Coherence / cycle | What timing errors cost |
|---|---|---|---|---|---|
| Superconducting (IBM Heron) | CZ 68 ns; dt = 4 ns | measurement 1.66 µs ([IBM QPU info](https://quantum.cloud.ibm.com/docs/en/guides/qpu-information)); median final measurement about **34× a 2Q gate**; MCM feature 65% shorter at about 10× 2Q error ([Shirgure et al.](https://arxiv.org/html/2604.03360v2)) | **about 600 ns** ([IBM blog](https://www.ibm.com/quantum/blog/utility-scale-dynamic-circuits)) | T1/T2 of order 100 µs | idle decoherence, spectator dephasing, frame-phase error |
| Superconducting (Google Willow) | CZ 42 ns | inside 1.1 µs cycle | decoder 63 µs average at d=5 ([arXiv:2408.13687](https://arxiv.org/abs/2408.13687)) | 1.1 µs QEC cycle | reaction-time budget, backlog |
| Neutral atoms | Rydberg CZ 270 ns | imaging about 500 µs ([Bluvstein et al.](https://www.nature.com/articles/s41586-023-06927-3)); cavity readout plus feedforward <100 µs ([arXiv:2606.24869](https://arxiv.org/abs/2606.24869)) | FPGA | T2 > 1 s | throughput, transport coupling |
| Trapped ions (Quantinuum H2) | 2Q tens of µs | sub-ms | network or Wasm calls for remote classical | transport about 60% of circuit time ([Moses et al.](https://arxiv.org/pdf/2305.03828v2)) | throughput; idle error small |

**[Synthesis]** On superconducting hardware, a single feedforward window of measurement plus about 600 ns is long against gate times. A back-of-envelope pure-dephasing estimate shows the scale. It is standard physics, not a cited measurement.

```latex
p_Z(t) = \tfrac{1}{2}\left(1 - e^{-t/T_2}\right), \qquad
t = 0.6\,\mu\text{s},\; T_2 = 100\,\mu\text{s} \;\Rightarrow\; p_Z \approx 3\times 10^{-3}
```

That is about three times a 1e-3 2Q gate error, before DD. DD exists precisely to suppress this. It depends on knowing the window length when the sequence is compiled. Context-aware DD in MERA presupposes known idle windows ([MERA](https://arxiv.org/abs/2511.10921)). IBM moved DD for dynamic circuits to backend insertion because the client-side scheduler cannot see the feedforward window ([IBM blog](https://www.ibm.com/quantum/blog/utility-scale-dynamic-circuits)).

A second, subtler cost is phase. A rotating-frame phase tracked in software accumulates an error of 2π·δf·Δt whenever elapsed time differs from the time the compiler assumed. **[Synthesis, hypothetical numbers]** A 10 kHz residual detuning and a 100 ns timing uncertainty give 6.3 mrad per occurrence. Qiskit's `ConstrainedReschedule` silently pads a 100 dt delay to 112 dt to meet a 16 dt acquire alignment, and IBM notes that a misaligned circuit can run with untracked phase ([Qiskit API](https://quantum.cloud.ibm.com/docs/api/qiskit/qiskit.transpiler.passes.ConstrainedReschedule)).

Measurement also disturbs neighbours. Dynamarq reports measurement-induced dephasing on spectators without quantifying it. MERA identifies crosstalk, idling decoherence and reset infidelity as distinct MCM error sources that vary strongly per qubit, and reports 24.94–52.00% fidelity gains over Qiskit O3 by modelling them ([MERA](https://arxiv.org/abs/2511.10921)). The literature contains **no clean curve of fidelity against feedforward-window length, and no DD on/off delta inside feedforward windows**. That measurement is itself a contribution the evaluation can supply.

The modality spread forces one design decision. Deadlines and gap bounds must be expressed **relative to a modality's coherence and cycle times**, never as absolute nanoseconds baked into the semantics. The semantics is parametric in a contract. The contract carries the numbers.

---

## Control hardware hides time behind two domains and a commit point

Every control stack reviewed shares one structure. A non-deterministic classical side (CPU, sequencer core or host) builds a timeline of timestamped events. A deterministic real-time side (timer, RT queue, RTIO FIFO) consumes it. Determinism holds downstream of the **commit point** where an event enters a timed queue. Everything upstream can be late. eQASM states this most cleanly. A "reserve phase" in the non-deterministic domain builds timing points, a "trigger phase" consumes them, and timing queues, event queues and measurement-result registers are the only crossings ([eQASM](https://ar5iv.labs.arxiv.org/html/1808.02449)) [older]. Its correctness condition is an issue-rate inequality, R_req ≤ R_allowed. The hardware assumes this condition but does not check it.

The systems differ in three places: what happens at a branch, what happens when the queue drains, and what latency they publish.

| System | Time base | Branch semantics | When the timeline is late | Published latency (provenance) |
|---|---|---|---|---|
| **ARTIQ** | 1 ns mu, 125 MHz coarse; cursor `now_mu` vs wall clock; slack = difference | exposed cursor; reading input leaves **negative slack**, so the programmer must add `delay` before the next output | `RTIOUnderflow` raised and catchable; **sequence, collision and busy errors silently drop the event**; 8 SED lanes is a hard limit | none numeric; "low and predictable" ([ARTIQ RTIO](https://m-labs.hk/artiq/manual/rtio.html)) |
| **Qblox Q1** | 4 ns; Q1 core feeds RT queue; wall-time = sum of RT `duration`s | `set_cond`: when false, RT core waits `else_duration`, so **both paths are equal by construction** (docs inconsistent: `else_cnt` vs `else_duration`) | RT queue empty → sequencer **halts** with `SEQUENCE_PROCESSOR_RT_EXEC_COMMAND_UNDERFLOW` | thresholded bits 160 / 250 / 472 ns self/intra/multi-cast (route tables, no statistic) ([Q1ASM](https://docs.qblox.com/en/main/products/qblox_instruments/q1/index.html); [LINQ](https://docs.qblox.com/en/v2026.04.0/products/architecture/sequencers/linq_based_feedback.html)) |
| **QM QUA** | 4 ns | implicit align at control flow; any QUA-variable dependence is non-deterministic → gaps of "a few cycles"; conditional `play` = equal-length wait | `strict_timing_` raises an error listing gaps | 224 ns active reset [vendor claim]; sync gap unpublished ([Timing in QUA](https://docs.quantum-machines.co/latest/docs/Guides/timing_in_qua/)) |
| **ZI LabOne Q** | signal/system grids; **200 ns grid** for globally routed feedback | section length is a minimum; compiler pads | "LabOne Q raises an error" | "<550 ns" global [vendor claim] ([timing rules](https://docs.zhinst.com/labone_q_user_manual/concepts/sections_and_pulses/timing_rules); [QHub](https://www.zhinst.com/products/qhub-quantum-system-hub)) |
| **IBM Heron / Qiskit Runtime** | dt = 4 ns | **only `if_test`**, ≤32-bit operand, no nesting, no measurement/reset inside conditionals, no `for`/`while`/`switch` | job fails validation (26.8 M instructions per qubit budget) | about 600 ns ([execute dynamic circuits](https://quantum.cloud.ibm.com/docs/en/guides/execute-dynamic-circuits); [job limits](https://quantum.cloud.ibm.com/docs/en/guides/dynamic-circuits-considerations)) |
| **QubiC 2.0** | 500 MHz, 72-bit timed pulse commands | `sync` resets time references at join; function-processor call **halts the core** until result | unspecified | inter-FPGA about 450 ns; about 1600 ns start-to-conditional-pulse including 1 µs readout ([QubiC 2.0](https://arxiv.org/html/2309.10333v1); [multi-FPGA](https://arxiv.org/html/2506.09856v1)) |
| **QICK tProc** | 48-bit counter, per-channel queues | conditional plus jump 42 ns [older] | v2 assembler rounds swept waits to maximum; source has a TODO to add safety checks of wait vs sync vs pulse | 184–211 ns digital feedback [older] ([Stefanazzi et al.](https://arxiv.org/pdf/2110.00557); [asm_v2.py](https://github.com/openquantumhardware/qick/blob/main/qick_lib/qick/asm_v2.py)) |
| **eQASM / CC-Light** [older] | 20 ns cycle; `QWAIT`/`QWAITR` timing points | fast conditional = cancel-in-place via execution flags (timeline unchanged); comprehensive feedback `FMR`→`BR` **stalls** and shifts all later timing points | unspecified | not given ([eQASM](https://ar5iv.labs.arxiv.org/html/1808.02449)) |

Four 2025–2026 research designs make the commit point first-class. They also show what a program-level contract must *not* duplicate.

**TIDE** separates a "runtime-revisable future" from a "hardware-timed committed-event stream". It measures every descriptor committed at least one timing-domain cycle (2.353 ns) before dispatch. A late commit is "retained and presented at the first eligible output cycle", which is a silent delay rather than an exception ([TIDE](https://arxiv.org/html/2608.15173)).

**QCORE** is simulation only. It checks a deadline/freshness/version triple on fast feedback results and defers or logs late ones. Its P99 latencies are normalised to L_max and explicitly not established in RTL or silicon ([QCORE](https://arxiv.org/html/2608.06875)).

**QuCtrl-BELL** fixes feedback phases at compile time (barrier → count → broadcast → branch). It measures 690 ns, with a residual that "depends on the instructions preceding the branch" ([BELL](https://arxiv.org/html/2605.22433)).

**NVQLink** defines four time domains and a blocking `device_call` that "must complete execution before quantum operations can resume". It reports a 3.96 µs *sample maximum* RTT, not a bound ([NVQLink](https://arxiv.org/html/2510.25213v2)).

**[Synthesis]** These are runtime and hardware mechanisms. They guarantee what happens *after* commitment or detect violations *during* execution. None of them gives a program semantics or a static check that a given dynamic program will never reach the late path. They are the substrate a contract describes, not competitors to it.

Two published-latency facts matter most for verification. First, **no vendor publishes a certified worst case for any feedback path**. Figures come as single measurements, marketing upper bounds, route tables, sample statistics or simulated percentiles. Second, the FPGA-local tier is cycle-countable in principle: Q1 jumps cost 16 ns taken and 4 ns not taken, and QICK's conditional is 16 clocks. Network tiers (NVQLink, Ethernet decoders) can only be statistical today.

---

## Languages leave branch timing unspecified, and vendors fill the hole three ways

At the language level, time is either compile-time-only or absent. OpenQASM 3 has `duration`, `delay`, `stretch`, `box` and `durationof`. It states that "stretch variables are resolved at compile time" and "all operations on durations happen at compile time". `box[d]` imposes "hard constraints" useful when a duration "is runtime dependent", but the spec does not say how a box is enforced ([OpenQASM timing](https://openqasm.com/language/delays.html)). The only hard branch-duration rule is inside `defcal`: "each branch of the control flow must have definite and equivalent duration resolvable at compile time" ([OpenQASM pulses](https://openqasm.com/language/pulses.html)). At circuit level, the duration of an `if` is unspecified. The Quil spec (draft) defines `DELAY` and `FENCE` informally, gives `JUMP-WHEN` and measurement no timing, and says "the precise mechanism by which WAIT works is deliberately unspecified" ([Quil spec](https://quil-lang.github.io/)). QIR Adaptive, CUDA-Q Quake and Catalyst carry no timing at all, so user timing intent does not survive lowering through them.

The only formalisation effort on OpenQASM 3 found is a parser. QASM-TS 2.0 produces a strongly-typed AST and lists a formal type theory as future work ([arXiv:2412.12578](https://arxiv.org/html/2412.12578v2)). Qiskit 2.1 offers the most practical carrier for contracts. `BoxOp` accepts custom `Annotation` objects, its `duration` may be a `Duration`/`Stretch` expression, and annotations round-trip through `qasm3.dump/load` with handlers and QPY v15 ([Qiskit 2.1 notes](https://quantum.cloud.ibm.com/docs/api/qiskit/release-notes/2.1)). IBM removed user pulse access on 3 February 2025, and Qiskit 2.0 deleted `qiskit.pulse` ([Qiskit 2.0 notes](https://eu-de.quantum.cloud.ibm.com/docs/en/api/qiskit/release-notes/2.0)). Users can still *request* timing with delay, stretch and box, but they cannot define it below the gate. That makes a contract between IR and backend the only remaining lever.

Vendors resolve branch timing in exactly three ways. The proposal's three policies name them.

| Policy | Mechanism | Instances | Guarantee | Price |
|---|---|---|---|---|
| **Equalize** (EQ) | pad shorter branch, wait worst-case result latency | Q1 `else_duration`; QUA conditional `play`; eQASM execution flags; QCC VSM masking; OpenPulse `defcal` rule | timeline independent of outcome and latency | idle = (hi − actual latency) + (longest − taken branch) |
| **Sync-at-join** (SYNC) | runtime barrier, resume together | QUA non-deterministic align; QubiC `sync`; eQASM `FMR`→`BR`; BELL barrier; IBM block restart | bounded only if the sync gap is bounded, and **no vendor publishes that bound** | sync gap; jitter after join |
| **Exposed timeline** (EXP) | programmer owns the cursor; violation detected | ARTIQ `now_mu`, slack, underflow | none static; runtime detection (or silent drop) | programmer burden; untestable rare paths |

A fourth, degenerate option is **restriction**. IBM forbids loops, nesting and measurement inside conditionals, so most of the question never arises ([IBM](https://quantum.cloud.ibm.com/docs/en/guides/execute-dynamic-circuits)). **[Synthesis]** A circuit-level program cannot today say which policy it expects, so the same `if` has backend-dependent timing. The portability argument in the Decision rests on this fact.

---

## Fault tolerance turns timing into correctness

In fault-tolerant execution, timing is no longer a fidelity term but a correctness and throughput constraint. Gidney and Ekerå assume "a surface code cycle time of 1 microsecond, and a reaction time of 10 microseconds" ([arXiv:1905.09749](https://arxiv.org/abs/1905.09749)). Google's below-threshold experiment decoded in real time with an "average decoder latency of 63 μs at distance-5" against a 1.1 µs cycle, about six times that assumption ([arXiv:2408.13687](https://arxiv.org/abs/2408.13687)). Skoric et al. restate Terhal's backlog argument. If syndrome generation outpaces processing (f > 1), a T-depth-k program takes at least c·f^k time. They separate throughput from reaction latency τ and give the logical clock as τ_clock = d·τ_rd + τ ([Skoric et al.](https://arxiv.org/pdf/2209.08552)).

Synchronisation is the second FT timing constraint. Before a merge or split, lattice-surgery patches must begin syndrome cycles together, and the out-of-phase slack must be absorbed. Maurya and Tannu measure the policy choice. Active slack spreading cuts logical error up to 2.4×. At d=7 with 500 ns slack, Passive gave 278 logical errors against 232 for Active. Hybrid cuts error up to 3.4× at d=15 with τ = 1000 ns. Desynchronisation comes from heterogeneous code cycles, non-deterministic magic-state cultivation retries, defects, twist-based surgery and chip-to-chip links, at about 1–11 synchronisations per EC cycle ([arXiv:2506.10258](https://arxiv.org/abs/2506.10258)). Their result is platform-dependent: on neutral atoms, Active gains only about 2% and Hybrid makes things worse. That is exactly why the slack-absorption policy belongs in a contract instead of being hard-coded.

**[Synthesis]** Three FT obligations map directly onto the proposal:

- **Reaction deadline.** For every conditional correction (magic-state injection, teleported gates), the time from last syndrome sample to first conditional pulse is ≤ D. A static checker can certify this given per-tier latency bounds.
- **Sync bound.** Every merge/split point has bounded inter-patch slack, absorbed by a declared policy.
- **Throughput.** The decoder service rate is at least the syndrome rate.

The first two are exactly the contract's `within[D]` and `sync{…}` clauses below. The third is a rate obligation of the same form as eQASM's R_req ≤ R_allowed.

---

## Real-time systems and planning already supply the theory

The real-time community solved deterministic timing under uncertain inputs decades ago, and the quantum stack keeps reinventing it without citation. The earlier stack-wide sweep found no use of Lustre, Esterel, Giotto/LET, PRET or Lingua Franca in quantum control.

**Logical vs physical time, with conditional determinism.** Lingua Franca separates a logical timeline (tags in T × U) from physical time. Its distributed determinism is conditional on a clock-sync bound E, a network-latency bound L and execution-time bounds X. "When any component sees messages out of timestamp order, one of the assumptions has been violated", so violations are detectable rather than prevented ([Lohstroh et al., TECS 2024](https://par.nsf.gov/servlets/purl/10554371)). Giotto's logical execution time gives value and time determinism if WCET fits within the LET ([Henzinger et al.](https://api.crossref.org/works/10.1109/JPROC.2002.805825)). **[Synthesis]** A mid-circuit measurement is an LF "physical action": its *value* is nondeterministic, but its *timing* can be logically bounded. "Deterministic modulo measurement outcomes" is the quantum analogue of LF's guarantee.

**Timing as ISA semantics.** The 2008 PRET design added `deadi`/`dead` instructions that block until a deadline register reaches zero, enforcing a lower bound on segment time. A missed deadline "did nothing", and a missed-deadline exception was future work ([Lickly et al. TR](https://www.cs.columbia.edu/~sedwards/papers/lickly2008predictable-tr.pdf)). FlexPRET (RTAS 2014, DOI 10.1109/RTAS.2014.6925994) extends RISC-V with nanosecond timing instructions. `interrupt_on_expire` aborts a reaction that overruns ([NG-RES 2025](https://drops.dagstuhl.de/storage/01oasics/oasics-vol128-ng-res2025/OASIcs.NG-RES.2025.1/OASIcs.NG-RES.2025.1.pdf)). `get_time` and `delay_until` are **unverified**. These two primitives, wait-until (lower bound) and abort-on-overrun (upper bound), correspond to `delay`/`stretch` padding and to a feedforward deadline handler.

**WCET.** The standard pipeline is CFG reconstruction, value and loop-bound analysis, microarchitectural analysis, then IPET path analysis as an ILP ([Wilhelm et al.](https://api.crossref.org/works/10.1145/1347375.1347389); [Li & Malik](https://api.crossref.org/works/10.1145/217474.217570)). **[Synthesis]** Quantum control is far easier than CPU WCET. Pulse durations are calibrated constants, there are no caches, and the hard parts are classical feedforward, path enumeration and synchronisation. The classical stream that refills the RT queue still needs a WCET, for example from the Q1 cycle table, to discharge underflow.

**Temporal networks.** These are the right algebra for measurement-conditioned timing. The facts below are verified unless marked.

| Formalism | What it adds | Decision problem | Complexity (verified source) |
|---|---|---|---|
| STN (Dechter, Meiri, Pearl 1991) | difference constraints x_j − x_i ≤ c | consistency = no negative cycle | O(n³) Floyd–Warshall (textbook; body not re-opened) ([Crossref](https://api.crossref.org/works/10.1016/0004-3702(91)90006-6)) |
| STNU | contingent links [l,u] chosen by nature | SC ⇒ DC ⇒ WC | SC poly, **DC poly**, WC co-NP-complete ([Sumic & Vidal slides](https://www.lirmm.fr/time2024/files/WeakControllabilityOfSTNUsTIME2024.pdf)) |
| STNU DC algorithms | — | — | MMV 2001 pseudo-polynomial; **Morris & Muscettola 2005 O(N⁵), the first truly polynomial**; Morris 2006 O(N⁴); **Morris 2014 O(N³)** ([Hunsberger survey PDF](https://www.cs.vassar.edu/~hunsberg/__papers__/springer-2015-acta.pdf)); **Cairo–Hunsberger–Rizzi 2018 RUL⁻ O(MN + K²N + KN log N)** ([LIPIcs TIME 2018.8](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.TIME.2018.8)) |
| CSTN (Tsamardinos, Vidal, Pollack CTP 2003) | observation nodes; labels on constraints | dynamic consistency | **PSPACE-complete (Cairo & Rizzi)** ([arXiv:1608.08545](https://arxiv.org/abs/1608.08545)); singly-exponential algorithm, coNP-hard (Comin & Rizzi) ([arXiv:1505.00828](https://arxiv.org/abs/1505.00828)) |
| CSTNU | CSTN + contingent links | DC | first sound-and-complete algorithms (Hunsberger & Posenato) ([LIPIcs TIME 2018.14](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.TIME.2018.14)) |
| Tooling | Java library + editor, v7.2, STN…CSTNU, PSTN experimental | — | live as of 2026-09-10 ([CSTNU Tool](https://profs.scienze.univr.it/~posenato/software/cstnu/); SoftwareX 17:100905) |

The comparatives to keep straight are **unverified**: the attribution of WC co-NP-completeness to Morris & Muscettola 1999, the venues TIME 2015/2016 for the two Rizzi papers, and Comin–Rizzi being exponential only in the number of propositions.

In RUL⁻, K counts contingent time-points. **[Synthesis]** For quantum programs, K is roughly the number of timing-relevant measurements, which is usually much smaller than N. That puts STNU DC near O(MN) in practice. CSTN hardness bites only when many outcome bits influence timing within one window.

**Timed automata.** UPPAAL uses zones, the same difference-constraint algebra, and reachability is PSPACE-complete ([Alur & Dill](https://doi.org/10.1016/0304-3975(94)90010-8)) [older, not re-fetched]. UPPAAL could act as an alternative back end. It is also what the closest competitor group uses.

**Expected runtime.** The ert calculus of Kaminski, Katoen, Matheja and Olmedo reasons about expected runtimes of probabilistic loops ([J. ACM 65(5) 2018](https://api.crossref.org/works/10.1145/3208102)). The proof rules were not re-opened in this pass. The 2026 quantum weakest-pre-expectation work handles infinite expected runtime through "reward statements", which count abstract cost, not wall-clock time with hardware latencies ([arXiv:2607.12532](https://arxiv.org/abs/2607.12532)).

---

## Prior art bounds the claim to "compiled dynamic programs, physical time, checked against hardware contracts"

| Work | What it does | What it does not do | Effect on claims |
|---|---|---|---|
| **GRAMPUS** (Adams, Bernardy, Perticone, Pope; TYPES 2025 / PLanQC 2026) | graded linear type theory with durations as grades; pulse-schedule model; sound, complete; Agda artifact; ALAP scheduler as right inverse of erasure ([arXiv:2510.03130](https://arxiv.org/pdf/2510.03130)) | **no measurement, classical control, branching or loops**; lists them as future work | cannot claim "first duration type system"; can claim the measurement/branch extension. Chalmers could extend it; move fast or collaborate. |
| **TqCCS** (Fernandes, MSc, U. Minho 2019) | quantum process algebra merging qCCS and CQP, extended with Timed-CCS-style real time; includes measurement ([PDF](https://repositorium.sdum.uminho.pt/bitstream/1822/80754/1/Vitor%20Emanuel%20Goncalves%20Fernandes.pdf)) | aim is studying the effect of time on quantum states; no schedule verification, branch policies or hardware contracts seen (chapters not fully read) | **cannot claim "first timed quantum calculus with measurement"** |
| **UPPAAL quantum protocols** (Christensen, Kristensen, Larsen, Mikučionis, Srba, Walsted; CAV 2026, LNCS 16684:372–386) | encodes states, operations and measurements into UPPAAL timed automata; exhaustive and statistical model checking under timing and decoherence ([AAU](https://vbn.aau.dk/da/publications/analysis-and-verification-of-quantum-communication-protocols-in-u/)) | communication protocols, hand-built models; not IR/circuit programs or controller contracts | **closest competitor group**; differentiate on automatic IR extraction, policies, contracts, counterexamples |
| Aalborg temporal framework (arXiv:2602.12459) | slot model with T_q, T_c, feedforward and adjacency constraints for measurement scheduling in quantum networks ([arXiv](https://arxiv.org/html/2602.12459v1)) | network-level, not an STN, no checker | same group: signals direction of travel |
| **TIDE / QCORE / NVQLink / BELL** | runtime commit boundaries, deadline/freshness guards, blocking `device_call`, fixed-phase feedback | no program semantics, no static checking | contract *describes* these; they supply instances |
| **TUM dynamic-circuit analyses** (Fulginiti, Chen, Mendl, Seidl) | sound compile-time simplification of classically controlled ops (about 50%, up to 80% less feedforward) and branch-aware constant propagation ([arXiv:2605.28439](https://arxiv.org/pdf/2605.28439); [arXiv:2606.02018](https://arxiv.org/pdf/2606.02018)) | logical only; latency is motivation; hardware cost models future work | complementary; their path-sensitive abstract interpretation is reusable machinery |
| **Riverlane control-stack DV** (DVCon) | UVM, SVA cycle-latency assertions, formal on interconnects ([arXiv:2310.05229](https://arxiv.org/html/2310.05229v1)) | hardware blocks only; no program-level deadlines | its block bounds are the ideal *certified* provenance inputs |
| Quantum Orchestras (arXiv:2607.09605) | denotational semantics for recursive hybrid programs ([arXiv](https://arxiv.org/abs/2607.09605)) | no physical time | untimed baseline semantics |
| qwp-ert line (arXiv:2607.12532; 1911.11247) | expected runtime of quantum programs | abstract cost, expected not worst case | cite for RUS; contrast with worst-case physical time |
| QASM-TS 2.0 (arXiv:2412.12578) | typed OQ3 parser | no timing semantics | potential front end |
| q1lens (PyPI, 2026) | cross-layer Q1ASM visualiser ([PyPI](https://pypi.org/project/q1lens/)) | execution-based; no checks | evidence of demand |
| QaiJi IR (arXiv:2609.29305) | eight-layer IR with "five-axis semantic contract" (data, semantics, lowering, runtime, verification); records a classical-feedback model and measurement-to-condition edges ([arXiv](https://arxiv.org/abs/2609.29305)) | abstract defines no timing (no durations, latency bounds, deadlines) and no timing checker; no physical feedback loop | closest IR-level neighbour for C3; contrast in related work (abstract checked; read full text) |

Three groups of claims remain **unverified from the papers themselves**: that CoqQ, QWIRE, SQIR/VOQC, Silq and Qafny have no wall-clock time model; IBM's block-restart behaviour after control flow; and LabOne Q `match`/`case` padding. Each needs a one-line check before submission.

The defensible novelty statement is: **the first timed semantics for compiled dynamic-circuit programs with measurement-conditioned branching and bounded loops, which (i) states and proves determinism modulo outcomes under explicit branch-timing policies, (ii) reduces timing safety to (C)STNU controllability, and (iii) checks programs statically against a portable, provenance-typed hardware timing contract, returning counterexamples.**

---

## The proposed solution: semantics, policies, contracts and a checker

The design has four layers, each of which can be published separately. The core calculus gives meaning. Policies are typing rules. Contracts supply numbers with provenance. The checker discharges obligations through a temporal-network encoding.

```
           ┌────────────── program side ──────────────┐     ┌──────── hardware side ────────┐
 OpenQASM 3 / Qiskit circuit                            Timing contract C (per backend)
   + policy annotations (BoxOp Annotation: eq/sync/exp)   timebase, grids, latencies+provenance,
   + deadlines (within[D] from c)                         commit lead, capacity, late policy
           │                                                        │
           ▼                                                        │
 [1] Front end → TQ core AST (resolve stretch, durationof)          │
 [2] Elaborate policies: EQ pads, SYNC joins, EXP cursor ops; unroll for; cap while
 [3] Labelled timed event graph (resources × outcome labels)  ◄────┘
 [4] Obligation generator O1–O9, each tagged with provenance of every latency used
 [5] Solver tiers:  (a) STN / Bellman–Ford fast path (EQ-only programs)
                    (b) per-scenario STN enumeration (k timing-relevant bits small)
                    (c) CSTNU DC (RUL⁻-style own impl. or Posenato CSTNU Tool)
                    (d) SMT (Z3 difference logic / LIA) for rates, parameters, grids
 [6] Verdict: PROVED | PROVED-UNDER{assumptions, provenance} | REFUTED(ω, θ, event, obligation) | UNKNOWN
 [7] Counterexample replay in reference executor (ARTIQ-like | Q1-like | IBM-like)
```

### A small core: timed OpenQASM 3 ("TQ")

The core keeps OpenQASM 3's timing constructs and adds three things: a policy tag on each branch and loop, an iteration cap on `while`, and an explicit deadline form. All durations are integers in the backend's dt. Latencies are intervals carrying a provenance class κ.

```
d  ::= n·dt | d + d | max(d, d) | durationof(s)              durations (static)
ℓ  ::= [lo, hi]^κ          κ ∈ {cert, cyc, mmax(n), pctl(p,ρ), mσ, vendor}
e  ::= c | x | n | e ⊕ e | ¬e                                  classical expressions
π  ::= EQ | SYNC(Δ, G) | EXP                                   branch-timing policy
s  ::= skip
     | U q̄                          gate; duration δ_U from contract
     | delay[d] q̄ | barrier q̄
     | c ← measure q                duration δ_M; result valid after ℓ_M^tier
     | reset q
     | s ; s
     | box[d] s                     hard duration constraint
     | if⟨π⟩ (e) s else s
     | for i ∈ [0, n) s             n static
     | while⟨π, N⟩ (e) s exhaust s  iteration cap N, exhaust handler
     | x ← call⟨ℓ⟩ f(ē)             blocking extern / device_call
     | within[D] from c s           s must start ≤ D after c is valid
```

**Semantic domains.** Resources R are qubits, frames and the classical issue core. A configuration is ⟨s, τ, σ, V⟩, where τ : R → ℕ is a per-resource clock (OpenPulse's "frame as a logical clock"), σ is the classical store, and V maps each bit to its result-valid time. Nature supplies an outcome stream ω ∈ {0,1}^ℕ and a latency realisation θ, which picks one value θ_i ∈ [lo_i, hi_i] for every contingent occurrence. The big-step judgement is

```latex
\omega,\theta \vdash \langle s,\tau,\sigma,V\rangle \Downarrow \langle \tau',\sigma',V',\mathit{tr}\rangle
\quad\text{or}\quad
\omega,\theta \vdash \langle s,\tau,\sigma,V\rangle \Downarrow \lightning(v)
```

Here tr is a trace of timestamped events (op, resource, t), and ↯(v) is a violation of kind v ∈ {underflow, deadline, gap, capacity, stale}, handled per the contract's late policy. Two representative rules:

```latex
\frac{t_0=\max_{q\in\bar q}\tau(q)}
     {\langle U\,\bar q,\tau,\sigma,V\rangle \Downarrow
      \langle \tau[\bar q\mapsto t_0+\delta_U],\,\sigma,\,V,\,[(U,\bar q,t_0)]\rangle}
\qquad
\frac{t_0=\tau(q)\quad b=\omega_j\quad t_v=t_0+\delta_M+\theta_i}
     {\langle c\leftarrow \mathtt{measure}\,q,\tau,\sigma,V\rangle \Downarrow
      \langle \tau[q\mapsto t_0+\delta_M],\,\sigma[c\mapsto b],\,V[c\mapsto t_v],\,[(M,q,t_0)]\rangle}
```

### "Deterministic modulo measurement outcomes", stated precisely

Let Θ_C be the latency realisations admitted by contract C, and let Ω_P be the outcome sequences consistent with P. Write t_e(ω, θ) for the timestamp of event e.

```latex
\textbf{Definition (DMO).}\; P \text{ is deterministic modulo outcomes under } C \text{ iff}\\
\text{(i) safety: } \forall \omega\in\Omega_P,\ \forall\theta\in\Theta_C:\ \text{exec}_C(P,\omega,\theta)\ \text{has no } \lightning;\\
\text{(ii) latency-independence: } \forall \omega,\ \forall \theta,\theta'\in\Theta_C:\ \mathit{tr}(P,\omega,\theta)=\mathit{tr}(P,\omega,\theta');\\
\text{(iii) causality: } t_e(\omega,\theta) \text{ depends only on } \{\omega_j : \mathrm{hi}(V(c_j)) \le t_e\}.
```

Condition (iii) rules out schedules that "know the future". It is exactly the dynamic part of dynamic controllability. Two weakenings matter in practice:

```latex
\Delta\text{-DMO: (i), (iii), and } |t_e(\omega,\theta)-t_e(\omega,\theta')| \le \Delta_e \text{ for all } e;
\qquad
\text{Safe-only (EXP): (i) and (iii).}
```

**Conjectured theorem (to be proved; [Synthesis]).** If every branch is EQ, every loop is bounded or capped, every `call` has a latency bound, and P type-checks with all obligations discharged, then P is DMO. If some branches are SYNC(Δ_k), P is Δ-DMO with Δ_e = Σ_{k ∈ joins before e on its path} Δ_k. If a SYNC join re-anchors to an absolute timing point (QubiC-style reference reset), the sum restarts there. EXP programs are at best safe-only.

### The three policies as typing rules

Judgements have the form Γ ⊢ s : [l, u]. This is the single-resource simplification; the real system uses one interval per resource plus a set of emitted obligations. Γ records, for each bit c, its valid-time interval Γ(c) = [a, b] relative to the current point.

```latex
\textsc{(If-EQ)}\quad
\frac{\Gamma\vdash s_1:[d_1,d_1]\quad \Gamma\vdash s_2:[d_2,d_2]\quad \Gamma(c)=[a,b]\quad w=\max(0,b)\quad d=\max(d_1,d_2)}
     {\Gamma\vdash \mathtt{if}\langle\mathrm{EQ}\rangle(c)\,s_1\,\mathtt{else}\,s_2:[w+d,\;w+d]}
\;\leadsto\; s_i' = \mathtt{delay}[w-\theta];\,s_i;\,\mathtt{delay}[d-d_i]
```

```latex
\textsc{(If-SYNC)}\quad
\frac{\Gamma\vdash s_i:[l_i,u_i]\quad \Gamma(c)=[a,b]\quad \lambda=[\lambda_l,\lambda_u]^{\kappa}\quad
(b-a)+(\max_i u_i-\min_i l_i)+(\lambda_u-\lambda_l)\le\Delta\quad \text{gap}_r\le G\ \forall r}
     {\Gamma\vdash \mathtt{if}\langle\mathrm{SYNC}(\Delta,G)\rangle(c)\,s_1\,\mathtt{else}\,s_2:
      [\max(0,a)+\min_i l_i+\lambda_l,\;\max(0,b)+\max_i u_i+\lambda_u]}
```

```latex
\textsc{(If-EXP)}\quad
\frac{\Gamma\vdash s_i:[l_i,u_i]\quad \Gamma(c)=[a,b]}
     {\Gamma\vdash \mathtt{if}\langle\mathrm{EXP}\rangle(c)\,s_1\,\mathtt{else}\,s_2:
      [\max(0,a)+\min_i l_i,\;\max(0,b)+\max_i u_i]\ \ \text{emit } \{\text{slack}\ge\Delta_{\text{lead}}\ \text{on every path}\}}
```

```latex
\textsc{(Seq)}\ \frac{\Gamma\vdash s_1:[l_1,u_1]\quad \Gamma'\vdash s_2:[l_2,u_2]}{\Gamma\vdash s_1;s_2:[l_1+l_2,\,u_1+u_2]}
\qquad
\textsc{(For)}\ \frac{\Gamma\vdash s:[l,u]}{\Gamma\vdash \mathtt{for}\ i\in[0,n)\ s:[n l,\,n u]}
\qquad
\textsc{(Box)}\ \frac{\Gamma\vdash s:[l,u]\quad u\le d}{\Gamma\vdash \mathtt{box}[d]\,s:[d,d]}
```

The **EQ elaboration** makes the price visible. The branch always waits until the worst-case valid time b, then pads to the longer branch. The **idle cost** of determinism is (b − θ) + (d − d_taken). SYNC trades that idle for a runtime barrier whose gap λ must be bounded by the contract. No vendor publishes such a bound, so SYNC verdicts on real targets will be "proved under measured-max assumptions". EXP is ARTIQ's model: it costs nothing in idle, guarantees nothing about timing, and its safety obligation is DC of the encoded network.

| Policy | Property delivered | Controllability notion (§ below) | Vendor instance | Idle price |
|---|---|---|---|---|
| EQ | DMO | SC over latencies, outcome-labelled | Q1 `set_cond`, QUA conditional `play` | (hi − θ) + branch imbalance |
| SYNC(Δ,G) | Δ-DMO | DC with bounded wait | QUA align, QubiC `sync`, BELL barrier | λ, bounded only if published |
| EXP | safe-only | DC | ARTIQ | none; correctness on programmer |

### Encoding a dynamic program into a CSTNU

**[Synthesis]** The encoding follows Hunsberger and Posenato's CSTNU structure: time-points, labelled requirement constraints, contingent links and observation time-points with propositions.

| Program element | CSTNU element |
|---|---|
| start/end of each op on each resource | time-points X_s, X_e, labelled with the conjunction of branch conditions enclosing it |
| gate duration δ_U | requirement X_e − X_s = δ_U (two edges) |
| per-resource order | X_s(next) − X_e(prev) ≥ 0 (no overlap) |
| measurement end → result valid | **contingent link** (X_e(M), [lo, hi], C_c) |
| outcome bit c | **observation time-point** P_c? at C_c, proposition p_c |
| `if (c) s1 else s2` | nodes of s1 labelled p_c, s2 labelled ¬p_c; join labelled with outer label |
| EQ policy | join constraints forcing equal end times for both labels; branch start ≥ X_e(M) + hi |
| SYNC(Δ) | contingent link for the sync gap λ; join-spread constraint ≤ Δ |
| `within[D] from c s` | X_s(first op of s) − C_c ≤ D |
| unplanned idle (O4) | X_s(next) − X_e(prev) ≤ G_r unless the gap is a declared `delay`/DD window |
| commit lead (O1) | issue-time point I_e (classical WCET) with X_s(e) − I_e ≥ Δ_lead |
| blocking `call` | contingent link of length WCET(f) + RTT; following ops ordered after it |

**Correspondences to prove ([Synthesis], conjectures).**

- **EXP safety is DC.** P under EXP is safe iff N(P) is dynamically controllable. A dispatcher may react only to observed propositions and observed contingent durations, which is condition (iii).
- **DMO is a hybrid notion.** P is DMO iff N(P) is controllable strongly over contingent durations and dynamically over propositions. Every contingent link is replaced by requirement edges at both extremes, and the result is checked for CSTN dynamic consistency.
- **EQ-only, outcome-independent structure collapses to an STN.** If every branch is EQ and no later constraint depends on which branch ran, the label space collapses and the problem is plain STN consistency, solvable in polynomial time.

The checker should try the cheap tiers first.

| Program class | Reduction | Cost |
|---|---|---|
| EQ-only, labels collapsible | STN consistency | O(n³) (Floyd–Warshall) or Bellman–Ford |
| k timing-relevant bits, small k | per-scenario STNs (2^k), SC over latencies | 2^k × STN |
| EXP with latencies, no timing-relevant labels | STNU DC | RUL⁻ O(MN + K²N + KN log N) |
| general | CSTNU DC | sound-and-complete propagation; PSPACE-complete in general (CSTN) |

The RUS loop and QEC rounds keep k per window small. Each round's outcomes affect only that round's correction, so windows can be checked compositionally, re-anchoring at each round boundary. **[Synthesis]** This compositional, windowed check is a likely technical contribution, because the general CSTN problem is PSPACE-complete.

### A cross-layer timing-contract vocabulary

The contract is a per-backend document (JSON/TOML), separate from the program. Every numeric field carries provenance.

| Clause | Content | Instances in the wild | Checker obligation |
|---|---|---|---|
| `timebase{unit, grid[op-class], domain}` | dt; grids per op class | IBM dt 4 ns, 16 dt acquire alignment; LabOne Q 200 ns feedback grid; ARTIQ 8 ns coarse | **O8** grid/alignment of every timestamp |
| `timeline{cursor, commit(Δ_lead), late_policy}` | where commit happens and how much lead is needed; late ∈ {raise, drop_log, delay, defer_round, halt, compile_error} | ARTIQ underflow raise; TIDE ≥1 cycle lead and delay-to-next-cycle; Q1 halt; QCORE defer | **O1** slack ≥ Δ_lead at every commit |
| `issue_cost{instr→cycles, taken/not}` , `refill_rate` | classical WCET model | Q1: 4 ns set/move, 12 ns ALU, 16/4 ns jump, 24/4 ns loop | **O1** via classical WCET; eQASM R_req ≤ R_allowed |
| `capacity{events_per_cycle, fifo_depth, monotonic_lane, one_per_ts}` | resource-rate limits | ARTIQ 8 SED lanes; TIDE 32-entry FIFOs; Qblox 32-entry feedback queue; IBM 26.8 M instr/qubit | **O5** capacity (catches ARTIQ's silent drops statically) |
| `latency{src→dst, tier, [lo,hi], provenance, data_dependent}` | feedback paths | Qblox 160/250/472 ns; ZI <550 ns; IBM about 600 ns; NVQLink 3.96 µs max | **O2** result-valid before use |
| `branch{class ∈ predicated, equalized, resync(λ), forbidden}` | what the backend does at an `if` | Q1 predicated; QUA resync; IBM forbidden nesting | policy compatibility: program π ⊑ backend class |
| `dep{r, valid_at, deadline, freshness, version}` | consumer constraints on results | QCORE triple; eQASM Qi-valid | **O2**, **O3** deadline, staleness |
| `domain_call{f, blocking, WCET, RTT}` | cross-domain calls | NVQLink `device_call` | **O6** slack_at_call ≥ WCET(f) + RTT_max |
| `sync{participants, cost(n, tier)}`, `reconfig{safe_point, defer_rounds}` | barriers, reconfiguration | QubiC `sync`, QUA cross-FEM, BELL barrier; TIDE DIPU/DISO, QCORE one-round defer | **O7** join bound; FT patch-sync slack |
| `idle{G_r, dd_windows}` | max unplanned idle per resource | derived from T2 and policy | **O4** no unplanned idle gap |
| `loop{bound | cap N, p_min}` | iteration limits | RUS, QEC rounds | **O9** bounded WCET, invariant slack |

**Latency provenance classes.** These form a chain ordered by evidential strength. The checker propagates the weakest class used in any proof to the verdict.

| Class | Meaning | Example | May discharge hard deadline? |
|---|---|---|---|
| `cert` | formally certified WCET | none public for any feedback path; Riverlane-style SVA block bounds are the nearest ([arXiv:2310.05229](https://arxiv.org/html/2310.05229v1)) | yes |
| `cyc` | cycle-counted design bound | Q1 jump 16 ns; QICK conditional 16 clocks | yes, if the design model is trusted |
| `mmax(n)` | sample maximum over n | NVQLink 3.96 µs over 1,000 samples | no; "proved under assumption" |
| `pctl(p, load)` | percentile under load | QCORE P99 1.984 L_max at ρ = 0.8 [sim] | no; probabilistic verdict |
| `mσ` | mean ± σ | Google decoder 63 ± 17 µs | no; advisory |
| `vendor` | marketing bound | ZI "<550 ns" [vendor claim] | no; advisory |

**[Synthesis]** This typing is what makes the checker honest. A verdict "PROVED-UNDER{IBM ff ≤ 600 ns : mmax(?)}" tells a reader exactly which unpublished bound the guarantee rests on. It also gives vendors a concrete, small request: publish these fields.

### Checker obligations

```latex
\begin{aligned}
&\textbf{O1 (no underflow)} && \forall e:\ t_e - \mathrm{issue}(e) \ge \Delta_{\text{lead}},\ \ \mathrm{issue}(e)=\text{WCET of classical stream up to } e\\
&\textbf{O2 (result ready)} && \forall\ \text{use of } c \text{ at } t:\ t \ge t^{M}_{\text{end}} + \mathrm{hi}(\ell^{\text{tier}}_M)\ \ (\text{EQ}),\ \text{or dispatched on observation (EXP/SYNC)}\\
&\textbf{O3 (deadline)} && t_{\text{first}(s)} - V(c) \le D\quad \text{for every } \mathtt{within}[D]\ \mathtt{from}\ c\ s\\
&\textbf{O4 (no unplanned idle)} && \forall r,\ \text{consecutive ops}:\ t_{s}(\text{next}) - t_{e}(\text{prev}) \le G_r \ \lor\ \text{gap is declared}\\
&\textbf{O5 (capacity)} && |\{e : \lfloor t_e/g_c\rfloor = k\}| \le \text{lanes},\ \text{FIFO occupancy} \le \text{depth},\ \text{lane timestamps strictly increasing}\\
&\textbf{O6 (domain call)} && \text{slack at call} \ge \mathrm{WCET}(f) + \mathrm{RTT}_{\max}\\
&\textbf{O7 (sync)} && \lambda_u - \lambda_l + \text{branch spread} \le \Delta\\
&\textbf{O8 (grid)} && t_e \equiv 0 \pmod{g_{\text{class}(e)}}\\
&\textbf{O9 (loops)} && \text{bounded: } n\cdot u;\ \text{capped: } N\cdot u + u_{\text{exhaust}};\ \text{slack after iteration} \ge \text{slack before}
\end{aligned}
```

Counterexamples are concrete: an outcome prefix ω, a latency realisation θ (extreme values from the contingent intervals), the violating event and the obligation. They replay deterministically in the reference executor. Most refutations of SC need only the interval endpoints, so the counterexample search is a finite enumeration over {lo, hi} per contingent link along the offending path.

### Two worked examples

**Teleportation-style feedforward on an IBM-like contract.** Take a Bell pair on q1, q2, a Bell-basis measurement of q0, q1 with outcome c, and `if⟨SYNC(Δ)⟩(c) { x q2 }`. With measurement 1.66 µs and feedforward about 600 ns, q2 idles for about 2.26 µs between entanglement and correction, independent of the outcome. That is about 2.3% of a 100 µs T2 before DD ([IBM QPU info](https://quantum.cloud.ibm.com/docs/en/guides/qpu-information); [IBM blog](https://www.ibm.com/quantum/blog/utility-scale-dynamic-circuits)). The checker proves O2 and O4 only if `latency{ff}` has an upper bound. IBM's 600 ns is a reported constant with unknown provenance, so the verdict is PROVED-UNDER{ff ≤ 600 ns : vendor}. Under EQ, the elaborated program waits to the declared upper bound and pads the empty `else` with `delay[δ_X]`. The result is timing-identical on both outcomes, which is the precondition for compile-time DD across the window.

**An ARTIQ input branch.** The manual's example counts edges in a 500 ns window. If the count exceeds 20, it inserts `delay(2*us)` before `pulse(500*ns)`, because `count()` leaves the kernel in negative slack ([ARTIQ RTIO](https://m-labs.hk/artiq/manual/rtio.html)). In TQ this is EXP with an explicit resync delay. The obligation O1 becomes 2 µs ≥ L_in→out + Δ_lead. M-Labs publishes no L_in→out, so the checker returns PROVED-UNDER{L_in→out ≤ 2 µs − Δ_lead}. If the `else` path schedules an output without a delay, the checker returns REFUTED with ω = (count ≤ 20) and θ = any. That is the path a test bench may never exercise if counts above 20 are common.

### Repeat-until-success and bounded loops

For an RUS body of duration T, with success probability p per round and a declared lower bound p_min, a cap N bounds the worst case and a failure tolerance ε fixes the cap. The tail formula is elementary geometric-distribution algebra.

```latex
\Pr[\text{iterations} > n] = (1-p)^n,\qquad
n^{*} = \left\lceil \frac{\ln \varepsilon}{\ln(1-p_{\min})} \right\rceil,\qquad
\mathrm{WCET}_{\text{cap}} = n^{*}\,T + T_{\text{exhaust}}
```

```latex
\mathbb{E}[T_{\text{uncapped}}] = \frac{T}{p}\ \ \big(\text{ert: } X = T + (1-p)X\big),\qquad
\mathbb{E}[T_{\text{cap }N}] = T\cdot\frac{1-(1-p)^{N}}{p}
```

**[Synthesis, illustrative numbers]** With p = 0.5, ε = 1e-6 and T = 2 µs, n* = ⌈13.82 / 0.693⌉ = 20. The verdict is worst case 40 µs + T_exhaust, expected 4 µs, and exhaust probability ≤ 1e-6. A program inside a `within[10 µs]` reaction window then fails the hard check. It passes a probabilistic one with miss probability (1−p)^4 ≈ 6%, which is exactly the kind of statement FT resource estimators need and do not get today.

p depends on the quantum state, so the contract carries p_min as a declared parameter. Deriving it requires simulation, which makes this a hybrid static/dynamic analysis. Each RUS iteration must also leave slack no lower than it found it (O9), or capped loops can underflow late in the run. Bounded `for` is handled by unrolling or by IPET-style loop-bound constraints. Unbounded `while` is out of scope by design.

### Where the user-facing pieces live

The policy and deadline annotations ride on Qiskit `BoxOp` `Annotation` objects in a dedicated namespace. They serialise to OpenQASM 3 `box` statements through `annotation_handlers` and to QPY v15, so they survive the round trip without changing the language ([Qiskit 2.1 notes](https://quantum.cloud.ibm.com/docs/api/qiskit/release-notes/2.1)). A transpiler pass runs the checker and emits verdicts. A second pass performs EQ elaboration, so `ContextAwareDynamicalDecoupling` sees fixed windows. The contract is a separate file, ideally a proposed extension of Qiskit `Target`/QDMI, but that is a later standardisation step.

---

## Research plan

### Research questions

| RQ | Question |
|---|---|
| RQ1 Semantics | Can a small timed core of OpenQASM 3 with MCM, branching, bounded/capped loops and blocking calls be given a semantics in which DMO, Δ-DMO and safe-only are precisely characterised by policy? |
| RQ2 Reduction | Are DMO and EXP-safety exactly equivalent to (hybrid SC/DC) controllability of the encoded CSTNU, and does windowed composition keep checking tractable for realistic programs? |
| RQ3 Contracts | What minimal, provenance-typed contract vocabulary is sufficient to instantiate ARTIQ, Q1ASM, IBM and QUA from public documentation, and which fields are missing from vendors? |
| RQ4 Utility | Does the checker find real timing defects (portability breaks, silent-drop risks, rare-branch deadline misses) that testing misses, at acceptable precision and cost? |
| RQ5 Physics link (optional) | Can delay-sweep experiments on cloud hardware bound otherwise unpublished latencies, and how does idle-window fidelity depend on window length and DD? |

### Falsifiable hypotheses

Thresholds marked ⟨·⟩ must be fixed in a pre-registration before evaluation runs.

| H | Statement | Falsified if |
|---|---|---|
| H1 Soundness | Across differential testing (≥ ⟨N⟩ randomised and extreme (ω, θ) runs per program), the reference executor reports no violation on any program the checker marks PROVED under the same contract | any executor violation on a PROVED program |
| H2 Precision | False-alarm rate (REFUTED or UNKNOWN on programs with no reachable violation, by exhaustive enumeration on small programs) ≤ ⟨x⟩% | rate > ⟨x⟩% |
| H3 Scalability | Windowed checking certifies ≥ ⟨y⟩% of benchmark programs within ⟨s⟩ s for up to ⟨k⟩ timing-relevant bits per window | coverage or time thresholds missed |
| H4 Portability | The same benchmark source receives different verdicts under ≥ 2 of the 4 backend contracts in ≥ ⟨z⟩% of dynamic programs | fewer than ⟨z⟩% differ (portability argument weakens) |
| H5 Policy cost | EQ elaboration adds ≤ ⟨w⟩% total idle relative to SYNC on QEC/RUS benchmarks under IBM-like latencies | idle overhead > ⟨w⟩% |
| H6 Hardware (optional) | Delay-sweep inference of the IBM feedforward window agrees with the about-600 ns figure within ⟨δ⟩ ns, with spread ≤ ⟨σ⟩ ns | disagreement or larger spread (a publishable finding either way) |

### Evaluation

**Benchmarks.** These include teleportation and gate teleportation, active reset, long-range CNOT and GHZ via measurement, RUS gate synthesis, repetition-code and small surface-code syndrome rounds with conditional corrections, magic-state injection with conditional S correction under `within[D]`, and lattice-surgery merge/split with patch-sync slack modelled on Maurya and Tannu. Add the Dynamarq suite where available ([arXiv:2604.03360](https://arxiv.org/abs/2604.03360)), and ARTIQ manual kernels translated to TQ EXP form.

**Reference executor.** This is a discrete-event interpreter with three back-end personalities, built only from documented behaviour:

| Personality | Behaviours modelled |
|---|---|
| ARTIQ-like | cursor and slack; underflow raised; sequence/collision dropped and logged; 8 lanes; input leaves negative slack |
| Q1-like | Q1 cycle costs; RT-queue underflow halt; `set_cond` with else-wait; 32-entry feedback queue |
| IBM-like | `if_test` only; about 600 ns feedforward; block-restart (to be verified) |

Latencies are sampled within contract intervals and also driven adversarially to the extremes.

**Differential testing.** This compares checker verdicts with executor outcomes (H1, H2). It also cross-checks the custom STNU/CSTNU solver against Posenato's CSTNU Tool on exported networks, which guards against solver bugs.

**Metrics.** Verdict distribution, false alarms, check time against program size and k, idle time per policy, deadline margin, and the number of verdicts that depend on non-certified provenance. That last number is a headline result: it quantifies how much of today's timing correctness rests on unpublished numbers.

**Optional IBM experiments.** IBM exposes only `if_test` and no timestamps, so experiments must infer timing from physics. Sweep an inserted `delay` on a spectator prepared in superposition across a feedforward window, with DD on and off. Fit the phase and contrast decay to estimate effective window length and its variation, and measure fidelity against window length, the curve the literature lacks. **[Synthesis]** This is a proposed method, untested.

### Milestones (about 18 months; compressible to 12 or stretchable to 24)

| Months | Milestone | Output |
|---|---|---|
| 0–2 | Close literature gaps: read QaiJi IR full text, TqCCS chapters, CoqQ/QWIRE/Silq/Qafny one-liners, ICAPS for STNU-quantum, IBM block restart, LabOne Q match padding; pre-register H1–H6 thresholds | related-work draft; go/no-go on C3 |
| 2–5 | TQ syntax, big-step semantics, DMO/Δ-DMO definitions, policy typing rules; paper proofs of soundness for EQ | workshop paper (e.g., PLanQC) |
| 4–8 | Contract vocabulary v0.1; instantiate ARTIQ, Q1, IBM, QUA from docs; provenance lattice | contract spec and 4 instances |
| 6–11 | Checker v1: front end, elaboration, obligations, STN fast path, per-scenario enumeration, Z3 tier; counterexamples; Qiskit pass | open-source tool |
| 9–13 | CSTNU encoding and DC tier (own RUL⁻-style or CSTNU Tool bridge); equivalence proofs for the reduction; windowed composition | core technical result |
| 10–14 | Reference executor (3 personalities), benchmarks, differential testing | H1–H5 results |
| 12–16 | RUS/capped loops with expected-time and tail verdicts; FT case studies (reaction deadline, patch sync) | main paper |
| 14–18 (optional) | IBM delay-sweep and window-fidelity experiments | H6; empirical curve |
| any (optional) | Mechanise core metatheory (Agda, building on GRAMPUS artifact) | stretch goal only |

### Threats to validity

- **External validity.** The executor is not hardware. Its personalities encode documented behaviour and nothing more, and undocumented vendor behaviour (QUA gap sizes, IBM block handling) is a parameter. Mitigation: report sensitivity, and validate the IBM personality against cloud experiments.
- **Construct validity.** Verdicts are only as good as contract numbers, and those are mostly measured-max or vendor claims. Mitigation: provenance typing makes this explicit rather than hiding it.
- **Benchmark bias.** Hand-picked programs may favour EQ. Mitigation: include ARTIQ-native EXP kernels and Dynamarq programs not written by the author.
- **Solver correctness.** A bug in the DC solver yields false proofs. Mitigation: cross-check with an independent tool and with exhaustive enumeration on small programs.
- **Cloud observability.** IBM's `if_test`-only support and lack of timestamps limit H6 to indirect inference.
- **Relevance drift.** Vendors increasingly hide timing (IBM pulse removal), and ion and atom platforms show small idle costs. The strongest results are therefore the FT and portability ones, not fidelity.

### Expected contributions and venues

| Contribution | Venue fit |
|---|---|
| TQ semantics, DMO/Δ-DMO, policies as typing rules | PLanQC (POPL-co-located; GRAMPUS venue), QPL, TYPES |
| CSTNU reduction plus windowed composition and complexity for the TQ fragment | TIME, ICAPS (planning), CAV/TACAS |
| Provenance-typed contract vocabulary and instances | IEEE QCE, ACM TQC; vendor/standards outreach (OpenQASM TSC, QDMI) |
| Static checker plus reference executor plus differential evaluation | CAV/TACAS tool track, OOPSLA, or ASPLOS for the systems angle |
| Real-time framing (LET/reactor mapping, PRET-style primitives) | EMSOFT, RTSS, RTAS |
| IBM window-fidelity curve | IEEE QCE, Quantum (if experimental quality suffices) |

---

## Conclusion

The research gap is precise. Industry has three working answers to "what does an `if` do to time", and none of them is written down in a form a compiler can check or a second vendor can honour. The four components fill that gap, but only together. The semantics alone is a calculus that reviewers will compare to GRAMPUS and TqCCS. The checker alone is a tool UPPAAL could imitate. The contract alone is a wish list to vendors. The combination makes timing correctness of dynamic programs a portable, checkable property, and the CSTNU reduction makes it a reuse of mature theory rather than a reinvention.

The reframing carries more weight than it first appears. Arguing from idle fidelity invites refutation by today's runtime enforcement and by ions. Arguing from portability, fault-tolerant reaction deadlines, untestable rare branches and silent drops matches where the field is heading: towards QEC rounds with conditional corrections, lattice-surgery synchronisation and classical calls into GPUs whose latency is only ever reported as a sample maximum. The provenance-typed verdict may be the most consequential artefact. A checker that says "proved, assuming the vendor's undocumented 600 ns holds" tells the field exactly which number has to be published before fault-tolerant timing can be guaranteed.

---

## References

**Language and IR specifications, tooling**
- OpenQASM 3, Circuit timing (delays, stretch, box) — https://openqasm.com/language/delays.html
- OpenQASM 3, Pulse-level descriptions / defcal branch rule — https://openqasm.com/language/pulses.html
- Cross et al., "OpenQASM 3: A broader and deeper quantum assembly language" — https://arxiv.org/abs/2104.14722
- Quil specification (draft), incl. Quil-T, WAIT, JUMP-WHEN — https://quil-lang.github.io/
- Kim & Edwards, QASM-TS 2.0 — https://arxiv.org/html/2412.12578v2
- Qiskit 2.1 release notes (BoxOp annotations, Duration/Stretch, qasm3 annotation handlers) — https://quantum.cloud.ibm.com/docs/api/qiskit/release-notes/2.1
- Qiskit 2.0 release notes (removal of qiskit.pulse) — https://eu-de.quantum.cloud.ibm.com/docs/en/api/qiskit/release-notes/2.0
- Qiskit ConstrainedReschedule API — https://quantum.cloud.ibm.com/docs/api/qiskit/qiskit.transpiler.passes.ConstrainedReschedule
- qiskit-ibm-runtime scheduling passes — https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/transpiler-passes-scheduling
- q1lens (PyPI) — https://pypi.org/project/q1lens/
- Ye, QaiJi IR — https://arxiv.org/abs/2609.29305

**Control hardware and runtimes**
- ARTIQ manual, Real-time I/O concepts — https://m-labs.hk/artiq/manual/rtio.html
- ARTIQ manual, Getting started with the core device — https://m-labs.hk/artiq/manual/getting_started_core.html
- Qblox Q1ASM user guide — https://docs.qblox.com/en/main/products/qblox_instruments/q1/index.html
- Qblox LINQ-based feedback (v2026.04) — https://docs.qblox.com/en/v2026.04.0/products/architecture/sequencers/linq_based_feedback.html
- Quantum Machines, Timing in QUA — https://docs.quantum-machines.co/latest/docs/Guides/timing_in_qua/
- Zurich Instruments LabOne Q timing rules — https://docs.zhinst.com/labone_q_user_manual/concepts/sections_and_pulses/timing_rules
- Zurich Instruments QHub — https://www.zhinst.com/products/qhub-quantum-system-hub
- IBM Quantum docs, Execute dynamic circuits — https://quantum.cloud.ibm.com/docs/en/guides/execute-dynamic-circuits
- IBM Quantum docs, Dynamic circuits considerations / job limits — https://quantum.cloud.ibm.com/docs/en/guides/dynamic-circuits-considerations
- IBM Quantum docs, QPU information — https://quantum.cloud.ibm.com/docs/en/guides/qpu-information
- IBM blog, Utility-scale dynamic circuits — https://www.ibm.com/quantum/blog/utility-scale-dynamic-circuits
- Fu et al., eQASM — https://ar5iv.labs.arxiv.org/html/1808.02449
- Xu et al., QubiC 2.0 — https://arxiv.org/html/2309.10333v1
- Xu et al., Multi-FPGA synchronization for quantum control — https://arxiv.org/html/2506.09856v1
- Stefanazzi et al., QICK — https://arxiv.org/pdf/2110.00557
- QICK asm_v2.py source — https://github.com/openquantumhardware/qick/blob/main/qick_lib/qick/asm_v2.py
- Luo, Song, Su, TIDE — https://arxiv.org/html/2608.15173
- Li et al., QCORE — https://arxiv.org/html/2608.06875
- She et al., QuCtrl-BELL — https://arxiv.org/html/2605.22433
- Caldwell et al., NVQLink — https://arxiv.org/html/2510.25213v2
- Alavi et al. (Riverlane), Design Verification of the Quantum Control Stack — https://arxiv.org/html/2310.05229v1

**Physics, benchmarking, fault tolerance**
- Shirgure et al., Characterizing and Benchmarking Dynamic Quantum Circuits (Dynamarq) — https://arxiv.org/html/2604.03360v2
- Zhong et al., MERA — https://arxiv.org/abs/2511.10921
- Google Quantum AI, Quantum error correction below the surface code threshold — https://arxiv.org/abs/2408.13687
- Gidney & Ekerå, How to factor 2048 bit RSA integers in 8 hours — https://arxiv.org/abs/1905.09749
- Maurya & Tannu, Synchronization for lattice surgery — https://arxiv.org/abs/2506.10258
- Skoric et al., Parallel window decoding / backlog — https://arxiv.org/pdf/2209.08552
- Bluvstein et al., Logical quantum processor based on reconfigurable atom arrays — https://www.nature.com/articles/s41586-023-06927-3
- Cavity-based mid-circuit measurement for neutral atoms — https://arxiv.org/abs/2606.24869
- Moses et al., A Race Track Trapped-Ion Quantum Processor — https://arxiv.org/pdf/2305.03828v2

**Quantum semantics, verification, prior art**
- Adams, Bernardy, Perticone, Pope, GRAMPUS — https://arxiv.org/pdf/2510.03130 ; https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.TYPES.2025.5
- Fernandes, Integration of time in a quantum process algebra (TqCCS), U. Minho 2019 — https://repositorium.sdum.uminho.pt/bitstream/1822/80754/1/Vitor%20Emanuel%20Goncalves%20Fernandes.pdf
- Christensen et al., Analysis and Verification of Quantum Communication Protocols in UPPAAL (CAV 2026) — https://vbn.aau.dk/da/publications/analysis-and-verification-of-quantum-communication-protocols-in-u/
- Søndergaard, Christensen, Popovski, Temporal framework for measurement scheduling in quantum networks — https://arxiv.org/html/2602.12459v1
- Quantum Orchestras — https://arxiv.org/abs/2607.09605
- Quantum Weakest Preconditions Revisited (expected runtime) — https://arxiv.org/abs/2607.12532
- Runtime Analysis of Quantum Programs — https://arxiv.org/abs/1911.11247
- Fulginiti et al., Compile-Time Simplification of Classically Controlled Operations — https://arxiv.org/pdf/2605.28439
- Fulginiti & Chen, Branch-Aware Quantum Constant Propagation — https://arxiv.org/pdf/2606.02018

**Real-time systems and formal foundations**
- Lohstroh et al., Deterministic Coordination across Multiple Timelines (TECS 2024) — https://par.nsf.gov/servlets/purl/10554371
- Henzinger, Horowitz, Kirsch, Giotto — https://api.crossref.org/works/10.1109/JPROC.2002.805825
- Lickly et al., Predictable Programming on a Precision Timed Architecture (TR) — https://www.cs.columbia.edu/~sedwards/papers/lickly2008predictable-tr.pdf
- FlexPRET on Lingua Franca (NG-RES 2025; cites FlexPRET RTAS 2014, DOI 10.1109/RTAS.2014.6925994) — https://drops.dagstuhl.de/storage/01oasics/oasics-vol128-ng-res2025/OASIcs.NG-RES.2025.1/OASIcs.NG-RES.2025.1.pdf
- Wilhelm et al., The worst-case execution-time problem — https://api.crossref.org/works/10.1145/1347375.1347389
- Li & Malik, Implicit path enumeration (IPET) — https://api.crossref.org/works/10.1145/217474.217570
- Dechter, Meiri, Pearl, Temporal constraint networks — https://api.crossref.org/works/10.1016/0004-3702(91)90006-6
- Sumic & Vidal, Weak controllability of STNUs (TIME 2024 slides) — https://www.lirmm.fr/time2024/files/WeakControllabilityOfSTNUsTIME2024.pdf
- Hunsberger, survey of DC-checking algorithms (PDF) — https://www.cs.vassar.edu/~hunsberg/__papers__/springer-2015-acta.pdf
- Morris, Dynamic controllability and dispatchability relationships (CPAIOR 2014) — https://www.doi.org/10.1007/978-3-319-07046-9_33
- Morris, A structural characterization of temporal dynamic controllability (CP 2006) — https://doi.org/10.1007/11889205_28
- Cairo, Hunsberger, Rizzi, Faster DC checking for STNUs (TIME 2018) — https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.TIME.2018.8
- Tsamardinos, Vidal, Pollack, CTP — https://deepblue.lib.umich.edu/items/f5521ccc-29ec-4bf9-ae3a-205216b63b82
- Cairo & Rizzi, DC of CSTNs is PSPACE-complete — https://arxiv.org/abs/1608.08545
- Comin & Rizzi, DC of CSTNs via mean-payoff games — https://arxiv.org/abs/1505.00828
- Hunsberger & Posenato, Sound-and-complete DC checking for CSTNUs (TIME 2018) — https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.TIME.2018.14
- Posenato, CSTNU Tool — https://profs.scienze.univr.it/~posenato/software/cstnu/
- Alur & Dill, A theory of timed automata — https://doi.org/10.1016/0304-3975(94)90010-8
- Kaminski, Katoen, Matheja, Olmedo, Expected runtimes (J. ACM 2018) — https://api.crossref.org/works/10.1145/3208102
