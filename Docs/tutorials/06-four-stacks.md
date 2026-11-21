# Same circuit, four stacks

**Question:** I have one dynamic circuit. What does qtiming say about it on IBM Heron, Quantum Machines QUA, Qblox Q1 and ARTIQ?

The answer is four different outcomes, because the four controllers handle the timing of a branch differently. Reference: [Contracts](../contracts.md), [Command reference](../cli.md), [Reading a verdict](../verdicts.md), [Error codes](../errors.md).

**Read this first.** Only the IBM contract publishes gate durations (from an unofficial snapshot). On the other three stacks the durations below are **illustrative `--assume` values chosen for this tutorial**, not vendor numbers. The verdicts show how qtiming behaves, not how fast any real controller is.

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent))
import _show

TP = _show.FAMILIES / "teleportation/tp_basic.qasm"
TP_Q1 = _show.FAMILIES / "teleportation/tp_q1.qasm"
# Illustrative gate durations (ns) for the three contracts that publish none.
DUR = ["durations.h=32", "durations.cx=64", "durations.x=32", "durations.measure=1000"]

def check(prog, contract, *assume, show=True):
    args = ["check", prog, "--contract", contract]
    for a in assume:
        args += ["--assume", a]
    return _show.run(*args, show=show)
```

## The program
`tp_basic` is teleportation with one classical correction. It has no timing policy of its own, so each contract's default branch policy applies.

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
    

## Stack 1: IBM Heron
The contract carries gate durations from an IBM Target snapshot. The only assumption is IBM's public claim that feed-forward takes about 600 ns. It is labelled *vendor*, so the verdict is PROVED-UNDER.

```python
code, ibm = check(TP, "ibm_heron")
assert code == 0 and ibm.startswith("PROVED-UNDER") and "ff.default" in ibm
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
    

## Stack 2: Quantum Machines QUA
With no assumptions the run stops: the QUA contract has no duration for `h`. That is `E-CT-MISSING`, an exit 2, not a verdict.

```python
code, qua0 = check(TP, "qua")
assert code == 2 and "E-CT-MISSING" in qua0
```

    error: E-CT-MISSING: contract 'qm_qua' has no duration for 'h'
      hint: add it to [durations] or import it from the backend Target
    [exit 2]
    

Supplying durations with `--assume` gets a verdict. The only latency the verdict leans on is QM's vendor claim of 224 ns for active reset.

```python
code, qua = check(TP, "qua", *DUR)
assert code == 0 and qua.startswith("PROVED-UNDER") and "active_reset" in qua
```

    PROVED-UNDER  (contract qm_qua, policy sync, sha256 d44238256a60)
      assumptions (weakest class: vendor):
        active_reset: [0 ns, 224 ns]  vendor: QM claim: 224 ns active reset (vendor)
      O2b: 1 obligation(s): proved (tier 1, margin 0 ns)
      O3: 2 obligation(s): proved (tier 1, margin 2776 ns)
      O4: 11 obligation(s): proved (tier 0, margin 0 ns); proved (tier 1, margin 0 ns)
      note: contract assumed value: durations.h=32
      note: contract assumed value: durations.cx=64
      note: contract assumed value: durations.x=32
      note: contract assumed value: durations.measure=1000
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 0]
    

## Stack 3: Qblox Q1
Q1 sequencers have no real branches. Both arms of an `if` are predicated, so the arms must take the same time. `tp_basic` has an `x` in one arm and nothing in the other, so qtiming refuses to build the graph: `E-ELAB-Q1-NOT-EQUALISABLE`, exit 2. This is a statement about the program on this stack, not a timing verdict.

```python
code, q1 = check(TP, "q1", *DUR)
assert code == 2 and "E-ELAB-Q1-NOT-EQUALISABLE" in q1
```

    error: E-ELAB-Q1-NOT-EQUALISABLE: arm totals differ: 8 dt when true, 1 dt when false
      hint: match RT instruction counts and durations, or use policy sync/exp
    [exit 2]
    

`tp_q1.qasm` is the same teleportation rewritten for Q1. Both arms hold one real-time instruction of the same duration, and the `eq` policy is declared.

```python
_show.source("teleportation/tp_q1.qasm")
```

    OPENQASM 3.0;
    // Teleportation for a predicated backend (Q1): the two arms hold one RT instruction of the same
    // duration, so the EQ policy is satisfiable (equal counts and durations; see plan 8.5).
    qubit[3] q;
    bit[2] c;
    
    h q[1];
    cx q[1], q[2];
    cx q[0], q[1];
    h q[0];
    c[0] = measure q[0];
    c[1] = measure q[1];
    delay[400ns] q[2];
    
    @timing.policy eq
    box {
        if (c[1]) {
            x q[2];
        } else {
            delay[32ns] q[2];
        }
    }
    

```python
code, q1v = check(TP_Q1, "q1", *DUR)
assert code == 0 and q1v.startswith("PROVED-UNDER") and "trigger.network" in q1v
```

    PROVED-UNDER  (contract qblox_q1, policy eq, sha256 c9650047ddee)
      assumptions (weakest class: vendor):
        trigger.network: [212 ns, 240 ns]  vendor: docs.qblox.com trigger_handling; documented figure, not cycle-certified [verify page path]
      O1: 10 obligation(s): proved (tier 0, margin 0 ns); proved (tier 0, margin 1172 ns); proved (tier 0, margin 148 ns); proved (tier 0, margin 176 ns); proved (tier 0, margin 2168 ns); proved (tier 0, margin 2564 ns); proved (tier 0, margin 2792 ns); proved (tier 0, margin 2796 ns); proved (tier 0, margin 28 ns); proved (tier 0, margin 88 ns)
      O2a: 2 obligation(s): proved (tier 1, margin 400 ns); proved (tier 2)
      O5: 1 obligation(s): proved (tier 0, margin 748 ns)
      note: contract assumed value: durations.h=32
      note: contract assumed value: durations.cx=64
      note: contract assumed value: durations.x=32
      note: contract assumed value: durations.measure=1000
      note: W-CT-ROUND: latency trigger.network [212, 239] ns -> [53, 60] dt (rounded outward)
      note: W-CT-ROUND: latency path.opip.base [149, 149] ns -> [37, 38] dt (rounded outward)
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 0]
    

The assumption here is Qblox's documented trigger-network latency (212 to 240 ns, class *vendor*; the contract notes the documentation page path still needs verifying).

## Stack 4: ARTIQ
ARTIQ's RTIO needs the *commit lead*: how long before its timestamp an event must be committed. The shipped contract does not publish it, so the dependent obligations are UNKNOWN and the report says which field is missing.

```python
code, art = check(TP, "artiq", *DUR)
assert code == 3 and art.startswith("UNKNOWN") and "timeline.commit_lead" in art
```

    UNKNOWN  (contract artiq_rtio, policy exp, sha256 0c124dd6fbf4)
      why: O1 at node 1: missing contract field: timeline.commit_lead
      why: O1 at node 2: missing contract field: timeline.commit_lead
      why: O1 at node 3: missing contract field: timeline.commit_lead
      why: O1 at node 4: missing contract field: timeline.commit_lead
      why: O1 at node 11: missing contract field: timeline.commit_lead
      why: O5 at node 1: Tier 2 does not encode Events (O5) yet
      assumptions (weakest class: vendor):
        in2cpu: [0 ns, unbounded]  vendor: ARTIQ manual (no numeric bound)
      O1: 5 obligation(s): unknown (tier -)
      O3: 1 obligation(s): proved (tier 1, margin 3000 ns)
      O5: 1 obligation(s): unknown (tier -)
      note: contract assumed value: durations.h=32
      note: contract assumed value: durations.cx=64
      note: contract assumed value: durations.x=32
      note: contract assumed value: durations.measure=1000
      note: no executor trace: ARTIQ commit_lead is unspecified; the executor will not guess it
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 3]
    

Assuming a commit lead moves the run on. The two values below are **illustrative**.
- `commit_lead=0`: the O1 checks that do not depend on the CPU-to-RTIO latency pass, but that latency (`in2cpu`) has no published upper bound, so one check stays UNKNOWN.
- `commit_lead=50`: the first events in the program are issued with no slack, so O1 fails and the verdict is REFUTED.

```python
code, art0 = check(TP, "artiq", *DUR, "timeline.commit_lead=0")
assert code == 3 and art0.startswith("UNKNOWN") and "in2cpu is large enough" in art0
```

    UNKNOWN  (contract artiq_rtio, policy exp, sha256 a8b50aa0d942)
      why: O1 at node 11: fails if in2cpu is large enough
      why: O5 at node 1: Tier 2 does not encode Events (O5) yet
      assumptions (weakest class: vendor):
        in2cpu: [0 ns, unbounded]  vendor: ARTIQ manual (no numeric bound)
      O1: 5 obligation(s): proved (tier 0, margin 0 ns); proved (tier 0, margin 160 ns); proved (tier 0, margin 32 ns); proved (tier 0, margin 96 ns); unknown (tier 2)
      O3: 1 obligation(s): proved (tier 1, margin 3000 ns)
      O5: 1 obligation(s): unknown (tier -)
      note: contract assumed value: durations.h=32
      note: contract assumed value: durations.cx=64
      note: contract assumed value: durations.x=32
      note: contract assumed value: durations.measure=1000
      note: contract assumed value: timeline.commit_lead=0
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 3]
    

```python
code, art50 = check(TP, "artiq", *DUR, "timeline.commit_lead=50")
assert code == 1 and art50.startswith("REFUTED") and "short by 50 ns" in art50
```

    REFUTED  (contract artiq_rtio, policy exp, sha256 47801973321c)
      why: O1 at node 1: RTIO event must be committed at least commit_lead before its timestamp
      why: O1 at node 2: RTIO event must be committed at least commit_lead before its timestamp
      O1 failed at E:/PROJECTS/Qtiming/benchmarks/families/teleportation/tp_basic.qasm:7 (tier 0, short by 50 ns)
      O1 failed at E:/PROJECTS/Qtiming/benchmarks/families/teleportation/tp_basic.qasm:8 (tier 0, short by 18 ns)
      assumptions (weakest class: vendor):
        in2cpu: [0 ns, unbounded]  vendor: ARTIQ manual (no numeric bound)
      O1: 5 obligation(s): proved (tier 0, margin 110 ns); proved (tier 0, margin 46 ns); refuted (tier 0, margin -18 ns); refuted (tier 0, margin -50 ns); unknown (tier 2)
      O3: 1 obligation(s): proved (tier 1, margin 3000 ns)
      O5: 1 obligation(s): unknown (tier -)
      note: contract assumed value: durations.h=32
      note: contract assumed value: durations.cx=64
      note: contract assumed value: durations.x=32
      note: contract assumed value: durations.measure=1000
      note: contract assumed value: timeline.commit_lead=50
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 1]
    

## Side by side
The table is computed from real runs of both programs on all four contracts. Nothing is typed in by hand. IBM runs with no `--assume`; the other three use the illustrative durations above, and ARTIQ has no commit lead.

```python
from IPython.display import HTML, display

STACKS = [("ibm_heron", []), ("qua", DUR), ("q1", DUR), ("artiq", DUR)]
ROWS = [("tp_basic", TP), ("tp_q1", TP_Q1)]

def outcome(prog, contract, assume):
    code, out = check(prog, contract, *assume, show=False)
    first = out.splitlines()[0]
    if first.startswith("error:"):
        return first.split(":")[1].strip(), "error", code
    return first.split()[0], "verdict", code

grid = {(p, c): outcome(path, c, a) for p, path in ROWS for c, a in STACKS}
COLOUR = {"PROVED-UNDER": "#1b7f3b", "PROVED": "#1b7f3b", "REFUTED": "#b3261e", "UNKNOWN": "#8a6d00"}
CELL = "padding:6px 10px;border:1px solid #8884"

def td(v):
    return f'<td style="{CELL}"><b style="color:{COLOUR.get(v[0], "#555")}">{v[0]}</b><br><small>{v[1]}, exit {v[2]}</small></td>'

head = "".join(f'<th style="{CELL}">{c}</th>' for c, _ in STACKS)
body = "".join(
    f'<tr><th style="{CELL};text-align:left">{p}</th>' + "".join(td(grid[p, c]) for c, _ in STACKS) + "</tr>"
    for p, _ in ROWS
)
display(HTML(f'<table style="border-collapse:collapse"><tr><th></th>{head}</tr>{body}</table>'))
```

<table style="border-collapse:collapse"><tr><th></th><th style="padding:6px 10px;border:1px solid #8884">ibm_heron</th><th style="padding:6px 10px;border:1px solid #8884">qua</th><th style="padding:6px 10px;border:1px solid #8884">q1</th><th style="padding:6px 10px;border:1px solid #8884">artiq</th></tr><tr><th style="padding:6px 10px;border:1px solid #8884;text-align:left">tp_basic</th><td style="padding:6px 10px;border:1px solid #8884"><b style="color:#1b7f3b">PROVED-UNDER</b><br><small>verdict, exit 0</small></td><td style="padding:6px 10px;border:1px solid #8884"><b style="color:#1b7f3b">PROVED-UNDER</b><br><small>verdict, exit 0</small></td><td style="padding:6px 10px;border:1px solid #8884"><b style="color:#555">E-ELAB-Q1-NOT-EQUALISABLE</b><br><small>error, exit 2</small></td><td style="padding:6px 10px;border:1px solid #8884"><b style="color:#8a6d00">UNKNOWN</b><br><small>verdict, exit 3</small></td></tr><tr><th style="padding:6px 10px;border:1px solid #8884;text-align:left">tp_q1</th><td style="padding:6px 10px;border:1px solid #8884"><b style="color:#1b7f3b">PROVED-UNDER</b><br><small>verdict, exit 0</small></td><td style="padding:6px 10px;border:1px solid #8884"><b style="color:#1b7f3b">PROVED-UNDER</b><br><small>verdict, exit 0</small></td><td style="padding:6px 10px;border:1px solid #8884"><b style="color:#1b7f3b">PROVED-UNDER</b><br><small>verdict, exit 0</small></td><td style="padding:6px 10px;border:1px solid #8884"><b style="color:#8a6d00">UNKNOWN</b><br><small>verdict, exit 3</small></td></tr></table>

```python
assert grid["tp_basic", "ibm_heron"] == ("PROVED-UNDER", "verdict", 0)
assert grid["tp_basic", "qua"] == ("PROVED-UNDER", "verdict", 0)
assert grid["tp_basic", "q1"] == ("E-ELAB-Q1-NOT-EQUALISABLE", "error", 2)
assert grid["tp_basic", "artiq"] == ("UNKNOWN", "verdict", 3)
assert grid["tp_q1", "q1"] == ("PROVED-UNDER", "verdict", 0)
assert grid["tp_q1", "artiq"] == ("UNKNOWN", "verdict", 3)
```

The `tp_q1` row is the Q1-shaped variant. It is also accepted on the other stacks, where it behaves like `tp_basic`.

## What just happened
- One circuit, four contracts, four different answers. PROVED-UNDER on IBM and QUA (each rests on a **vendor claim**), a structural refusal on Q1, UNKNOWN on ARTIQ.
- `E-CT-MISSING` and UNKNOWN are how qtiming reports numbers a vendor has not published. Supplying a value with `--assume` is your own claim, and the report records it.
- The `--assume` values used here (gate durations, `commit_lead`) are illustrative. The verdicts on QUA, Q1 and ARTIQ say nothing about real hardware speed.
- Q1 needs the program written for predication (`tp_q1`); the other stacks accept `tp_basic`.

Try other programs and sweep the main latency of each stack on the [comparison page](compare.md). More on the contracts behind these numbers: [Contracts](../contracts.md).
