# Contracts are claims

**Question:** where do the numbers behind a verdict come from, and what happens when I change them?

A *contract* is a TOML file of hardware timing numbers. qtiming uses only what it states. Every latency carries an evidence class and a source string; a number the contract leaves out is *absent*, never guessed. Reference: [Contracts](../contracts.md), [Reading a verdict](../verdicts.md), [Errors](../errors.md).

```python
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent))
import _show

TP = _show.FAMILIES / "teleportation/tp_basic.qasm"
```

## The program
The same teleportation as in tutorial 01: the correction must start within 3000 ns of the measurement result arriving.

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
    

## 1. Inspect: `contract show`
Durations and latencies are printed in dt (IBM dt is 4 ns). The one IBM latency is `ff.default`, 150 dt = 600 ns, class `vendor`: IBM's public "about 600 ns" claim. Gate durations here come from an *unofficial offline snapshot*, a fixture, not a live backend.

```python
code, out = _show.run("contract", "show", "ibm_heron")
shown = json.loads(out.rsplit("[exit", 1)[0])
assert code == 0 and shown["latencies"]["ff.default"] == [0, 150, "vendor"] and shown["missing"] == []
```

    {
      "name": "ibm_heron",
      "personality": "ibm",
      "dt_ns": "4",
      "commit_lead_dt": null,
      "missing": [],
      "durations": {
        "cx": 20,
        "cz": 17,
        "h": 8,
        "measure": 545,
        "measure_2": 345,
        "reset": 250,
        "sx": 8,
        "x": 8,
        "z": 8
      },
      "latencies": {
        "ff.default": [
          0,
          150,
          "vendor"
        ]
      }
    }
    [exit 0]
    

## 2. Validate and see what is absent
`validate` reports `missing` fields. ARTIQ's contract has no `commit_lead` and no upper bound for `in2cpu`, and no stack except IBM ships gate durations. These are left absent on purpose.

```python
inst = "src/qtiming/contract/instances"
code, out = _show.run("contract", "validate", *[f"{inst}/{n}.toml" for n in ("ibm_heron", "q1", "artiq", "qua")])
assert code == 0 and "missing: timeline.commit_lead" in out and "placeholders=3" in out
```

    OK ibm_heron sha256=9cf4d27a06ae placeholders=0 missing=0 warnings=0
    OK qblox_q1 sha256=df77f741d36f placeholders=0 missing=0 warnings=2
    OK artiq_rtio sha256=f893d78201d1 placeholders=0 missing=2 warnings=0
      missing: latency.in2cpu.hi
      missing: timeline.commit_lead
    OK qm_qua sha256=87985e202758 placeholders=3 missing=0 warnings=0
    [exit 0]
    

## 3. Absent means stop or UNKNOWN, not a guess
Without gate durations the three non-IBM stacks refuse to run `tp_basic`:

```python
for c in ("artiq", "q1", "qua"):
    code, out = _show.run("check", TP, "--contract", c)
    assert code == 2 and "E-CT-MISSING" in out
```

    error: E-CT-MISSING: contract 'artiq_rtio' has no duration for 'h'
      hint: add it to [durations] or import it from the backend Target
    [exit 2]
    

    error: E-CT-MISSING: contract 'qblox_q1' has no duration for 'h'
      hint: add it to [durations] or import it from the backend Target
    [exit 2]
    

    error: E-CT-MISSING: contract 'qm_qua' has no duration for 'h'
      hint: add it to [durations] or import it from the backend Target
    [exit 2]
    

## 4. `--assume`: supply a number for one run
`--assume durations.NAME=NS` supplies a gate duration. **These numbers are illustrative, not vendor values** (the report says so with `note: contract assumed value`). With them each stack gives its own answer for the *same* program:

```python
DUR = ["--assume", "durations.h=32", "--assume", "durations.cx=200",
       "--assume", "durations.measure=1000", "--assume", "durations.x=32"]
code, out = _show.run("check", TP, "--contract", "qua", *DUR)
assert code == 0 and out.startswith("PROVED-UNDER") and "active_reset" in out
```

    PROVED-UNDER  (contract qm_qua, policy sync, sha256 fac3890f9435)
      assumptions (weakest class: vendor):
        active_reset: [0 ns, 224 ns]  vendor: QM claim: 224 ns active reset (vendor)
      O2b: 1 obligation(s): proved (tier 1, margin 0 ns)
      O3: 2 obligation(s): proved (tier 1, margin 2776 ns)
      O4: 11 obligation(s): proved (tier 0, margin 0 ns); proved (tier 1, margin 0 ns)
      note: contract assumed value: durations.h=32
      note: contract assumed value: durations.cx=200
      note: contract assumed value: durations.measure=1000
      note: contract assumed value: durations.x=32
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 0]
    

QUA is PROVED-UNDER its vendor claim for `active_reset`. ARTIQ has no `commit_lead`, so an obligation that needs it is UNKNOWN and the `why:` line names the key:

```python
code, out = _show.run("check", TP, "--contract", "artiq", *DUR)
assert code == 3 and out.startswith("UNKNOWN") and "timeline.commit_lead" in out
```

    UNKNOWN  (contract artiq_rtio, policy exp, sha256 8d63dcfd9f20)
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
      note: contract assumed value: durations.cx=200
      note: contract assumed value: durations.measure=1000
      note: contract assumed value: durations.x=32
      note: no executor trace: ARTIQ commit_lead is unspecified; the executor will not guess it
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 3]
    

Supply `commit_lead` (illustrative, 200 ns) and a bound for `in2cpu` (`KEY=LO:HI`) and ARTIQ now *refutes*: an RTIO event is committed too late. The `short by` figures come from the invented numbers, so read this as "if the lead were 200 ns", not as a fact about ARTIQ. O5 stays UNKNOWN because the symbolic encoding is not built.

```python
code, out = _show.run("check", TP, "--contract", "artiq", *DUR,
                      "--assume", "timeline.commit_lead=200", "--assume", "in2cpu=0:300")
assert code == 1 and out.startswith("REFUTED") and "short by 200 ns" in out and "unknown (tier -)" in out
```

    REFUTED  (contract artiq_rtio, policy exp, sha256 bec340355d18)
      why: O1 at node 1: RTIO event must be committed at least commit_lead before its timestamp
      why: O1 at node 2: RTIO event must be committed at least commit_lead before its timestamp
      why: O1 at node 11: RTIO event must be committed at least commit_lead before its timestamp
      O1 failed at E:/PROJECTS/Qtiming/benchmarks/families/teleportation/tp_basic.qasm:7 (tier 0, short by 200 ns)
      O1 failed at E:/PROJECTS/Qtiming/benchmarks/families/teleportation/tp_basic.qasm:8 (tier 0, short by 168 ns)
      O1 failed at E:/PROJECTS/Qtiming/benchmarks/families/teleportation/tp_basic.qasm:18 (tier 2)
      assumptions (weakest class: vendor):
        in2cpu: [0 ns, 300 ns]  vendor: --assume in2cpu=0:300
      O1: 5 obligation(s): proved (tier 0, margin 232 ns); proved (tier 0, margin 32 ns); refuted (tier 0, margin -168 ns); refuted (tier 0, margin -200 ns); refuted (tier 2)
      O3: 1 obligation(s): proved (tier 1, margin 3000 ns)
      O5: 1 obligation(s): unknown (tier -)
      note: contract assumed value: durations.h=32
      note: contract assumed value: durations.cx=200
      note: contract assumed value: durations.measure=1000
      note: contract assumed value: durations.x=32
      note: contract assumed value: timeline.commit_lead=200
      note: contract assumed value: in2cpu=0:300
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 1]
    

Q1 is predicated, and `tp_basic` has an `x` arm and an empty `else` arm. With a 32 ns `x` the two arms cannot be equalised, and the elaborator says so. Only when `x` is one RT instruction (4 ns, again illustrative) are the arms the same length:

```python
code, out = _show.run("check", TP, "--contract", "q1", *DUR)
assert code == 2 and "E-ELAB-Q1-NOT-EQUALISABLE" in out
Q1 = ["--assume", "durations.h=32", "--assume", "durations.cx=200",
      "--assume", "durations.measure=1000", "--assume", "durations.x=4"]
code, out = _show.run("check", TP, "--contract", "q1", *Q1)
assert code == 0 and out.startswith("PROVED-UNDER") and "trigger.network" in out
```

    error: E-ELAB-Q1-NOT-EQUALISABLE: arm totals differ: 8 dt when true, 1 dt when false
      hint: match RT instruction counts and durations, or use policy sync/exp
    [exit 2]
    

    PROVED-UNDER  (contract qblox_q1, policy eq, sha256 6fe4bc10658c)
      assumptions (weakest class: vendor):
        trigger.network: [212 ns, 240 ns]  vendor: docs.qblox.com trigger_handling; documented figure, not cycle-certified [verify page path]
      O1: 8 obligation(s): proved (tier 0, margin 0 ns); proved (tier 0, margin 1444 ns); proved (tier 0, margin 224 ns); proved (tier 0, margin 2440 ns); proved (tier 0, margin 2672 ns); proved (tier 0, margin 28 ns); proved (tier 0, margin 420 ns); proved (tier 0, margin 448 ns)
      O2a: 1 obligation(s): proved (tier 1, margin 0 ns)
      O3: 1 obligation(s): proved (tier 1, margin 2972 ns)
      O5: 1 obligation(s): proved (tier 0, margin 748 ns)
      note: contract assumed value: durations.h=32
      note: contract assumed value: durations.cx=200
      note: contract assumed value: durations.measure=1000
      note: contract assumed value: durations.x=4
      note: W-CT-ROUND: latency trigger.network [212, 239] ns -> [53, 60] dt (rounded outward)
      note: W-CT-ROUND: latency path.opip.base [149, 149] ns -> [37, 38] dt (rounded outward)
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 0]
    

## 5. Guard rails on what `--assume` may do
An assumption can only be class `vendor`, so a typed number can never make a verdict PROVED. And an assumption cannot silently override the Target: the snapshot says `h` is 32 ns, so `durations.h=40` is a conflict, not an override.

```python
code, out = _show.run("contract", "validate", f"{inst}/ibm_heron.toml", "--assume", "ff.default=0:600:cyc")
assert code == 1 and "E-CT-ASSUME" in out
code, out = _show.run("contract", "validate", f"{inst}/ibm_heron.toml", "--assume", "durations.h=40")
assert code == 1 and "E-CT-TARGET-CONFLICT" in out
```

    FAIL src/qtiming/contract/instances/ibm_heron.toml
      E-CT-ASSUME: --assume 'ff.default=0:600:cyc': only class 'vendor' is allowed
    [exit 1]
    

    FAIL src/qtiming/contract/instances/ibm_heron.toml
      E-CT-TARGET-CONFLICT: durations.h = 40 ns conflicts with Target (8 dt)
    [exit 1]
    

## 6. Compare: `contract diff`
Exit 1 means the contracts differ. The IBM numbers are dt-denominated from the snapshot; QUA has none.

```python
code, out = _show.run("contract", "diff", "ibm_heron", "qua")
assert code == 1 and "personality: 'ibm' -> 'qua'" in out
```

    name: 'ibm_heron' -> 'qm_qua'
    personality: 'ibm' -> 'qua'
    durations: {'cx': 20, 'cz': 17, 'h': 8, 'measure': 545, 'measure_2': 345, 'reset': 250, 'sx': 8, 'x': 8, 'z': 8} -> {}
    latencies: {'ff.default': [0, 150, 'vendor']} -> {'align.same_fem': [0, 3, 'vendor'], 'align.cross_fem': [0, 6, 'vendor'], 'align.cross_chassis': [0, 12, 'vendor'], 'active_reset': [0, 56, 'vendor']}
    [exit 1]
    

## 7. Sweep the claim: where does the verdict flip?
The only IBM latency is a vendor claim of at most 600 ns. What if it were larger? `--assume ff.default=0:N` re-runs the check with upper bound N. The program's deadline is 3000 ns.

```python
NS = [200, 600, 1000, 1500, 2000, 2500, 2900, 3000, 3004, 3100, 3500, 4000]
rows = []
for n in NS:
    _, out = _show.run("check", TP, "--contract", "ibm_heron", "--assume", f"ff.default=0:{n}", show=False)
    m = re.search(r"O3: .*?margin (-?\d+) ns", out)
    rows.append((n, out.split()[0], int(m.group(1)) if m else None))
print("ff upper bound (ns)  verdict        O3 margin (ns)")
for n, v, g in rows:
    print(f"{n:>19}  {v:<13}  {'' if g is None else g}")
flip = [n for n, v, _ in rows if v == "REFUTED"]
assert all(v == "PROVED-UNDER" for n, v, _ in rows if n <= 3000)
assert min(flip) == 3004 and dict((n, g) for n, _, g in rows)[3000] == 0
```

    ff upper bound (ns)  verdict        O3 margin (ns)
                    200  PROVED-UNDER   2800
                    600  PROVED-UNDER   2400
                   1000  PROVED-UNDER   2000
                   1500  PROVED-UNDER   1500
                   2000  PROVED-UNDER   1000
                   2500  PROVED-UNDER   500
                   2900  PROVED-UNDER   100
                   3000  PROVED-UNDER   0
                   3004  REFUTED        
                   3100  REFUTED        
                   3500  REFUTED        
                   4000  REFUTED        
    

Hand-made SVG of the same data: green dots are PROVED-UNDER, red are REFUTED. The line is the O3 margin, which falls one nanosecond per nanosecond until it hits zero at the deadline.

```python
from IPython.display import HTML, display

W, H, L, R, T, B = 640, 220, 60, 20, 20, 50
xs = lambda n: L + (W - L - R) * n / 4000
ys = lambda g: T + (H - T - B) * (1 - g / 3000)
pts = [(n, g) for n, _, g in rows if g is not None]
line = " ".join(f"{xs(n):.1f},{ys(g):.1f}" for n, g in pts)
dots = "".join(
    f'<circle cx="{xs(n):.1f}" cy="{(ys(g) if g is not None else H - B + 14):.1f}" r="5" '
    f'fill="{"#1a7f37" if v != "REFUTED" else "#cf222e"}"><title>{n} ns: {v}</title></circle>'
    for n, v, g in rows)
ticks = "".join(
    f'<text x="{xs(n):.1f}" y="{H - B + 36}" font-size="11" text-anchor="middle" fill="currentColor">{n}</text>'
    for n in (0, 1000, 2000, 3000, 4000))
svg = (
    f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Verdict versus feed-forward upper bound" '
    f'style="max-width:640px;color:#57606a">'
    f'<line x1="{L}" y1="{H - B}" x2="{W - R}" y2="{H - B}" stroke="currentColor"/>'
    f'<line x1="{xs(3000):.1f}" y1="{T}" x2="{xs(3000):.1f}" y2="{H - B}" stroke="#cf222e" stroke-dasharray="4"/>'
    f'<text x="{xs(3000) + 4:.1f}" y="{T + 10}" font-size="11" fill="#cf222e">deadline 3000 ns</text>'
    f'<line x1="{xs(600):.1f}" y1="{T}" x2="{xs(600):.1f}" y2="{H - B}" stroke="currentColor" stroke-dasharray="2"/>'
    f'<text x="{xs(600) + 4:.1f}" y="{T + 10}" font-size="11" fill="currentColor">vendor claim 600 ns</text>'
    f'<polyline points="{line}" fill="none" stroke="#1a7f37" stroke-width="1.5"/>{dots}{ticks}'
    f'<text x="{L - 8}" y="{ys(3000) + 4:.1f}" font-size="11" text-anchor="end" fill="currentColor">3000</text>'
    f'<text x="{L - 8}" y="{ys(0) + 4:.1f}" font-size="11" text-anchor="end" fill="currentColor">0</text>'
    f'<text x="{L - 8}" y="{H - B + 18}" font-size="11" text-anchor="end" fill="currentColor">refuted</text>'
    f'<text x="{(L + W - R) / 2}" y="{H - 4}" font-size="12" text-anchor="middle" fill="currentColor">'
    f'assumed ff.default upper bound (ns); line = O3 margin (ns)</text></svg>')
display(HTML(svg))
```

<svg viewBox="0 0 640 220" width="100%" role="img" aria-label="Verdict versus feed-forward upper bound" style="max-width:640px;color:#57606a"><line x1="60" y1="170" x2="620" y2="170" stroke="currentColor"/><line x1="480.0" y1="20" x2="480.0" y2="170" stroke="#cf222e" stroke-dasharray="4"/><text x="484.0" y="30" font-size="11" fill="#cf222e">deadline 3000 ns</text><line x1="144.0" y1="20" x2="144.0" y2="170" stroke="currentColor" stroke-dasharray="2"/><text x="148.0" y="30" font-size="11" fill="currentColor">vendor claim 600 ns</text><polyline points="88.0,30.0 144.0,50.0 200.0,70.0 270.0,95.0 340.0,120.0 410.0,145.0 466.0,165.0 480.0,170.0" fill="none" stroke="#1a7f37" stroke-width="1.5"/><circle cx="88.0" cy="30.0" r="5" fill="#1a7f37"><title>200 ns: PROVED-UNDER</title></circle><circle cx="144.0" cy="50.0" r="5" fill="#1a7f37"><title>600 ns: PROVED-UNDER</title></circle><circle cx="200.0" cy="70.0" r="5" fill="#1a7f37"><title>1000 ns: PROVED-UNDER</title></circle><circle cx="270.0" cy="95.0" r="5" fill="#1a7f37"><title>1500 ns: PROVED-UNDER</title></circle><circle cx="340.0" cy="120.0" r="5" fill="#1a7f37"><title>2000 ns: PROVED-UNDER</title></circle><circle cx="410.0" cy="145.0" r="5" fill="#1a7f37"><title>2500 ns: PROVED-UNDER</title></circle><circle cx="466.0" cy="165.0" r="5" fill="#1a7f37"><title>2900 ns: PROVED-UNDER</title></circle><circle cx="480.0" cy="170.0" r="5" fill="#1a7f37"><title>3000 ns: PROVED-UNDER</title></circle><circle cx="480.6" cy="184.0" r="5" fill="#cf222e"><title>3004 ns: REFUTED</title></circle><circle cx="494.0" cy="184.0" r="5" fill="#cf222e"><title>3100 ns: REFUTED</title></circle><circle cx="550.0" cy="184.0" r="5" fill="#cf222e"><title>3500 ns: REFUTED</title></circle><circle cx="620.0" cy="184.0" r="5" fill="#cf222e"><title>4000 ns: REFUTED</title></circle><text x="60.0" y="206" font-size="11" text-anchor="middle" fill="currentColor">0</text><text x="200.0" y="206" font-size="11" text-anchor="middle" fill="currentColor">1000</text><text x="340.0" y="206" font-size="11" text-anchor="middle" fill="currentColor">2000</text><text x="480.0" y="206" font-size="11" text-anchor="middle" fill="currentColor">3000</text><text x="620.0" y="206" font-size="11" text-anchor="middle" fill="currentColor">4000</text><text x="52" y="24.0" font-size="11" text-anchor="end" fill="currentColor">3000</text><text x="52" y="174.0" font-size="11" text-anchor="end" fill="currentColor">0</text><text x="52" y="188" font-size="11" text-anchor="end" fill="currentColor">refuted</text><text x="340.0" y="216" font-size="12" text-anchor="middle" fill="currentColor">assumed ff.default upper bound (ns); line = O3 margin (ns)</text></svg>

## 8. `--max-safe`: ask for the flip point directly
Instead of sweeping, bisect. The answer must equal the largest bound the sweep still proved.

```python
code, out = _show.run("check", TP, "--contract", "ibm_heron", "--max-safe", "ff.default")
assert code == 0 and "max safe ff.default.hi: 750 dt = 3000 ns" in out
```

    PROVED-UNDER  (contract ibm_heron, policy sync, sha256 9cf4d27a06ae)
      assumptions (weakest class: vendor):
        ff.default: [0 ns, 600 ns]  vendor: IBM blog, 2025-11-19 (feedforward about 600 ns); vendor claim, not a certified bound
      O2b: 1 obligation(s): proved (tier 1, margin 0 ns)
      O3: 2 obligation(s): proved (tier 1, margin 2400 ns)
      O4: 11 obligation(s): proved (tier 0, margin 0 ns); proved (tier 1, margin 0 ns)
      O7: 1 obligation(s): proved (tier 1, margin 0 ns)
      max safe ff.default.hi: 750 dt = 3000 ns
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 0]
    

## What just happened
- A contract is a set of claims, each with an evidence class and a source. `show`, `validate` and `diff` expose them.
- Absent numbers stop the run (`E-CT-MISSING`) or make the dependent obligation UNKNOWN. Nothing is filled in.
- `--assume` is a vendor-class, per-run override. It cannot raise a verdict to PROVED and cannot contradict the Target (`E-CT-TARGET-CONFLICT`). The numbers used for ARTIQ, Q1 and the durations are illustrative.
- The verdict flips from PROVED-UNDER to REFUTED exactly past the deadline, and `--max-safe` finds that point without a sweep. The 600 ns is a vendor claim: the proof is only as good as it.

Previous: [The four verdicts](02-four-verdicts.md).
