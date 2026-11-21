# Tutorial 00 sources: real-time models of the four stacks

Access date for every URL: 2026-11-22. Every statement below was read on the cited page. Vendor
figures are vendor claims, not certified bounds. No contract was changed; numbers the contracts
leave absent stay absent.

## IBM dynamic circuits / feed-forward

Source: https://www.ibm.com/quantum/blog/utility-scale-dynamic-circuits (IBM Quantum blog, dated 19 Nov 2025; accessed 2026-11-22)

- Dynamic circuits use mid-circuit measurements and classical compute and conditional logic to decide which quantum operations run next; the page calls this classical feedforward.
- The page states that "Feedforward latency is also down to around ~600ns, comparable with industry standards." It does not call this a bound or give a distribution.
- The page says classical operations such as mid-circuit measurement and feedforward are relatively slow compared to gate operations, and that Qiskit has no mechanism for reliably modeling the execution time of the classical operations involved in feedforward; `stretch` is introduced so users express timing intent instead of fixed delays.
- The new `MidCircuitMeasure` instruction captures results "nearly a full microsecond (940 ns) faster" than the previous implementation; the page says it is not available on all backends.
- The page lists limits of the Qiskit Runtime implementation: only the conditional `if` is supported (no `for`, `switch`), nested conditionals are not allowed, and `reset` and measurements inside conditionals are not supported. Independent conditional branches can run in parallel.
- The timing visualisation example states 1 dt = 4 ns for that backend; timing visualisation needs `qiskit-ibm-runtime` v0.43.0 or later and is described as an experimental preview.

## Qblox Q1 sequencer and trigger network

Source: https://docs.qblox.com/en/main/products/architecture/sequencers/trigger_handling.html ("Feedback Trigger Handling", docs 2026.11.0; accessed 2026-11-22). Supplementary: https://docs.qblox.com/en/main/products/qblox_instruments/tutorials/QRM/conditional_playback.html

- The trigger network has four parallel lines mapping to 15 trigger addresses; a trigger sent from any source reaches all sequencers simultaneously 212 ns later, only one trigger can be on the backplane at once, and the network is ready again after 252 ns.
- The network runs on a 28 ns timegrid aligned by `wait_sync`; triggers sent off-grid wait for the next grid point, "a maximum time penalty of 24 ns". The page's figure labels the network contribution "212-239ns".
- Worked example on the page: Feedback time = OP + IP + TOF + Trig = 40 + 109 + 0 + 239 = 388 ns. For most modules with base options OP + IP = 149 ns. Base latencies: Control/Readout Baseband output 40 ns, Readout Baseband input 109 ns, Control/Readout RF output 50 ns, Readout RF input 109 ns. Option RTP adds +24 ns output latency; TTL changes input latency by -35 ns. Propagation delay (cabling) is assumed 0 in these figures.
- `set_cond` makes the RT core evaluate a boolean condition before every real-time instruction: if true the instruction executes, if false the core "simply waits for else_time ns before moving on to the next real-time instruction". `wait_trigger` is documented as not deterministic in execution time.
- The tutorial page says a skipped conditional instruction stalls the RT pipeline for `<else_wait>`, with a minimum of 4 ns.
- A separate Qblox tutorial page (a search excerpt, not read in full) says a trigger sent less than 252 ns after the previous one is missed and a warning flag is raised.

## ARTIQ RTIO and underflow

Sources: https://m-labs.hk/artiq/manual/rtio.html ("ARTIQ Real-Time I/O concepts") and https://m-labs.hk/artiq/manual/core_drivers_reference.html (accessed 2026-11-22)

- The kernel CPU queues events into FIFOs and gateware fires them at predetermined timestamps; "if an event cannot be released at its predetermined time, it is not fired and the kernel will raise an exception".
- The timeline cursor `now_mu` is advanced by `delay()`/`delay_mu()` and set by `at_mu()`; the wall clock is `rtio_counter_mu`. Their difference is slack, and output events are fired when the wall clock reaches their timestamp, not when the CPU processes them.
- Scheduling an output event for a timestamp in the past (non-positive slack) raises `RTIOUnderflow`; the driver reference adds that "The offending event is discarded and the RTIO core keeps operating."
- Reading input (for example `count()`) makes the kernel wait for the wall clock, which can leave negative slack; a later `delay` can restore positive slack. The page notes no guarantees about slack when a new kernel starts, and `core.reset()` re-initialises the cursor.
- A machine unit `mu` "normally corresponds to one nanosecond". The pages I read give no numeric minimum slack for an RTIO write to be accepted.

## Quantum Machines QUA align and real-time control flow

Sources: https://docs.quantum-machines.co/1.1.7/qm-qua-sdk/docs/Guides/timing_in_qua/ ("Timing in QUA", SDK docs 1.1.7) and https://www.quantum-machines.co/technology/make-your-quantum-circuits-truly-dynamic/ (vendor marketing page, page modified 2026-08-12); both accessed 2026-11-22. Also https://docs.quantum-machines.co/1.5.0/docs/Introduction/qua_overview/ (search excerpt)

- `align()` makes later operations on the aligned elements wait for earlier ones on all of them. When durations are known at compile time (deterministic) the compiler replaces the hardware sync with precalculated waits and no gap forms; when a duration is only known at run time (non-deterministic) there are gaps, described as "a few cycles delay" (several clock cycles to pass information between threads).
- There is an implicit align at the start of any `for`, `while`, `if/else/elif` or `switch` that several elements participate in, so loop duration is set by the longer element sequence.
- `strict_timing_()` requires no gaps and raises an error otherwise; the flag `not-strict-timing` turns errors into warnings. The 1.1.7 page says this feature "only exists in the OPX+".
- Example 2 on that page: `wait(100)` delays by 400 ns (100 cycles), so one cycle is 4 ns.
- The overview page says extra latency can occur when aligning elements on separate controllers if the compiler cannot determine each element's wait time, and when a measurement on one controller affects playback on another.
- The vendor page claims a conditional pulse (active reset) "takes 224 ns for one qubit" for analog-to-analog feedback on OPX+, measured from the last point of the measurement input pulse. It also says standard-feedback active reset is "under 250 ns". Both are vendor claims.

## Discrepancies

Compared with the provenance data in `src/qtiming/contract/instances/*.toml` (the fields are named `prov` and `source`; there is no field literally called `provenance`).

IBM (`ibm_heron.toml`)
1. `ff.default` has `hi_ns = 600` and `lo_ns = 0`. The blog says "around ~600ns", an approximate headline, not an upper bound. The `source` string does say "vendor claim, not a certified bound", so the text is honest, but the numeric `hi_ns` reads as a bound. Not changed.
2. `join_behavior = "pad_to_longest_block"` cites "old fast-path stack docs". The blog says the new implementation was built from scratch with parallel conditional execution, so the old behaviour may not apply. The contract already flags it as to-be-calibrated. Nothing on the blog confirms or contradicts the join rule itself.
3. `late_policy = "compile_error"`, `max_cond_bits = 32`, `instr_per_qubit` and `broadcast_budget` are not stated on the blog page; I could not verify them there. `allow_nested`, `allow_measure_in_branch`, `allow_loops` and `while_supported` all being false agree with the blog.

Qblox (`q1.toml`)
4. `path.opip.base = 149` has source text "output 40 ns (baseband) or 50 ns (RF) + input 109 ns". The page confirms the 40/50/109 values, but 149 only equals the baseband sum; RF readout would be 50 + 109 = 159. The page says 149 holds "for most modules with base options". The key's single value hides the RF case.
5. The `[verify page path]` and `[verify the decomposition]` notes can be closed: the page is `.../products/architecture/sequencers/trigger_handling.html` and the 388 = 40 + 109 + 0 + 239 decomposition is stated there (the contract comment writes it as 149 + 239, which is arithmetically the same).
6. The page says off-grid triggers get "a maximum time penalty of 24 ns" on a 28 ns grid, yet gives 212-239 ns (a 27 ns spread). The contract copies 212 and 239 correctly; the page is slightly self-inconsistent.
7. `late_policy = "halt"` (`SEQUENCE_PROCESSOR_RT_EXEC_COMMAND_UNDERFLOW`), `rt_queue_depth = 32`, the whole `[issue_cost]` table (4/12/4/16/24 ns) and `commit_lead` were not on the pages I read; unverified here. `else_time_dt = 1` (4 ns) agrees with the 4 ns minimum else_wait in the tutorial page.
8. `trigger.network_busy` says a second trigger "is lost or delayed"; the Qblox excerpt says it is missed and a warning flag is raised (lost, not delayed).
9. Page says 15 addresses; `max_cond_bits = 15` agrees (its `[verify]` tag can be dropped).

ARTIQ (`artiq.toml`)
10. `late_policy = "mixed"` lists underflow as "raise". Docs agree an exception is raised, and the driver reference adds that the offending event is also discarded. The contract does not record the discard.
11. `in2cpu` source says "ARTIQ manual (no numeric bound)". I did not see any statement about input-to-CPU latency on the pages read; unverified. `commit_lead` absent matches: no numeric minimum slack was seen.
12. `lanes = 8`, `coarse_mu = 8` and `sed_spread_enable` were not on the pages read; unverified.

QM (`qua.toml`)
13. The `align.*` entries are marked `placeholder = true` and "a few cycles" matches the docs. The ordering "same FEM < cross-FEM < cross-chassis" cited in `source` is not on the pages I read (the 1.1.7 SDK docs only say cross-controller alignment can add latency). Unverified; placeholders are already labelled.
14. `late_policy = "compile_error"` with `strict_timing = true` agrees with `strict_timing_()` raising an error. But the 1.1.7 page says the feature "only exists in the OPX+", whereas the contract's FEM/chassis tiers imply OPX1000. The contract does not scope strict timing to a platform. Possibly an outdated docs version; not resolved.
15. `active_reset` has `hi_ns = 224`, source "QM claim: 224 ns active reset (vendor)". The marketing page confirms 224 ns but for one qubit, analog-to-analog, measured from the last point of the measurement input pulse, on OPX+; it also gives "under 250 ns" for standard feedback. The contract's `hi_ns` presents a marketing figure as an upper bound and omits those conditions.
16. The note about non-suppressible implicit aligns for broadcast and measure results read by another core is not on the pages read; unverified. Implicit aligns at flow-control starts agree.

## Not done / limits

- The Exa search tool hit its free rate limit on the IBM query; IBM and the QM 224 ns evidence came from Firecrawl instead.
- I did not read IBM's `classical-feedforward-and-control-flow` documentation page in full (only a search excerpt), so IBM claims rest on the blog.
- A Qblox URL I guessed first (`q1_sequence_processor.html`) returned 404; the URLs above are the ones actually read.
