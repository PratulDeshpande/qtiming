# Obligations

An obligation is a small claim about the timed event graph of one program, checked against the fixed dispatch of one hardware personality. A report prints one line per obligation kind, for example `O4: 11 obligation(s): proved (tier 0, margin 0 ns); proved (tier 1, margin 0 ns)`. A failure names the kind, the program node (`O4 at node 11`) and the source line. `qtiming explain --obligations` lists every obligation with its check and message; `--elaborated` shows the node numbers in the elaborated program.

| Code | Protects | Generated for |
| --- | --- | --- |
| O1 | Real-time queue never underflows | ARTIQ, Q1 |
| O2a | Condition result is valid when the real-time core reads it | Q1 |
| O2b | An equalised branch never stalls on the feedback latency | IBM, QUA |
| O3 | Reaction deadlines (`timing.within`) | all four |
| O4 | No idle gap whose length varies | IBM, QUA |
| O5 | Capacity | ARTIQ (SED lanes), Q1 (trigger network) |
| O7 | Equalised blocks end at the same time for every outcome | IBM, Q1 |

Not generated in 0.1.0: **O4a**, **O6** (blocking calls), **O8** (timing grid), **O9** (loop windows), and **O7 for SYNC with a spread bound**. Every report lists these on its last line. A verdict does not cover them.

## O1: no underflow

Every real-time event must be committed at least `commit_lead` before its timestamp. On ARTIQ the check is that the kernel issues each RTIO event early enough. On Q1 the real-time core must never need an instruction the classical core has not issued yet.

A failure means an event is scheduled too close to the time its own preceding code finishes, so the hardware would raise an underflow (ARTIQ) or halt the sequencer (Q1). ARTIQ leaves `commit_lead` absent, so O1 is UNKNOWN until you supply it. The values below are illustrative:

    $ qtiming check benchmarks/families/artiq/artiq_ramsey_fb --contract artiq --assume durations.x=100 --assume durations.measure=1000 --assume durations.h=50 --assume timeline.commit_lead=200 --assume in2cpu=0:300
    REFUTED  (contract artiq_rtio, policy exp, sha256 8cbc342b1f07)
      why: O1 at node 1: RTIO event must be committed at least commit_lead before its timestamp
      O1 failed at benchmarks/families/artiq/artiq_ramsey_fb.qasm:7 (tier 0, short by 200 ns)
      ...
    $ echo $?
    1

Line 7 is the first `h`, at time 0, with nothing before it to give the 200 ns of lead. What to change: put a `delay` before the event, at least as long as the shortfall. `qtiming repair` does this for O1 and re-verifies the result:

    $ qtiming repair benchmarks/families/artiq/artiq_ramsey_fb --contract artiq --assume durations.x=100 --assume durations.measure=1000 --assume durations.h=50 --assume timeline.commit_lead=200 --assume in2cpu=0:300
    repair: unknown: the program is UNKNOWN: O5 at node 1: Tier 2 does not encode Events (O5) yet
    before: REFUTED  after: UNKNOWN
      O1: insert before line 7:  delay[200ns] $0;  (200 dt)
    added idle time: 200 ns; the patched program was re-verified by the full pipeline
    $ echo $?
    3

The O1 failure is gone. The program is now UNKNOWN because of O5 (below). The delay is idle time on the qubit; weigh it against decoherence.

## O2a: result valid when read

On a predicated backend (Q1) the real-time core consults the condition result when it reaches a conditional instruction. The result must already be valid, that is, the measurement finished and the trigger-network latency has elapsed. A failure would mean the branch reads a stale value.

Under the `eq` policy the elaborator inserts a wait equal to the latency upper bound, so O2a held in every Q1 run I made. I did not produce an O2a failure. Q1 accepts only `eq` for predicated branches; see [Policies](policies.md).

## O2b: no stall

For an equalised (`eq`) branch on IBM or QUA, the inserted wait must cover the feedback latency so the branch never waits for the result. A failure means the wait is shorter than the latency upper bound. The elaborator computes the wait from the contract, so O2b held in every run I made and I did not produce a failure. If you replace `ff.default` with a larger bound, the wait grows with it.

## O3: deadline

For `@timing.within D c[i]`, the first operation inside the box must start no later than `D` after the result `c[i]` is valid. Under `eq` the branch starts only after the full latency upper bound, so the deadline must be at least that. A failing example (the bound `ff.default` is 600 ns, the deadline 300 ns):

    $ qtiming check benchmarks/families/active_reset/reset_within_tight --contract ibm_heron --policy eq
    REFUTED  (contract ibm_heron, policy eq, sha256 9cf4d27a06ae)
      why: O3 at node 2: first operation must start within the deadline after the result
      O3 failed at benchmarks/families/active_reset/reset_within_tight.qasm:7 (tier 2)
      ...
    $ echo $?
    1

What to change: raise the deadline, or use a policy that starts the branch earlier. With the deadline edited from `300ns` to `600ns` the program is PROVED-UNDER with `O3 ... margin 0 ns`; at `700ns` the margin is 100 ns. Raising the deadline is only honest if the deadline is a real requirement of the circuit. `@timing.hard` makes the obligation discharge only on a `cyc` or `cert` bound; see [Reading a verdict](verdicts.md).

## O4: no unplanned idle gap

On IBM and QUA, the gap between two consecutive operations on one qubit must not vary with measurement outcomes or latencies by more than `idle.max_gap_variation_ns` (0 in every shipped contract). A gap that varies breaks compile-time dynamical decoupling and phase tracking. This is the most common failure under `sync`:

    $ qtiming check benchmarks/families/teleportation/tp_sync --contract ibm_heron --policy eq
    REFUTED  (contract ibm_heron, policy eq, sha256 9cf4d27a06ae)
      why: O4 at node 11: idle gap on q2 must not vary with outcomes or latencies
      O4 failed at benchmarks/families/teleportation/tp_sync.qasm:17 (tier 2)
      ...

The same circuit under `eq` (`tp_basic`) is PROVED-UNDER: the elaborator pads the wait to the latency upper bound and pads the shorter arm, so the gap is the same for every outcome and every latency. What to change: use `@timing.policy eq`, or write the delay yourself and declare it. On the other policies this obligation has no automatic fix; `qtiming repair` reports `unsupported: no automatic patch for O4`.

## O5: capacity

**ARTIQ.** A concrete list of RTIO events is checked against the SED lane rules: no sequence error, collision or busy drop. The symbolic encoding is not built, so O5 is UNKNOWN (`Tier 2 does not encode Events (O5) yet`) for the ARTIQ programs I ran, even when every other obligation holds.

**Q1.** A second trigger within the network busy window (`trigger.network_busy`, 252 ns in the shipped contract) is lost. The check requires consecutive real-time ends to be at least that far apart. In my Q1 run it held with a margin of 748 ns.

## O7: block join

For an `eq` block, the block must end at the same time for every outcome (IBM: variation 0 between the block end and the barrier; Q1: the next real-time instruction starts at the same time after either arm). It held in every run I made, including with `join_behavior = "restart_at_join"` in a copy of the IBM contract. A failure would mean the two arms have different lengths and the equalisation did not work. On Q1 this shows up earlier as `E-ELAB-Q1-NOT-EQUALISABLE`; see [Error codes](errors.md).

O7 for `sync` with a `delta` spread bound is not generated. The `delta` and `gap` arguments of `sync(...)` are parsed and stored but no obligation uses them.
