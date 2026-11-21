# The four verdicts

**Question:** `check` printed `PROVED-UNDER` (or `UNKNOWN`). Is that a pass? What would make it `PROVED`?

Every `check` ends in exactly one of four verdicts. This tutorial produces each one from a real program, on IBM Heron and on ARTIQ, and shows how `--strict-proved` and `--assume` change what you get. Reference: [Reading a verdict](../verdicts.md), [Contracts](../contracts.md), [Command reference](../cli.md).

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent))
import _show
from IPython.display import HTML, display

TUT = Path.cwd().relative_to(_show.ROOT)  # tutorials/02-four-verdicts, repo-relative
FAM = _show.FAMILIES

def card(rows):
    """Verdict cards, one per (title, exit code, report text). The label is text, not just colour."""
    import html
    css = ("<style>.qv{display:grid;grid-template-columns:repeat(auto-fit,minmax(15rem,1fr));gap:.6rem}"
           ".qv div{border:1px solid #8886;border-left:6px solid var(--c);border-radius:6px;padding:.5rem .7rem}"
           ".qv b{font-size:1.05em}.qv small{display:block;opacity:.8}</style>")
    colour = {"PROVED": "#1a7f37", "PROVED-UNDER": "#9a6700", "REFUTED": "#cf222e", "UNKNOWN": "#6e7781"}
    out = []
    for title, code, text in rows:
        v = text.split()[0]
        out.append(f'<div style="--c:{colour[v]}"><b>{html.escape(v)}</b> (exit {code})'
                   f'<small>{html.escape(title)}</small></div>')
    display(HTML(css + '<div class="qv">' + "".join(out) + "</div>"))
```

## How a program gets its verdict
`check` generates timing obligations and the result is the **weakest** of them, in the order `REFUTED`, `UNKNOWN`, `PROVED-UNDER`, `PROVED`. One failing obligation refutes the whole program; one undecided obligation makes it unknown even if the rest passed.

## 1. PROVED: nothing depends on a latency
A branch-free Bell circuit. No feed-forward, so no obligation depends on an unpublished or vendor-claimed number.

```python
_show.source(TUT / "plain.qasm")
```

    OPENQASM 3.0;
    // plain: a branch-free circuit; no obligation depends on a latency
    qubit[2] q;
    bit[2] c;
    
    h q[0];
    cx q[0], q[1];
    c[0] = measure q[0];
    c[1] = measure q[1];
    

```python
code, out = _show.run("check", TUT / "plain.qasm", "--contract", "ibm_heron")
assert code == 0 and out.startswith("PROVED ") and "assumptions" not in out
proved = (code, out)
```

    PROVED  (contract ibm_heron, policy sync, sha256 9cf4d27a06ae)
      O4: 5 obligation(s): proved (tier 0, margin 0 ns)
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 0]
    

No `assumptions:` block: the result was decided by exact evaluation (tier 0). This is the only way a program reaches `PROVED` with the shipped contracts: every shipped contract states its latencies at the `vendor` class, and only `cyc` or `cert` evidence can discharge a latency-dependent obligation (see [assumption classes](../verdicts.md#assumptions-and-evidence-classes)). I found no family program with a branch that is PROVED, and `--assume` cannot raise a number above `vendor`.

## 2. PROVED-UNDER: true if the vendor number is
Teleportation with a correction branch. It holds if the feed-forward latency stays within IBM's public claim.

```python
code, out = _show.run("check", FAM / "teleportation/tp_basic.qasm", "--contract", "ibm_heron")
assert code == 0 and out.startswith("PROVED-UNDER") and "weakest class: vendor" in out
under = (code, out)
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
    

Read the assumption line: key `ff.default`, interval `[0 ns, 600 ns]`, class `vendor`, and the citation labelled *vendor claim, not a certified bound*. Exit code is 0, so a CI gate would pass. If that is too weak for you, add `--strict-proved`:

```python
code, out = _show.run("check", FAM / "teleportation/tp_basic.qasm", "--contract", "ibm_heron", "--strict-proved")
assert code == 1 and out.startswith("PROVED-UNDER")
strict = (code, out)
```

    PROVED-UNDER  (contract ibm_heron, policy sync, sha256 9cf4d27a06ae)
      assumptions (weakest class: vendor):
        ff.default: [0 ns, 600 ns]  vendor: IBM blog, 2025-11-19 (feedforward about 600 ns); vendor claim, not a certified bound
      O2b: 1 obligation(s): proved (tier 1, margin 0 ns)
      O3: 2 obligation(s): proved (tier 1, margin 2400 ns)
      O4: 11 obligation(s): proved (tier 0, margin 0 ns); proved (tier 1, margin 0 ns)
      O7: 1 obligation(s): proved (tier 1, margin 0 ns)
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 1]
    

Same verdict text, exit 1. And `--strict-proved` leaves a real `PROVED` alone:

```python
code, out = _show.run("check", TUT / "plain.qasm", "--contract", "ibm_heron", "--strict-proved")
assert code == 0 and out.startswith("PROVED ")
```

    PROVED  (contract ibm_heron, policy sync, sha256 9cf4d27a06ae)
      O4: 5 obligation(s): proved (tier 0, margin 0 ns)
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 0]
    

### Changing the assumption changes the verdict
`--assume ff.default=LO:HI` overrides the latency for one run (always class `vendor`, and recorded in the report). The deadline in `tp_basic` is 3000 ns, so a much slower feed-forward should break it. The 4000 ns here is illustrative, not a vendor value.

```python
code, out = _show.run("check", FAM / "teleportation/tp_basic.qasm", "--contract", "ibm_heron",
                      "--assume", "ff.default=0:4000")
assert code == 1 and out.startswith("REFUTED")
```

    REFUTED  (contract ibm_heron, policy sync, sha256 72af101a0bc1)
      why: O3 at node 7: first operation must start within the deadline after the result
      O3 failed at E:/PROJECTS/Qtiming/benchmarks/families/teleportation/tp_basic.qasm:14 (tier 2)
      O3 failed at E:/PROJECTS/Qtiming/benchmarks/families/teleportation/tp_basic.qasm:14 (tier 2)
      assumptions (weakest class: vendor):
        ff.default: [0 ns, 4000 ns]  vendor: --assume ff.default=0:4000
      O2b: 1 obligation(s): proved (tier 1, margin 0 ns)
      O3: 2 obligation(s): refuted (tier 2)
      O4: 11 obligation(s): proved (tier 0, margin 0 ns); proved (tier 1, margin 0 ns)
      O7: 1 obligation(s): proved (tier 1, margin 0 ns)
      timeline (counterexample):
        t(ns)     0                                                6404
        q0        .ch...................m......................................
        q1        hc....................m......................................
        q2        .c.........................................................dx
      note: contract assumed value: ff.default=0:4000
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 1]
    

## 3. REFUTED: a concrete counterexample
`tp_sync` demands that the idle gap on `q2` not vary with the outcome. It does vary, by 2 ns.

```python
code, out = _show.run("check", FAM / "teleportation/tp_sync.qasm", "--contract", "ibm_heron")
assert code == 1 and out.startswith("REFUTED") and "second execution" in out
refuted = (code, out)
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
    

```python
_show.report_svg(FAM / "teleportation/tp_sync.qasm", "ibm_heron")
```

<svg viewBox="0 0 840 104" role="img" aria-label="counterexample" width="100%">
<text x="2" y="14" font-size="11">counterexample</text>
<text x="2" y="41" font-size="11">q0</text>
<line x1="80" x2="840" y1="44" y2="44" stroke="#bbb" stroke-width="1"/>
<text x="2" y="67" font-size="11">q1</text>
<line x1="80" x2="840" y1="70" y2="70" stroke="#bbb" stroke-width="1"/>
<text x="2" y="93" font-size="11">q2</text>
<line x1="80" x2="840" y1="96" y2="96" stroke="#bbb" stroke-width="1"/>
<g><title>h (node 1) at 32 ns</title><rect x="90.0" y="58" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>cx (node 2) at 112 ns</title><rect x="114.9" y="58" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>cx (node 2) at 112 ns</title><rect x="114.9" y="84" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>cx (node 3) at 192 ns</title><rect x="139.9" y="32" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>cx (node 3) at 192 ns</title><rect x="139.9" y="58" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>h (node 4) at 224 ns</title><rect x="149.8" y="32" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>measure (node 5) at 2404 ns</title><rect x="829.4" y="32" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>measure (node 6) at 2372 ns</title><rect x="819.4" y="58" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>x (node 11) at 2406 ns</title><rect x="830.0" y="84" width="6" height="14" fill="#2c6fbb"/></g>
<text x="80" y="102" font-size="10">0</text><text x="780" y="102" font-size="10">2406 ns</text></svg>
<svg viewBox="0 0 840 104" role="img" aria-label="second execution" width="100%">
<text x="2" y="14" font-size="11">second execution</text>
<text x="2" y="41" font-size="11">q0</text>
<line x1="80" x2="840" y1="44" y2="44" stroke="#bbb" stroke-width="1"/>
<text x="2" y="67" font-size="11">q1</text>
<line x1="80" x2="840" y1="70" y2="70" stroke="#bbb" stroke-width="1"/>
<text x="2" y="93" font-size="11">q2</text>
<line x1="80" x2="840" y1="96" y2="96" stroke="#bbb" stroke-width="1"/>
<g><title>h (node 1) at 32 ns</title><rect x="90.0" y="58" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>cx (node 2) at 112 ns</title><rect x="114.9" y="58" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>cx (node 2) at 112 ns</title><rect x="114.9" y="84" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>cx (node 3) at 192 ns</title><rect x="139.9" y="32" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>cx (node 3) at 192 ns</title><rect x="139.9" y="58" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>h (node 4) at 224 ns</title><rect x="149.9" y="32" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>measure (node 5) at 2404 ns</title><rect x="830.0" y="32" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>measure (node 6) at 2372 ns</title><rect x="820.0" y="58" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>x (node 11) at 2404 ns</title><rect x="830.0" y="84" width="6" height="14" fill="#2c6fbb"/></g>
<text x="80" y="102" font-size="10">0</text><text x="780" y="102" font-size="10">2404 ns</text></svg>

The two timelines are the counterexample (the report text above prints both). Every REFUTED is replayed in an independent executor before it is reported; see [tutorial 01](01-first-verdict.md).

## 4. UNKNOWN: the tool will not guess
Same program, but with the SMT solver (tier 2) switched off. Tier 1 can only prove, never refute, so the one obligation it cannot prove stays undecided.

```python
code, out = _show.run("check", FAM / "teleportation/tp_sync.qasm", "--contract", "ibm_heron", "--no-tier2")
assert code == 3 and out.startswith("UNKNOWN") and "Tier 2 is disabled" in out
unknown = (code, out)
```

    UNKNOWN  (contract ibm_heron, policy sync, sha256 9cf4d27a06ae)
      why: O4 at node 11: Tier 1 inconclusive and Tier 2 is disabled
      assumptions (weakest class: vendor):
        ff.default: [0 ns, 600 ns]  vendor: IBM blog, 2025-11-19 (feedforward about 600 ns); vendor claim, not a certified bound
      O4: 9 obligation(s): proved (tier 0, margin 0 ns); unknown (tier -)
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 3]
    

Exit 3 is neither pass nor fail. Treat it as "not checked". More reasons for UNKNOWN show up on ARTIQ.

## ARTIQ: how absent numbers play out
The `artiq` contract publishes no gate durations, no commit lead and no upper bound for `in2cpu`. Without durations the run stops with an error (exit 2). The programs are synthetic, written by the qtiming authors, not ARTIQ code, and every number I assume below is illustrative.

```python
prog = FAM / "artiq/artiq_reset_fb.qasm"
_show.source(prog)
```

    OPENQASM 3.0;
    // artiq_reset_fb: measure, wait out the result latency, conditionally flip
    // synthetic ARTIQ-style kernel written by the qtiming authors, NOT external code (not from the ARTIQ project); exposed-timeline (EXP) form
    qubit[1] q;
    bit[1] c;
    
    c[0] = measure q[0];
    delay[800ns] q[0];
    @timing.policy exp
    box {
        if (c[0]) {
            x q[0];
        }
    }
    

```python
D = ["--assume", "durations.x=100", "--assume", "durations.measure=1000", "--assume", "durations.h=50"]
code, out = _show.run("check", prog, "--contract", "artiq")
assert code == 2 and "E-CT-MISSING" in out
```

    error: E-CT-MISSING: contract 'artiq_rtio' has no duration for 'x'
      hint: add it to [durations] or import it from the backend Target
    [exit 2]
    

Supply durations: now the commit lead is the missing number.

```python
code, out = _show.run("check", prog, "--contract", "artiq", *D)
assert code == 3 and "missing contract field: timeline.commit_lead" in out
a1 = (code, out)
```

    UNKNOWN  (contract artiq_rtio, policy exp, sha256 06e2688c8777)
      why: O1 at node 7: missing contract field: timeline.commit_lead
      why: O5 at node 7: Tier 2 does not encode Events (O5) yet
      assumptions (weakest class: vendor):
        in2cpu: [0 ns, unbounded]  vendor: ARTIQ manual (no numeric bound)
      O1: 1 obligation(s): unknown (tier -)
      O5: 1 obligation(s): unknown (tier -)
      note: contract assumed value: durations.x=100
      note: contract assumed value: durations.measure=1000
      note: contract assumed value: durations.h=50
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 3]
    

Supply the commit lead too: the `in2cpu` latency has no upper bound, so the counterexample needs an unbounded latency, and that is UNKNOWN, never REFUTED.

```python
L = [*D, "--assume", "timeline.commit_lead=200"]
code, out = _show.run("check", prog, "--contract", "artiq", *L)
assert code == 3 and "fails if in2cpu is large enough" in out
a2 = (code, out)
```

    UNKNOWN  (contract artiq_rtio, policy exp, sha256 25fb9ef1b8c6)
      why: O1 at node 7: fails if in2cpu is large enough
      why: O5 at node 7: Tier 2 does not encode Events (O5) yet
      assumptions (weakest class: vendor):
        in2cpu: [0 ns, unbounded]  vendor: ARTIQ manual (no numeric bound)
      O1: 1 obligation(s): unknown (tier 2)
      O5: 1 obligation(s): unknown (tier -)
      note: contract assumed value: durations.x=100
      note: contract assumed value: durations.measure=1000
      note: contract assumed value: durations.h=50
      note: contract assumed value: timeline.commit_lead=200
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 3]
    

Bound `in2cpu` at 300 ns. O1 is now proved (tier 1, margin 300 ns), but the verdict is still UNKNOWN: the symbolic encoding of O5 is not built, and this build says so instead of dropping the obligation.

```python
code, out = _show.run("check", prog, "--contract", "artiq", *L, "--assume", "in2cpu=0:300")
assert code == 3 and "O1: 1 obligation(s): proved" in out and "Tier 2 does not encode Events (O5)" in out
a3 = (code, out)
```

    UNKNOWN  (contract artiq_rtio, policy exp, sha256 8cbc342b1f07)
      why: O5 at node 7: Tier 2 does not encode Events (O5) yet
      assumptions (weakest class: vendor):
        in2cpu: [0 ns, 300 ns]  vendor: --assume in2cpu=0:300
      O1: 1 obligation(s): proved (tier 1, margin 300 ns)
      O5: 1 obligation(s): unknown (tier -)
      note: contract assumed value: durations.x=100
      note: contract assumed value: durations.measure=1000
      note: contract assumed value: durations.h=50
      note: contract assumed value: timeline.commit_lead=200
      note: contract assumed value: in2cpu=0:300
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 3]
    

Allow `in2cpu` up to 2000 ns: the result is now REFUTED for O1, even though O5 is still unknown (REFUTED outranks UNKNOWN).

```python
code, out = _show.run("check", prog, "--contract", "artiq", *L, "--assume", "in2cpu=0:2000")
assert code == 1 and out.startswith("REFUTED") and "O5: 1 obligation(s): unknown" in out
a4 = (code, out)
```

    REFUTED  (contract artiq_rtio, policy exp, sha256 16926af85185)
      why: O1 at node 7: RTIO event must be committed at least commit_lead before its timestamp
      O1 failed at E:/PROJECTS/Qtiming/benchmarks/families/artiq/artiq_reset_fb.qasm:12 (tier 2)
      assumptions (weakest class: vendor):
        in2cpu: [0 ns, 2000 ns]  vendor: --assume in2cpu=0:2000
      O1: 1 obligation(s): refuted (tier 2)
      O5: 1 obligation(s): unknown (tier -)
      note: contract assumed value: durations.x=100
      note: contract assumed value: durations.measure=1000
      note: contract assumed value: durations.h=50
      note: contract assumed value: timeline.commit_lead=200
      note: contract assumed value: in2cpu=0:2000
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 1]
    

## All results side by side

```python
card([
    ("plain.qasm, ibm_heron", *proved),
    ("tp_basic, ibm_heron", *under),
    ("tp_basic, ibm_heron, --strict-proved", *strict),
    ("tp_sync, ibm_heron", *refuted),
    ("tp_sync, ibm_heron, --no-tier2", *unknown),
    ("artiq_reset_fb, no commit_lead", *a1),
    ("artiq_reset_fb, in2cpu unbounded", *a2),
    ("artiq_reset_fb, in2cpu 0:300", *a3),
    ("artiq_reset_fb, in2cpu 0:2000", *a4),
])
```

<style>.qv{display:grid;grid-template-columns:repeat(auto-fit,minmax(15rem,1fr));gap:.6rem}.qv div{border:1px solid #8886;border-left:6px solid var(--c);border-radius:6px;padding:.5rem .7rem}.qv b{font-size:1.05em}.qv small{display:block;opacity:.8}</style><div class="qv"><div style="--c:#1a7f37"><b>PROVED</b> (exit 0)<small>plain.qasm, ibm_heron</small></div><div style="--c:#9a6700"><b>PROVED-UNDER</b> (exit 0)<small>tp_basic, ibm_heron</small></div><div style="--c:#9a6700"><b>PROVED-UNDER</b> (exit 1)<small>tp_basic, ibm_heron, --strict-proved</small></div><div style="--c:#cf222e"><b>REFUTED</b> (exit 1)<small>tp_sync, ibm_heron</small></div><div style="--c:#6e7781"><b>UNKNOWN</b> (exit 3)<small>tp_sync, ibm_heron, --no-tier2</small></div><div style="--c:#6e7781"><b>UNKNOWN</b> (exit 3)<small>artiq_reset_fb, no commit_lead</small></div><div style="--c:#6e7781"><b>UNKNOWN</b> (exit 3)<small>artiq_reset_fb, in2cpu unbounded</small></div><div style="--c:#6e7781"><b>UNKNOWN</b> (exit 3)<small>artiq_reset_fb, in2cpu 0:300</small></div><div style="--c:#cf222e"><b>REFUTED</b> (exit 1)<small>artiq_reset_fb, in2cpu 0:2000</small></div></div>

## What just happened
- The verdict is the weakest obligation result: `REFUTED` > `UNKNOWN` > `PROVED-UNDER` > `PROVED`.
- `PROVED` needs no latency-dependent obligation; `PROVED-UNDER` lists every assumption it used, with its evidence class.
- `--strict-proved` only changes the exit code of `PROVED-UNDER` (0 to 1).
- `UNKNOWN` means a missing number, an unbounded latency, a disabled tier, or an unbuilt encoding. It is never silently turned into a pass.
- All ARTIQ results here depend on illustrative `--assume` numbers, not published ARTIQ values.

Next: [Policies](03-policies.md).
