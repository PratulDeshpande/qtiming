# Obligation tour

**Question:** a report says `O4: 11 obligation(s): proved`. What *is* an obligation, which hardware stack produces which one, and what does a failure of each look like?

An obligation is one small timing claim about the event graph of one program, checked against one hardware personality. This tour runs one small program per obligation kind. Reference: [Obligations](../obligations.md), [Reading a verdict](../verdicts.md), [Contracts](../contracts.md).

| Code | Protects | Stack |
| --- | --- | --- |
| O1 | real-time queue never underflows | ARTIQ, Q1 |
| O2a | condition result valid when the real-time core reads it | Q1 |
| O2b | an equalised branch never stalls on the feedback latency | IBM, QUA |
| O3 | reaction deadline (`timing.within`) | all four |
| O4 | no idle gap whose length varies | IBM, QUA |
| O5 | capacity | ARTIQ (SED lanes), Q1 (trigger network) |
| O7 | equalised blocks end together for every outcome | IBM, Q1 |

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent))
import _show

HERE = Path.cwd()
TP = _show.FAMILIES / "teleportation/tp_basic.qasm"
RESET = _show.FAMILIES / "active_reset/reset_within_tight.qasm"

# ARTIQ and Q1 publish no gate durations. The numbers below are ILLUSTRATIVE assumptions
# passed with --assume (class `vendor`); they are not vendor values.
ARTIQ = ["durations.x=100", "durations.measure=1000", "durations.h=50", "in2cpu=0:300"]
Q1 = ["durations.x=32", "durations.measure=1000"]

def check(program, contract, *assume, policy=None):
    args = ["check", program, "--contract", contract]
    for a in assume:
        args += ["--assume", a]
    if policy:
        args += ["--policy", policy]
    return _show.run(*args)

def line(out, code):
    return next(l.strip() for l in out.splitlines() if l.strip().startswith(code + ":"))
```

Every report prints one `Ok:` line per obligation kind and ends with a line naming what this build does **not** check. That last line is covered at the end.

## IBM Heron: O2b, O3, O4, O7
Teleportation with one corrected branch, `@timing.policy eq`, deadline 3000 ns.

```python
_show.source(TP)
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
    

```python
code, out = check(TP, "ibm_heron")
assert code == 0 and out.startswith("PROVED-UNDER")
for k in ("O2b", "O3", "O4", "O7"):
    assert "proved" in line(out, k), k
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
    

Four kinds from one program. `O2b` says the inserted wait covers the 600 ns feedback latency (a **vendor** claim, shown under *assumptions*). `O4` has 11 obligations, one per idle gap. `O7` says the equalised branch ends at the same time for every outcome. Margin 0 ns on O2b, O4 and O7 means "equal", which is exactly what they demand.

### O3 failing
`reset_within_tight` demands a reaction within 300 ns, tighter than the 600 ns feedforward claim.

```python
_show.source(RESET)
```

    OPENQASM 3.0;
    // reset_within_tight: reset with a 300 ns deadline: tighter than the vendor 600 ns feedforward claim
    qubit[1] q;
    bit[1] c;
    
    c[0] = measure q[0];
    @timing.within 300ns c[0]
    box {
        if (c[0]) {
            x q[0];
        }
    }
    

```python
code, out = check(RESET, "ibm_heron", policy="eq")
assert code == 1 and out.startswith("REFUTED") and "O3 failed at" in out
assert line(out, "O3").endswith("refuted (tier 2)")
```

    REFUTED  (contract ibm_heron, policy eq, sha256 9cf4d27a06ae)
      why: O3 at node 2: first operation must start within the deadline after the result
      O3 failed at E:/PROJECTS/Qtiming/benchmarks/families/active_reset/reset_within_tight.qasm:7 (tier 2)
      O3 failed at E:/PROJECTS/Qtiming/benchmarks/families/active_reset/reset_within_tight.qasm:7 (tier 2)
      assumptions (weakest class: vendor):
        ff.default: [0 ns, 600 ns]  vendor: IBM blog, 2025-11-19 (feedforward about 600 ns); vendor claim, not a certified bound
      O2b: 1 obligation(s): proved (tier 1, margin 0 ns)
      O3: 2 obligation(s): refuted (tier 2)
      O4: 4 obligation(s): proved (tier 0, margin 0 ns); proved (tier 1, margin 0 ns)
      O7: 1 obligation(s): proved (tier 1, margin 0 ns)
      timeline (counterexample):
        t(ns)     0                                                2812
        q0        ..............................................m............dx
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 1]
    

```python
_show.report_svg(RESET, "ibm_heron")
```

<svg viewBox="0 0 840 52" role="img" aria-label="counterexample" width="100%">
<text x="2" y="14" font-size="11">counterexample</text>
<text x="2" y="41" font-size="11">q0</text>
<line x1="80" x2="840" y1="44" y2="44" stroke="#bbb" stroke-width="1"/>
<g><title>measure (node 1) at 2180 ns</title><rect x="818.5" y="32" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>x (node 6) at 2214 ns</title><rect x="830.0" y="32" width="6" height="14" fill="#2c6fbb"/></g>
<text x="80" y="50" font-size="10">0</text><text x="780" y="50" font-size="10">2214 ns</text></svg>
<svg viewBox="0 0 840 52" role="img" aria-label="second execution" width="100%">
<text x="2" y="14" font-size="11">second execution</text>
<text x="2" y="41" font-size="11">q0</text>
<line x1="80" x2="840" y1="44" y2="44" stroke="#bbb" stroke-width="1"/>
<g><title>measure (node 1) at 2180 ns</title><rect x="819.2" y="32" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>x (node 6) at 2212 ns</title><rect x="830.0" y="32" width="6" height="14" fill="#2c6fbb"/></g>
<text x="80" y="50" font-size="10">0</text><text x="780" y="50" font-size="10">2212 ns</text></svg>

(The picture uses the default policy, so it shows the `sync` counterexample, which fails O4; the text above is the `eq` run. Under `eq` the branch starts only after the full 600 ns, so no 300 ns deadline can hold. The fix is a deadline of at least 600 ns, only if that is a real requirement.)

### O4 failing
`tp_sync` asks for identical idle time on `q2` across outcomes; the two executions differ by 2 ns.

```python
code, out = check(_show.FAMILIES / "teleportation/tp_sync.qasm", "ibm_heron", policy="eq")
assert code == 1 and "O4 failed at" in out and "O4 at node 11" in out
```

    REFUTED  (contract ibm_heron, policy eq, sha256 9cf4d27a06ae)
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
    

## QUA: O2b, O3, O4 and a different latency
The same `reset_within_tight` on QUA, with `x` and `measure` durations assumed. QUA's vendor claim is a 224 ns active reset, so a 300 ns deadline is met with 76 ns to spare. Same program, other contract, other verdict.

```python
code, out = check(RESET, "qua", "durations.x=32", "durations.measure=1000", policy="eq")
assert code == 0 and out.startswith("PROVED-UNDER")
assert "margin 76 ns" in line(out, "O3")
for k in ("O2b", "O4"):
    assert "proved" in line(out, k)
```

    PROVED-UNDER  (contract qm_qua, policy eq, sha256 f08c2d109bac)
      assumptions (weakest class: vendor):
        active_reset: [0 ns, 224 ns]  vendor: QM claim: 224 ns active reset (vendor)
      O2b: 1 obligation(s): proved (tier 1, margin 0 ns)
      O3: 2 obligation(s): proved (tier 1, margin 76 ns)
      O4: 4 obligation(s): proved (tier 0, margin 0 ns); proved (tier 1, margin 0 ns)
      note: contract assumed value: durations.x=32
      note: contract assumed value: durations.measure=1000
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 0]
    

## Q1: O1, O2a, O3, O5, O7
Q1 accepts only `eq`, with arms of equal real-time length; otherwise you get `E-ELAB-Q1-NOT-EQUALISABLE` (exit 2, see [Error codes](../errors.md)), which the shipped `tp_basic` hits on Q1. So this tutorial ships its own small program: two measure-and-correct steps, each branch padded with a `delay`, the second with a 500 ns deadline.

```python
Q1PROG = HERE / "q1_two_triggers.qasm"
_show.source(Q1PROG)
```

    OPENQASM 3.0;
    // q1_two_triggers: written for this tutorial. Two measure-and-correct steps back to back on Q1,
    // the second deadline-annotated, so the trigger network is used twice.
    qubit[2] q;
    bit[2] c;
    
    c[0] = measure q[0];
    @timing.policy eq
    box {
        if (c[0]) {
            x q[0];
        } else {
            delay[32ns] q[0];
        }
    }
    c[1] = measure q[1];
    @timing.policy eq
    @timing.within 500ns c[1]
    box {
        if (c[1]) {
            x q[1];
        } else {
            delay[32ns] q[1];
        }
    }
    

```python
code, out = check(Q1PROG, "q1", *Q1)
assert code == 0 and out.startswith("PROVED-UNDER")
for k in ("O1", "O2a", "O3", "O5", "O7"):
    assert "proved" in line(out, k), k
```

    PROVED-UNDER  (contract qblox_q1, policy eq, sha256 e6b959ace31f)
      assumptions (weakest class: vendor):
        trigger.network: [212 ns, 240 ns]  vendor: docs.qblox.com trigger_handling; documented figure, not cycle-certified [verify page path]
      O1: 8 obligation(s): proved (tier 0, margin 0 ns); proved (tier 0, margin 1224 ns); proved (tier 0, margin 1228 ns); proved (tier 0, margin 1252 ns); proved (tier 0, margin 2248 ns); proved (tier 0, margin 2476 ns); proved (tier 0, margin 2480 ns); proved (tier 0, margin 996 ns)
      O2a: 4 obligation(s): proved (tier 1, margin 0 ns); proved (tier 2)
      O3: 2 obligation(s): proved (tier 2)
      O5: 1 obligation(s): proved (tier 0, margin 1024 ns)
      O7: 1 obligation(s): proved (tier 0, margin 0 ns)
      note: contract assumed value: durations.x=32
      note: contract assumed value: durations.measure=1000
      note: W-CT-ROUND: latency trigger.network [212, 239] ns -> [53, 60] dt (rounded outward)
      note: W-CT-ROUND: latency path.opip.base [149, 149] ns -> [37, 38] dt (rounded outward)
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 0]
    

`O1`: each real-time event is issued early enough (8 events). `O2a`: the trigger-network result (212 to 239 ns, a **vendor** documented figure, not cycle-certified) is valid before the branch reads it. `O5`: the second trigger is not inside the first one's 252 ns network-busy window. `O7`: both arms take the same real-time time.

`explain --obligations` lists the individual claims behind those lines. Here are the O5 and O7 ones:

```python
code, out = _show.run("explain", Q1PROG, "--contract", "q1", *sum((["--assume", a] for a in Q1), []), "--obligations", show=False)
for l in out.splitlines():
    if l.startswith(("O5", "O7")):
        print(l)
assert any(l.startswith("O5") for l in out.splitlines())
```

    O5 n9: Diff(x=15, y=3, op='>=', c=63)  deps=[]  a second trigger inside the network busy window is lost
    O7 n4: Variation(x=14, y=9, bound=0)  deps=[]  an EQ block must take the same RT time for every outcome
    

A passing program has no counterexample timeline in the text report; the HTML report carries the schedule as an SVG:

```python
_show.report_svg(Q1PROG, "q1", *Q1)
```

<svg viewBox="0 0 840 52" role="img" aria-label="typical run" width="100%">
<text x="2" y="14" font-size="11">typical run</text>
<text x="2" y="41" font-size="11">rt</text>
<line x1="80" x2="840" y1="44" y2="44" stroke="#bbb" stroke-width="1"/>
<g><title>acquire (node 1) at 4 ns</title><rect x="81.2" y="32" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>wait (node 18) at 1004 ns</title><rect x="378.3" y="32" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>x (node 6) at 1244 ns</title><rect x="449.7" y="32" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>wait (node 8) at 1248 ns</title><rect x="450.8" y="32" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>acquire (node 9) at 1280 ns</title><rect x="460.3" y="32" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>wait (node 21) at 2280 ns</title><rect x="757.5" y="32" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>x (node 14) at 2520 ns</title><rect x="828.8" y="32" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>wait (node 16) at 2524 ns</title><rect x="830.0" y="32" width="6" height="14" fill="#2c6fbb"/></g>
<text x="80" y="50" font-size="10">0</text><text x="780" y="50" font-size="10">2524 ns</text></svg>

## ARTIQ: O1 (fails) and O5 (unknown)
`artiq_ramsey_fb` is a synthetic Ramsey kernel (written by the qtiming authors, not ARTIQ code) with a feedback correction. The ARTIQ contract publishes no commit lead, so we assume 200 ns (illustrative). The first `h` is at time 0, so nothing gives it any lead.

```python
RAMSEY = _show.FAMILIES / "artiq/artiq_ramsey_fb.qasm"
_show.source(RAMSEY)
```

    OPENQASM 3.0;
    // artiq_ramsey_fb: Ramsey sequence with a feedback correction after a free-evolution delay
    // synthetic ARTIQ-style kernel written by the qtiming authors, NOT external code (not from the ARTIQ project); exposed-timeline (EXP) form
    qubit[1] q;
    bit[1] c;
    
    h q[0];
    delay[2000ns] q[0];
    h q[0];
    c[0] = measure q[0];
    delay[800ns] q[0];
    @timing.policy exp
    box {
        if (c[0]) {
            x q[0];
        }
    }
    

```python
code, out = check(RAMSEY, "artiq", *ARTIQ, "timeline.commit_lead=200")
assert code == 1 and out.startswith("REFUTED")
assert "O1 failed at" in out and "short by 200 ns" in out
assert "refuted (tier 0, margin -200 ns)" in line(out, "O1")
```

    REFUTED  (contract artiq_rtio, policy exp, sha256 d33bb0390f11)
      why: O1 at node 1: RTIO event must be committed at least commit_lead before its timestamp
      O1 failed at E:/PROJECTS/Qtiming/benchmarks/families/artiq/artiq_ramsey_fb.qasm:7 (tier 0, short by 200 ns)
      assumptions (weakest class: vendor):
        in2cpu: [0 ns, 300 ns]  vendor: --assume in2cpu=0:300
      O1: 3 obligation(s): proved (tier 0, margin 1850 ns); proved (tier 1, margin 300 ns); refuted (tier 0, margin -200 ns)
      O5: 1 obligation(s): unknown (tier -)
      note: contract assumed value: durations.x=100
      note: contract assumed value: durations.measure=1000
      note: contract assumed value: durations.h=50
      note: contract assumed value: in2cpu=0:300
      note: contract assumed value: timeline.commit_lead=200
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 1]
    

O1 failed at source line 7 (the first `h`), short by 200 ns: the margin is negative. Compare `artiq_slack_neg`, where the feedback is issued with no slack after the measurement:

```python
code, out = check(_show.FAMILIES / "artiq/artiq_slack_neg.qasm", "artiq", *ARTIQ, "timeline.commit_lead=200")
assert code == 1 and "O1 failed at" in out
```

    REFUTED  (contract artiq_rtio, policy exp, sha256 d33bb0390f11)
      why: O1 at node 6: RTIO event must be committed at least commit_lead before its timestamp
      O1 failed at E:/PROJECTS/Qtiming/benchmarks/families/artiq/artiq_slack_neg.qasm:11 (tier 2)
      assumptions (weakest class: vendor):
        in2cpu: [0 ns, 300 ns]  vendor: --assume in2cpu=0:300
      O1: 1 obligation(s): refuted (tier 2)
      O5: 1 obligation(s): unknown (tier -)
      note: contract assumed value: durations.x=100
      note: contract assumed value: durations.measure=1000
      note: contract assumed value: durations.h=50
      note: contract assumed value: in2cpu=0:300
      note: contract assumed value: timeline.commit_lead=200
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 1]
    

### O5 is not built symbolically
With a commit lead of 0 the O1 failure goes away, and the verdict is still not PROVED:

```python
code, out = check(RAMSEY, "artiq", *ARTIQ, "timeline.commit_lead=0")
assert code == 3 and out.startswith("UNKNOWN")
assert "Tier 2 does not encode Events (O5) yet" in out
assert "unknown" in line(out, "O5")
```

    UNKNOWN  (contract artiq_rtio, policy exp, sha256 9536dcc058de)
      why: O5 at node 1: Tier 2 does not encode Events (O5) yet
      assumptions (weakest class: vendor):
        in2cpu: [0 ns, 300 ns]  vendor: --assume in2cpu=0:300
      O1: 3 obligation(s): proved (tier 0, margin 0 ns); proved (tier 0, margin 2050 ns); proved (tier 1, margin 500 ns)
      O5: 1 obligation(s): unknown (tier -)
      note: contract assumed value: durations.x=100
      note: contract assumed value: durations.measure=1000
      note: contract assumed value: durations.h=50
      note: contract assumed value: in2cpu=0:300
      note: contract assumed value: timeline.commit_lead=0
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 3]
    

**The symbolic encoding of O5 is not built in this version.** O5 on ARTIQ (SED lane capacity) is UNKNOWN for every ARTIQ program I ran, even when all of O1 holds. Do not read an ARTIQ `UNKNOWN` of this kind as "probably fine". On Q1, O5 (trigger-network busy window) *is* checked, as above.

## What is not checked by this build
Every report ends with the same line. A verdict does not cover these:

```python
code, out = check(TP, "ibm_heron")
last = out.strip().splitlines()[-1]
for k in ("O4a", "O6", "O8", "O9", "O7 for SYNC with a spread bound"):
    assert k in last, k
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
    

| Not checked | Meaning |
| --- | --- |
| O4a | off by default |
| O6 | blocking calls |
| O8 | timing grid |
| O9 | loop windows |
| O7 for `sync` with a spread bound | `delta` and `gap` are parsed and stored but no obligation uses them |

## What just happened
- One program per obligation kind, on the stack that generates it: IBM (O2b, O3, O4, O7), QUA (O2b, O3, O4), Q1 (O1, O2a, O3, O5, O7), ARTIQ (O1, O5).
- Failures name the kind, the node and the source line: O3 on IBM, O4 on IBM, O1 on ARTIQ.
- The same program can pass on one contract and fail on another (O3 on QUA vs IBM), because the contracts carry different latencies, each labelled with its provenance.
- O5 on ARTIQ is UNKNOWN: its symbolic encoding is not built. Numbers passed with `--assume` here are illustrative, not vendor values.

Reference: [Obligations](../obligations.md), [Policies](../policies.md), [CLI](../cli.md).
