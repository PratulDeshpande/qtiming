# Policies and annotations

**Question:** a branch on a measurement result takes different times on its two arms. How do I tell qtiming what I expect, and what does it do about it?

Three policies (`eq`, `sync`, `exp`) and three annotations that matter here (`within`, `hard`, `cap`). Reference: [Policies and annotations](../policies.md), [Command reference](../cli.md).

```python
TP = _show.FAMILIES / "teleportation"
MS = _show.FAMILIES / "magic_state"
QUA = ["--contract", "qua", "--assume", "durations.h=32", "--assume", "durations.cx=64",
       "--assume", "durations.x=32", "--assume", "durations.measure=1000"]
```

## The program, with policy `eq`
`@timing.policy eq` says both arms of the branch must take the same time. `@timing.within 3000ns c[1]` is a deadline: the correction must start within 3000 ns of the result.

```python
_show.source("teleportation/tp_basic.qasm")
```

    OPENQASM 3.0;
    // Teleportation with one classical correction (plan Appendix A.1).
    // Policy EQ with a 3000 ns deadline from the arrival of the measurement result.
    qubit[3] q;
    bit[2] c;
    
    h q[1];
    cx q[1], q[2];
    cx q[0], q[1];
    h q[0];
    c[0] = measure q[0];
    c[1] = measure q[1];
    
    @timing.policy eq
    @timing.within 3000ns c[1]
    box {
        if (c[1]) {
            x q[2];
        }
    }
    

## Before and after: what `eq` does to the program
`explain --elaborated` prints the program after qtiming rewrote it. Lines marked `synth(from n9)` did not exist in your source: a barrier, a delay equal to the **upper bound of the feedback latency**, and a delay on the `else` arm to match the `x` gate on the `then` arm. On IBM Heron that delay is 150 dt, which is the vendor-claimed 600 ns at 4 ns per dt.

```python
code, out = _show.run("explain", TP / "tp_basic.qasm", "--contract", "ibm_heron", "--elaborated")
assert code == 0
assert "Barrier n15" in out and "Delay n16 qubits=(2,) dur=150" in out and "Delay n13 qubits=(2,) dur=8" in out
```

    Seq n0
      Gate n1 name='h' qubits=(1,) dur=8
      Gate n2 name='cx' qubits=(1, 2) dur=20
      Gate n3 name='cx' qubits=(0, 1) dur=20
      Gate n4 name='h' qubits=(0,) dur=8
      Measure n5 cbit=BitRef(reg='c', idx=0)
      Measure n6 qubit=1 cbit=BitRef(reg='c', idx=1)
      Box n7
        Seq n8
          Seq n17 synth(from n9)
            Barrier n15 qubits=(1, 2) synth(from n9)
            Delay n16 qubits=(2,) dur=150 declared=True synth(from n9)
            If n9 policy=Policy(kind='eq', delta=None, gap=None) synth(from n9)
              then:
                Seq n12 synth(from n9)
                  Seq n10
                    Gate n11 name='x' qubits=(2,) dur=8
              else:
                Seq n14 synth(from n9)
                  Delay n13 qubits=(2,) dur=8 declared=True synth(from n9)
    [exit 0]
    

The synthesised delay comes from the contract, so another backend gives another number. On QUA (with the gate durations supplied by `--assume`, since the contract leaves them absent) the claimed 224 ns active reset becomes 56 dt:

```python
code, out = _show.run("explain", TP / "tp_basic.qasm", *QUA, "--elaborated")
assert code == 0 and "Delay n16 qubits=(2,) dur=56" in out
```

    Seq n0
      Gate n1 name='h' qubits=(1,) dur=8
      Gate n2 name='cx' qubits=(1, 2) dur=16
      Gate n3 name='cx' qubits=(0, 1) dur=16
      Gate n4 name='h' qubits=(0,) dur=8
      Measure n5 cbit=BitRef(reg='c', idx=0)
      Measure n6 qubit=1 cbit=BitRef(reg='c', idx=1)
      Box n7
        Seq n8
          Seq n17 synth(from n9)
            Barrier n15 qubits=(1, 2) synth(from n9)
            Delay n16 qubits=(2,) dur=56 declared=True synth(from n9)
            If n9 policy=Policy(kind='eq', delta=None, gap=None) synth(from n9)
              then:
                Seq n12 synth(from n9)
                  Seq n10
                    Gate n11 name='x' qubits=(2,) dur=8
              else:
                Seq n14 synth(from n9)
                  Delay n13 qubits=(2,) dur=8 declared=True synth(from n9)
    [exit 0]
    

## The verdict for `eq`, and its timeline
The idle time on `q2` is now the same for every outcome and every latency, so O4 is proved. The only assumption is the vendor latency claim, hence PROVED-UNDER.

```python
code, out = _show.run("check", TP / "tp_basic.qasm", "--contract", "ibm_heron")
assert code == 0 and out.startswith("PROVED-UNDER") and "O4: 11" in out and "ff.default" in out
```

    PROVED-UNDER  (contract ibm_heron, policy sync, sha256 9cf4d27a06ae)
      assumptions (weakest class: vendor):
        ff.default: [0 ns, 600 ns]  vendor: IBM blog, 2025-11-19 (feedforward about 600 ns); vendor claim, not a certified bound
      O2b: 1 obligation(s): proved (tier 1, margin 0 ns)
      O3: 2 obligation(s): proved (tier 1, margin 2400 ns)
      O4: 11 obligation(s): proved (tier 0, margin 0 ns); proved (tier 1, margin 0 ns)
      O7: 1 obligation(s): proved (tier 1, margin 0 ns)
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 0]
    

```python
_show.report_svg(TP / "tp_basic.qasm", "ibm_heron")
```

<div class="qt-fig qt-tl"><svg viewBox="0 0 840 104" role="img" aria-label="typical run" width="100%">
<text x="2" y="14" font-size="11">typical run</text>
<text x="2" y="41" font-size="11">q0</text>
<line x1="80" x2="840" y1="44" y2="44" stroke="#bbb" stroke-width="1"/>
<text x="2" y="67" font-size="11">q1</text>
<line x1="80" x2="840" y1="70" y2="70" stroke="#bbb" stroke-width="1"/>
<text x="2" y="93" font-size="11">q2</text>
<line x1="80" x2="840" y1="96" y2="96" stroke="#bbb" stroke-width="1"/>
<g><title>h (node 1) at 32 ns</title><rect x="88.0" y="58" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>cx (node 2) at 112 ns</title><rect x="108.0" y="58" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>cx (node 2) at 112 ns</title><rect x="108.0" y="84" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>cx (node 3) at 192 ns</title><rect x="127.9" y="32" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>cx (node 3) at 192 ns</title><rect x="127.9" y="58" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>h (node 4) at 224 ns</title><rect x="135.9" y="32" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>measure (node 5) at 2404 ns</title><rect x="680.2" y="32" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>measure (node 6) at 2372 ns</title><rect x="672.2" y="58" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>delay (node 16) at 2972 ns</title><rect x="822.0" y="84" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>delay (node 13) at 3004 ns</title><rect x="830.0" y="84" width="6" height="14" fill="#2c6fbb"/></g>
<text x="80" y="102" font-size="10">0</text><text x="780" y="102" font-size="10">3004 ns</text></svg></div>

## The same circuit under `sync`
`sync` pads nothing: each arm runs as soon as the result is there. `tp_sync` is the same teleportation with `@timing.policy sync` and the requirement that idle time on `q2` not vary. It varies, so it is REFUTED, and the text report draws the two executions that differ.

```python
code, out = _show.run("check", TP / "tp_sync.qasm", "--contract", "ibm_heron")
assert code == 1 and out.startswith("REFUTED") and "O4" in out and "timeline (second execution)" in out
```

    REFUTED  (contract ibm_heron, policy sync, sha256 9cf4d27a06ae)
      why: O4 at node 11: idle gap on q2 must not vary with outcomes or latencies
      O4 failed at E:/PROJECTS/Qtiming/benchmarks/families/teleportation/tp_sync.qasm:17 (tier 2)
      assumptions (weakest class: vendor):
        ff.default: [0 ns, 600 ns]  vendor: IBM blog, 2025-11-19 (feedforward about 600 ns); vendor claim, not a certified bound
      O4: 9 obligation(s): proved (tier 0, margin 0 ns); refuted (tier 2)
      timeline (counterexample):
        t(ns)     0                                                2406
        q0        ....ch.....................................................m.
        q1        h.c.c......................................................m.
        q2        ..c.........................................................x
      timeline (second execution):
        t(ns)     0                                                2404
        q0        ....ch......................................................m
        q1        h.c.c......................................................m.
        q2        ..c.........................................................x
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 1]
    

Same program, same verdict on QUA, where `sync` is the native policy (an align is inserted after the branch, see the elaborated output below). The refutation is about the program asking for constant idle time, not about the backend:

```python
code, out = _show.run("check", TP / "tp_sync.qasm", *QUA)
assert code == 1 and out.startswith("REFUTED")
code, out = _show.run("explain", TP / "tp_sync.qasm", *QUA, "--elaborated")
assert "Barrier n13" in out
```

    REFUTED  (contract qm_qua, policy sync, sha256 d44238256a60)
      why: O4 at node 11: idle gap on q2 must not vary with outcomes or latencies
      O4 failed at E:/PROJECTS/Qtiming/benchmarks/families/teleportation/tp_sync.qasm:17 (tier 2)
      O4 failed at E:/PROJECTS/Qtiming/benchmarks/families/teleportation/tp_sync.qasm:17 (tier 2)
      assumptions (weakest class: vendor):
        active_reset: [0 ns, 224 ns]  vendor: QM claim: 224 ns active reset (vendor)
      O4: 10 obligation(s): proved (tier 0, margin 0 ns); refuted (tier 2)
      timeline (counterexample):
        t(ns)     0                                                1194
        elem:q0   ........ch.................................................m.
        elem:q1   .h..c...c.................................................m..
        elem:q2   ....c.......................................................x
      timeline (second execution):
        t(ns)     0                                                1192
        elem:q0   ........ch..................................................m
        elem:q1   .h..c...c.................................................m..
        elem:q2   ....c.......................................................x
      note: contract assumed value: durations.h=32
      note: contract assumed value: durations.cx=64
      note: contract assumed value: durations.x=32
      note: contract assumed value: durations.measure=1000
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 1]
    

    Seq n0
      Gate n1 name='h' qubits=(1,) dur=8
      Gate n2 name='cx' qubits=(1, 2) dur=16
      Gate n3 name='cx' qubits=(0, 1) dur=16
      Gate n4 name='h' qubits=(0,) dur=8
      Measure n5 cbit=BitRef(reg='c', idx=0)
      Measure n6 qubit=1 cbit=BitRef(reg='c', idx=1)
      Box n7
        Seq n8
          Seq n12 synth(from n9)
            If n9 policy=Policy(kind='sync', delta=None, gap=None) synth(from n9)
              then:
                Seq n10
                  Gate n11 name='x' qubits=(2,) dur=8
            Barrier n13 qubits=(2,) synth(from n9)
    [exit 0]
    

## `exp`: you own the timeline
`tp_exp` writes its delays by hand and asks for `exp`. Per the compatibility table, only an exposed-timeline backend (ARTIQ) accepts that. IBM and QUA refuse it up front:

```python
code, out = _show.run("check", TP / "tp_exp.qasm", "--contract", "ibm_heron")
assert code == 1 and "policy-incompatible" in out
```

    REFUTED  (contract ibm_heron, policy sync, sha256 9cf4d27a06ae)
      why: policy-incompatible: policy 'exp' is not accepted on restricted backends: restricted backend has no exposed timeline
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 1]
    

```python
code, out = _show.run("check", TP / "tp_exp.qasm", *QUA)
assert code == 1 and "policy-incompatible" in out
```

    REFUTED  (contract qm_qua, policy sync, sha256 d44238256a60)
      why: policy-incompatible: policy 'exp' is not accepted on resync backends: implicit aligns remove the exposed cursor
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 1]
    

On ARTIQ the policy is accepted, but the verdict is **UNKNOWN**: the shipped contract has no `timeline.commit_lead` and no gate durations, and qtiming does not guess them. That is the honest state of the contract, not a pass.

```python
code, out = _show.run("check", TP / "tp_exp.qasm", "--contract", "artiq",
                      "--assume", "durations.h=32", "--assume", "durations.cx=64",
                      "--assume", "durations.x=32", "--assume", "durations.measure=1000")
assert code == 3 and out.startswith("UNKNOWN") and "timeline.commit_lead" in out
```

    UNKNOWN  (contract artiq_rtio, policy exp, sha256 0c124dd6fbf4)
      why: O1 at node 2: missing contract field: timeline.commit_lead
      why: O1 at node 3: missing contract field: timeline.commit_lead
      why: O1 at node 4: missing contract field: timeline.commit_lead
      why: O1 at node 5: missing contract field: timeline.commit_lead
      why: O1 at node 13: missing contract field: timeline.commit_lead
      why: O5 at node 2: Tier 2 does not encode Events (O5) yet
      assumptions (weakest class: vendor):
        in2cpu: [0 ns, unbounded]  vendor: ARTIQ manual (no numeric bound)
      O1: 5 obligation(s): unknown (tier -)
      O5: 1 obligation(s): unknown (tier -)
      note: contract assumed value: durations.h=32
      note: contract assumed value: durations.cx=64
      note: contract assumed value: durations.x=32
      note: contract assumed value: durations.measure=1000
      note: no executor trace: ARTIQ commit_lead is unspecified; the executor will not guess it
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 3]
    

## `within` and `hard`: deadlines
The magic-state injection family puts a conditional fix-up inside a `within` box. `msi_hard_3000` has no policy annotation, so `--policy` decides. Under the default (`sync`) it fails O4 for the reason above; under `eq` the 3000 ns deadline is met with a margin of 2400 ns (3000 ns minus the 600 ns latency bound).

```python
_show.source("magic_state/msi_hard_3000.qasm")
```

    OPENQASM 3.0;
    // msi_hard_3000: injection with a conditional S-like fix-up inside a hard 3000 ns reaction deadline
    qubit[2] q;
    bit[1] c;
    
    h q[0];
    cx q[0], q[1];
    c[0] = measure q[1];
    @timing.within 3000ns c[0]
    @timing.hard
    box {
        if (c[0]) {
            sx q[0];
        }
    }
    

```python
code, out = _show.run("check", MS / "msi_hard_3000.qasm", "--contract", "ibm_heron")
assert code == 1 and "O4" in out
code, out = _show.run("check", MS / "msi_hard_3000.qasm", "--contract", "ibm_heron", "--policy", "eq")
assert code == 0 and out.startswith("PROVED-UNDER") and "margin 2400 ns" in out
```

    REFUTED  (contract ibm_heron, policy sync, sha256 9cf4d27a06ae)
      why: O4 at node 8: idle gap on q0 must not vary with outcomes or latencies
      O4 failed at E:/PROJECTS/Qtiming/benchmarks/families/magic_state/msi_hard_3000.qasm:13 (tier 2)
      assumptions (weakest class: vendor):
        ff.default: [0 ns, 600 ns]  vendor: IBM blog, 2025-11-19 (feedforward about 600 ns); vendor claim, not a certified bound
      O3: 1 obligation(s): proved (tier 1, margin 3000 ns)
      O4: 5 obligation(s): proved (tier 0, margin 0 ns); refuted (tier 2)
      timeline (counterexample):
        t(ns)     0                                                2326
        q0        h.c.........................................................s
        q1        ..c........................................................m.
      timeline (second execution):
        t(ns)     0                                                2324
        q0        h.c.........................................................s
        q1        ..c........................................................m.
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 1]
    

    PROVED-UNDER  (contract ibm_heron, policy eq, sha256 9cf4d27a06ae)
      assumptions (weakest class: vendor):
        ff.default: [0 ns, 600 ns]  vendor: IBM blog, 2025-11-19 (feedforward about 600 ns); vendor claim, not a certified bound
      O2b: 1 obligation(s): proved (tier 1, margin 0 ns)
      O3: 2 obligation(s): proved (tier 1, margin 2400 ns)
      O4: 7 obligation(s): proved (tier 0, margin 0 ns); proved (tier 1, margin 0 ns)
      O7: 1 obligation(s): proved (tier 1, margin 0 ns)
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 0]
    

`@timing.hard` marks the deadline as one that only `cyc` or `cert` evidence should discharge. In this build `msi_hard_3000` still comes out PROVED-UNDER on a vendor bound, exactly like the soft version `msi_soft_within`, so the flag does not change the verdict here (it is recorded for the evidence phase, which is not built yet).

```python
code, soft = _show.run("check", MS / "msi_soft_within.qasm", "--contract", "ibm_heron", "--policy", "eq", show=False)
assert code == 0 and soft.startswith("PROVED-UNDER")
```

A deadline tighter than the latency is refuted with a counterexample. `msi_hard_tight` under `eq`:

```python
code, out = _show.run("check", MS / "msi_hard_tight.qasm", "--contract", "ibm_heron", "--policy", "eq")
assert code == 1 and "O3 failed" in out
```

    REFUTED  (contract ibm_heron, policy eq, sha256 9cf4d27a06ae)
      why: O3 at node 4: first operation must start within the deadline after the result
      O3 failed at E:/PROJECTS/Qtiming/benchmarks/families/magic_state/msi_hard_tight.qasm:9 (tier 2)
      O3 failed at E:/PROJECTS/Qtiming/benchmarks/families/magic_state/msi_hard_tight.qasm:9 (tier 2)
      assumptions (weakest class: vendor):
        ff.default: [0 ns, 600 ns]  vendor: IBM blog, 2025-11-19 (feedforward about 600 ns); vendor claim, not a certified bound
      O2b: 1 obligation(s): proved (tier 1, margin 0 ns)
      O3: 2 obligation(s): refuted (tier 2)
      O4: 7 obligation(s): proved (tier 0, margin 0 ns); proved (tier 1, margin 0 ns)
      O7: 1 obligation(s): proved (tier 1, margin 0 ns)
      timeline (counterexample):
        t(ns)     0                                                2924
        q0        h.c........................................................ds
        q1        ..c............................................m.............
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 1]
    

## `cap`
`@timing.cap N` bounds a `while` loop, and a `while` without it fails with `E-FE-UNBOUNDED-WHILE`. The unrolled loop and the QUA run are in [Policies and annotations](../policies.md#annotations). Note that RUS loops are not wired into `check` yet, so this tutorial does not demo one.

## What just happened
- `eq` rewrote the program: barrier, a latency-bound delay, and a padding delay on the short arm (`explain --elaborated`, `synth(from ...)` lines). The delay size comes from the contract (150 dt on IBM, 56 dt on QUA).
- `sync` adds nothing, so a requirement of constant idle time is REFUTED with two replayable executions.
- `exp` is accepted only by ARTIQ, and there the verdict is UNKNOWN because the contract omits numbers.
- `within` generates a deadline obligation; the margin is the deadline minus the vendor latency bound. `hard` does not yet change the verdict.

Next: [Backends and contracts](04-obligations.md).
