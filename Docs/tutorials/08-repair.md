# Automatic repair

**Question:** qtiming says my ARTIQ program is REFUTED. Can it fix it for me, and can I trust the fix?

`qtiming repair` proposes a patch for one kind of failure only: **O1**, the commit-lead (RTIO underflow) obligation. It inserts a declared `delay`, then **re-verifies** the patched program with the normal pipeline before showing it. It refuses O3 (deadlines). Reference: [Command reference](../cli.md), [Obligations](../obligations.md).

```python
import difflib, json, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent))
import _show
```

## The program and the numbers we have to supply
`artiq_burst` fires four `x` gates back to back, then measures. It is a synthetic kernel written for this repo, not ARTIQ project code.

```python
_show.source("artiq/artiq_burst.qasm")
```

    OPENQASM 3.0;
    // artiq_burst: back-to-back gates on one channel before a measurement (sequence-error / collision candidate)
    // synthetic ARTIQ-style kernel written by the qtiming authors, NOT external code (not from the ARTIQ project); exposed-timeline (EXP) form
    qubit[1] q;
    bit[1] c;
    
    x q[0];
    x q[0];
    x q[0];
    x q[0];
    c[0] = measure q[0];
    delay[800ns] q[0];
    @timing.policy exp
    box {
        if (c[0]) {
            x q[0];
        }
    }
    

The shipped `artiq` contract leaves `timeline.commit_lead`, gate durations and the `in2cpu` upper bound **absent**, because ARTIQ publishes no numbers for them. Without them `check` stops with a usage error, not a guess:

```python
BURST = _show.FAMILIES / "artiq/artiq_burst.qasm"
SLACK = _show.FAMILIES / "artiq/artiq_slack_neg.qasm"
code, out = _show.run("check", BURST, "--contract", "artiq")
assert code == 2 and "E-CT-MISSING" in out
```

    error: E-CT-MISSING: contract 'artiq_rtio' has no duration for 'x'
      hint: add it to [durations] or import it from the backend Target
    [exit 2]
    

So we supply them with `--assume`. **These values are illustrative, not ARTIQ numbers**: 32 ns per `x`, 1000 ns measurement, `commit_lead` 100 ns, `in2cpu` 0 to 300 ns. Every one is recorded as an assumption in the report.

```python
A = ["durations.x=32", "durations.measure=1000", "timeline.commit_lead=100", "in2cpu=0:300"]
ASSUME = [x for a in A for x in ("--assume", a)]
```

## 1. Before: REFUTED
Each `x` is issued back to back, so the CPU is behind the timeline. The shortfall against the 100 ns commit lead is 100, 68, 36 and 4 ns for the four gates.

```python
code, out = _show.run("check", BURST, "--contract", "artiq", *ASSUME)
assert code == 1 and out.startswith("REFUTED")
for s in ("short by 100 ns", "short by 68 ns", "short by 36 ns", "short by 4 ns"):
    assert s in out
```

    REFUTED  (contract artiq_rtio, policy exp, sha256 9fc816ccf863)
      why: O1 at node 1: RTIO event must be committed at least commit_lead before its timestamp
      why: O1 at node 2: RTIO event must be committed at least commit_lead before its timestamp
      why: O1 at node 3: RTIO event must be committed at least commit_lead before its timestamp
      why: O1 at node 4: RTIO event must be committed at least commit_lead before its timestamp
      O1 failed at E:/PROJECTS/Qtiming/benchmarks/families/artiq/artiq_burst.qasm:7 (tier 0, short by 100 ns)
      O1 failed at E:/PROJECTS/Qtiming/benchmarks/families/artiq/artiq_burst.qasm:8 (tier 0, short by 68 ns)
      O1 failed at E:/PROJECTS/Qtiming/benchmarks/families/artiq/artiq_burst.qasm:9 (tier 0, short by 36 ns)
      O1 failed at E:/PROJECTS/Qtiming/benchmarks/families/artiq/artiq_burst.qasm:10 (tier 0, short by 4 ns)
      assumptions (weakest class: vendor):
        in2cpu: [0 ns, 300 ns]  vendor: --assume in2cpu=0:300
      O1: 5 obligation(s): proved (tier 1, margin 400 ns); refuted (tier 0, margin -100 ns); refuted (tier 0, margin -36 ns); refuted (tier 0, margin -4 ns); refuted (tier 0, margin -68 ns)
      O5: 1 obligation(s): unknown (tier -)
      note: contract assumed value: durations.x=32
      note: contract assumed value: durations.measure=1000
      note: contract assumed value: timeline.commit_lead=100
      note: contract assumed value: in2cpu=0:300
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 1]
    

This verdict has no timeline picture: the HTML report for it contains no timeline, only the per-obligation shortfalls above.

## 2. `repair`
`--out` sends the repair summary to a file (here a temporary directory, never the repo); `--verbose` prints the patched program's verdict on screen.

```python
with tempfile.TemporaryDirectory() as d:
    summary = Path(d) / "repair.txt"
    code, out = _show.run("repair", BURST, "--contract", "artiq", *ASSUME, "--out", summary, "--verbose")
    saved = summary.read_text(encoding="utf-8")
print("--- contents of the --out file ---")
print(saved.rstrip())
assert "before: REFUTED  after: UNKNOWN" in saved
assert "insert before line 7:  delay[100ns] $0;  (100 dt)" in saved
assert code == 3 and out.startswith("UNKNOWN")
```

    UNKNOWN  (contract artiq_rtio, policy exp, sha256 9fc816ccf863)
      why: O5 at node 1: Tier 2 does not encode Events (O5) yet
      assumptions (weakest class: vendor):
        in2cpu: [0 ns, 300 ns]  vendor: --assume in2cpu=0:300
      O1: 5 obligation(s): proved (tier 0, margin 0 ns); proved (tier 0, margin 32 ns); proved (tier 0, margin 64 ns); proved (tier 0, margin 96 ns); proved (tier 1, margin 400 ns)
      O5: 1 obligation(s): unknown (tier -)
      note: contract assumed value: durations.x=32
      note: contract assumed value: durations.measure=1000
      note: contract assumed value: timeline.commit_lead=100
      note: contract assumed value: in2cpu=0:300
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 3]
    --- contents of the --out file ---
    repair: unknown: the program is UNKNOWN: O5 at node 1: Tier 2 does not encode Events (O5) yet
    before: REFUTED  after: UNKNOWN
      O1: insert before line 7:  delay[100ns] $0;  (100 dt)
    added idle time: 100 ns; the patched program was re-verified by the full pipeline
    

The patch is one declared delay of exactly the largest shortfall, 100 ns, before the first `x`. The **after** verdict is UNKNOWN, not PROVED, and the exit code is 3. In the patched verdict above all five O1 obligations are proved, and the only open item is **O5, which this build does not encode yet** (`Tier 2 does not encode Events (O5) yet`). qtiming reports that honestly instead of calling the patch proved.

## 3. The patch as a diff
`repair` prints the hunk; it does not write patched QASM. Applying the hunk by hand (`$0` is `q[0]`) gives the diff below, and checking that hand-patched file gives the same verdict as the one `repair` re-verified.

```python
src = BURST.read_text(encoding="utf-8").splitlines()
i = next(n for n, ln in enumerate(src) if ln.startswith("x q[0]"))
new = src[:i] + ["delay[100ns] q[0];"] + src[i:]
print("\n".join(difflib.unified_diff(src, new, "artiq_burst.qasm", "artiq_burst.patched.qasm", lineterm="", n=1)))
with tempfile.TemporaryDirectory() as d:
    p = Path(d) / "burst_patched.qasm"
    p.write_text("\n".join(new) + "\n", encoding="utf-8")
    code, out = _show.run("check", p, "--contract", "artiq", *ASSUME, show=False)
    for ln in out.splitlines():
        if ln.startswith(("UNKNOWN", "REFUTED", "  O1:", "  why:")):
            print(ln.split("  (")[0] if ln[0] != " " else ln)
    assert out.startswith("UNKNOWN") and "O5" in out and "refuted" not in out
    _show.report_svg(p, "artiq", *A)
```

    --- artiq_burst.qasm
    +++ artiq_burst.patched.qasm
    @@ -6,2 +6,3 @@
     
    +delay[100ns] q[0];
     x q[0];
    

    UNKNOWN
      why: O5 at node 2: Tier 2 does not encode Events (O5) yet
      O1: 5 obligation(s): proved (tier 0, margin 0 ns); proved (tier 0, margin 32 ns); proved (tier 0, margin 64 ns); proved (tier 0, margin 96 ns); proved (tier 1, margin 400 ns)
    

<svg viewBox="0 0 840 52" role="img" aria-label="typical run" width="100%">
<text x="2" y="14" font-size="11">typical run</text>
<text x="2" y="41" font-size="11">q0</text>
<line x1="80" x2="840" y1="44" y2="44" stroke="#bbb" stroke-width="1"/>
<g><title>event (node 2) at 100 ns</title><rect x="462.7" y="32" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>event (node 3) at 132 ns</title><rect x="585.1" y="32" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>event (node 4) at 164 ns</title><rect x="707.6" y="32" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>event (node 5) at 196 ns</title><rect x="830.0" y="32" width="6" height="14" fill="#2c6fbb"/></g>
<text x="80" y="50" font-size="10">0</text><text x="780" y="50" font-size="10">196 ns</text></svg>

The picture is the patched program's report (a typical run, as the report labels it). The text report above it shows the patched O1 margins: 0, 32, 64, 96 ns, none negative.

## 4. When it will not patch: `artiq_slack_neg`
Here the feedback is issued right after the measurement with no slack. With `in2cpu` bounded at 0 to 300 ns, `check` refutes O1 (found by the Tier 2 solver, which needs the `z3` extra).

```python
code, out = _show.run("check", SLACK, "--contract", "artiq", *ASSUME)
assert code == 1 and out.startswith("REFUTED") and "O1 failed" in out
```

    REFUTED  (contract artiq_rtio, policy exp, sha256 9fc816ccf863)
      why: O1 at node 6: RTIO event must be committed at least commit_lead before its timestamp
      O1 failed at E:/PROJECTS/Qtiming/benchmarks/families/artiq/artiq_slack_neg.qasm:11 (tier 2)
      assumptions (weakest class: vendor):
        in2cpu: [0 ns, 300 ns]  vendor: --assume in2cpu=0:300
      O1: 1 obligation(s): refuted (tier 2)
      O5: 1 obligation(s): unknown (tier -)
      note: contract assumed value: durations.x=32
      note: contract assumed value: durations.measure=1000
      note: contract assumed value: timeline.commit_lead=100
      note: contract assumed value: in2cpu=0:300
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 1]
    

```python
code, out = _show.run("repair", SLACK, "--contract", "artiq", *ASSUME)
assert code == 1 and "unsupported: no automatic patch for O1" in out
```

    repair: unsupported: no automatic patch for O1 (RTIO event must be committed at least commit_lead before its timestamp)
    before: REFUTED  after: REFUTED
    [exit 1]
    

`repair` gives up. Its search only pads shortfalls it can compute exactly (Tier 0 counterexamples with a fixed `short by N ns`); this one comes from the solver and depends on the `in2cpu` range, so there is no exact number to pad. **This differs from what the project plan expected** (an automatic O1 patch here); the shipped build reports "no automatic patch" and we show it as it is. Without the `in2cpu` bound the verdict is not even REFUTED:

```python
NOIN = ["--assume", "durations.x=32", "--assume", "durations.measure=1000",
        "--assume", "timeline.commit_lead=100"]
code, out = _show.run("check", SLACK, "--contract", "artiq", *NOIN)
assert code == 3 and out.startswith("UNKNOWN") and "fails if in2cpu is large enough" in out
code, out = _show.run("repair", SLACK, "--contract", "artiq", *NOIN)
assert code == 3 and "before: UNKNOWN  after: UNKNOWN" in out
```

    UNKNOWN  (contract artiq_rtio, policy exp, sha256 502d2565c39f)
      why: O1 at node 6: fails if in2cpu is large enough
      why: O5 at node 6: Tier 2 does not encode Events (O5) yet
      assumptions (weakest class: vendor):
        in2cpu: [0 ns, unbounded]  vendor: ARTIQ manual (no numeric bound)
      O1: 1 obligation(s): unknown (tier 2)
      O5: 1 obligation(s): unknown (tier -)
      note: contract assumed value: durations.x=32
      note: contract assumed value: durations.measure=1000
      note: contract assumed value: timeline.commit_lead=100
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 3]
    

    repair: unknown: the program is UNKNOWN: O1 at node 6: fails if in2cpu is large enough; O5 at node 6: Tier 2 does not encode Events (O5) yet
    before: UNKNOWN  after: UNKNOWN
    [exit 3]
    

`repair` needs a REFUTED program; an UNKNOWN one comes back unchanged (exit 3).

## 5. O3 is refused on purpose
A deadline (`@timing.within`) fails when the work starts too *late*, and a delay makes that worse. The O3 refusal needs a program with a deadline, so this one uses IBM's `tp_basic` (3000 ns deadline) with an assumed, illustrative 0 to 5000 ns feed-forward latency. The plan lists ARTIQ only for this tutorial; this is the one place it uses `ibm_heron`.

```python
TP = _show.FAMILIES / "teleportation/tp_basic.qasm"
code, out = _show.run("check", TP, "--contract", "ibm_heron", "--assume", "ff.default=0:5000")
assert code == 1 and "O3 failed" in out
```

    REFUTED  (contract ibm_heron, policy sync, sha256 9771035544fa)
      why: O3 at node 7: first operation must start within the deadline after the result
      O3 failed at E:/PROJECTS/Qtiming/benchmarks/families/teleportation/tp_basic.qasm:14 (tier 2)
      O3 failed at E:/PROJECTS/Qtiming/benchmarks/families/teleportation/tp_basic.qasm:14 (tier 2)
      assumptions (weakest class: vendor):
        ff.default: [0 ns, 5000 ns]  vendor: --assume ff.default=0:5000
      O2b: 1 obligation(s): proved (tier 1, margin 0 ns)
      O3: 2 obligation(s): refuted (tier 2)
      O4: 11 obligation(s): proved (tier 0, margin 0 ns); proved (tier 1, margin 0 ns)
      O7: 1 obligation(s): proved (tier 1, margin 0 ns)
      timeline (counterexample):
        t(ns)     0                                                7404
        q0        .h.................m.........................................
        q1        cc.................m.........................................
        q2        c..........................................................dx
      note: contract assumed value: ff.default=0:5000
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 1]
    

```python
code, out = _show.run("repair", TP, "--contract", "ibm_heron", "--assume", "ff.default=0:5000")
assert code == 1 and "unsupported: O3 (deadline): a delay makes it worse" in out
assert "before: REFUTED  after: REFUTED" in out
```

    repair: unsupported: O3 (deadline): a delay makes it worse; change the policy or the program
    before: REFUTED  after: REFUTED
    [exit 1]
    

## What just happened
- `repair` fixed `artiq_burst`: one inserted 100 ns delay, re-verified by the full pipeline. The result is UNKNOWN only because O5 is not encoded in this build; no O1 obligation is left failing.
- It declined `artiq_slack_neg` (solver-found O1 failure, no exact shortfall) and `tp_basic` (O3: a delay would worsen it), and said why.
- Every number on the ARTIQ side was supplied by `--assume` and is illustrative, not vendor data.

See also [Command reference](../cli.md) and [Obligations](../obligations.md).
