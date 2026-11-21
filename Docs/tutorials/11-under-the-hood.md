# Under the hood

**Question:** what does `check` actually build and run, and what do the knobs `--no-tier1`, `--no-tier2`, `--timeout` and `--no-window` change?

We use a distance-3 repetition code (`qec/rep_d3_r3` and `rep_d3_r100`, three and a hundred syndrome rounds) on IBM Heron. Reference: [Command reference](../cli.md), [Obligations](../obligations.md), [Windowing (T4)](../theory/T4-windowing.md).

```python
import json, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent))
import _show

R3 = _show.FAMILIES / "qec/rep_d3_r3.qasm"
R100 = _show.FAMILIES / "qec/rep_d3_r100.qasm"
```

## The program
One syndrome round: entangle, measure two ancillas, apply a correction chosen by the outcomes, reset. `rep_d3_r100` is the same text with `for int i in [0:99]`.

```python
_show.source("qec/rep_d3_r3.qasm")
```

    OPENQASM 3.0;
    // rep_d3_r3: distance-3 repetition code, 3 syndrome round(s), toy lookup decoder
    qubit[5] q;
    bit[2] c;
    
    for int i in [0:2] {
    barrier q;
    cx q[0], q[3];
    cx q[1], q[3];
    cx q[1], q[4];
    cx q[2], q[4];
    c[0] = measure q[3];
    c[1] = measure q[4];
    if (c[0] && !c[1]) {
        x q[0];
    }
    if (c[0] && c[1]) {
        x q[1];
    }
    if (!c[0] && c[1]) {
        x q[2];
    }
    reset q[3];
    reset q[4];
    barrier q;
    }
    

## 1. The event graph
`explain` shows the pipeline's size summary: nodes are timed events (start, end, valid, join...), edges are ordering constraints with latency intervals, obligations are the claims to discharge.

```python
code, out = _show.run("explain", R3, "--contract", "ibm_heron")
assert code == 0 and "115 nodes" in out and "44 obligations" in out
```

    ibm_heron (ibm): 115 nodes, 168 edges, 6 latency variables, 44 obligations
      facts[block]: 9
      facts[blockend]: 9
      facts[eqbar]: 6
      facts[gap]: 45
      facts[ready]: 9
    [exit 0]
    

`--graph dot` prints the whole graph in Graphviz DOT. The three-round graph is too big to read, so we draw the **one-round** program (`rep_d3_r1`):

```python
code, dot = _show.run("explain", _show.FAMILIES / "qec/rep_d3_r1.qasm", "--contract", "ibm_heron", "--graph", "dot", show=False)
assert code == 0 and dot.startswith("digraph lteg")
print(dot.count("->"), "edges")
_show.dot(dot, height=500)
```

    46 edges
    

<div class="qt-dot" style="min-height:500px"><pre class="qt-dot-src" hidden>digraph lteg {
  rankdir=LR; node [shape=box, fontsize=10];
  n0 [label=&quot;origin/origin@-1&quot;];
  n1 [label=&quot;start/start@1&quot;];
  n2 [label=&quot;end/end@1&quot;];
  n3 [label=&quot;start/start@2&quot;];
  n4 [label=&quot;end/end@2&quot;];
  n5 [label=&quot;start/start@3&quot;];
  n6 [label=&quot;end/end@3&quot;];
  n7 [label=&quot;start/start@4&quot;];
  n8 [label=&quot;end/end@4&quot;];
  n9 [label=&quot;start/start@5&quot;];
  n10 [label=&quot;end/end@5&quot;];
  n11 [label=&quot;valid/valid@5&quot;];
  n12 [label=&quot;start/start@6&quot;];
  n13 [label=&quot;end/end@6&quot;];
  n14 [label=&quot;valid/valid@6&quot;];
  n15 [label=&quot;valid/cvalid@7&quot;];
  n16 [label=&quot;join/bready@7&quot;];
  n17 [label=&quot;start/bstart@7&quot;];
  n18 [label=&quot;start/start@9/n[cond@n7]&quot;];
  n19 [label=&quot;end/end@9/n[cond@n7]&quot;];
  n20 [label=&quot;end/bend@7&quot;];
  n21 [label=&quot;valid/cvalid@10&quot;];
  n22 [label=&quot;join/bready@10&quot;];
  n23 [label=&quot;start/bstart@10&quot;];
  n24 [label=&quot;start/start@12/n[cond@n10]&quot;];
  n25 [label=&quot;end/end@12/n[cond@n10]&quot;];
  n26 [label=&quot;end/bend@10&quot;];
  n27 [label=&quot;valid/cvalid@13&quot;];
  n28 [label=&quot;join/bready@13&quot;];
  n29 [label=&quot;start/bstart@13&quot;];
  n30 [label=&quot;start/start@15/n[cond@n13]&quot;];
  n31 [label=&quot;end/end@15/n[cond@n13]&quot;];
  n32 [label=&quot;end/bend@13&quot;];
  n33 [label=&quot;start/start@16&quot;];
  n34 [label=&quot;end/end@16&quot;];
  n35 [label=&quot;start/start@17&quot;];
  n36 [label=&quot;end/end@17&quot;];
  n0 -&gt; n1 [label=&quot;0&quot;, fontsize=9];
  n0 -&gt; n1 [label=&quot;0&quot;, fontsize=9];
  n1 -&gt; n2 [label=&quot;20&quot;, fontsize=9];
  n0 -&gt; n3 [label=&quot;0&quot;, fontsize=9];
  n2 -&gt; n3 [label=&quot;0&quot;, fontsize=9];
  n3 -&gt; n4 [label=&quot;20&quot;, fontsize=9];
  n4 -&gt; n5 [label=&quot;0&quot;, fontsize=9];
  n0 -&gt; n5 [label=&quot;0&quot;, fontsize=9];
  n5 -&gt; n6 [label=&quot;20&quot;, fontsize=9];
  n0 -&gt; n7 [label=&quot;0&quot;, fontsize=9];
  n6 -&gt; n7 [label=&quot;0&quot;, fontsize=9];
  n7 -&gt; n8 [label=&quot;20&quot;, fontsize=9];
  n4 -&gt; n9 [label=&quot;0&quot;, fontsize=9];
  n9 -&gt; n10 [label=&quot;545&quot;, fontsize=9];
  n10 -&gt; n11 [label=&quot;ff.default in [0, 150]&quot;, fontsize=9, style=dashed];
  n8 -&gt; n12 [label=&quot;0&quot;, fontsize=9];
  n12 -&gt; n13 [label=&quot;545&quot;, fontsize=9];
  n13 -&gt; n14 [label=&quot;ff.default in [0, 150]&quot;, fontsize=9, style=dashed];
  n11 -&gt; n15 [label=&quot;0&quot;, fontsize=9];
  n14 -&gt; n15 [label=&quot;0&quot;, fontsize=9];
  n2 -&gt; n16 [label=&quot;0&quot;, fontsize=9];
  n16 -&gt; n17 [label=&quot;0&quot;, fontsize=9];
  n15 -&gt; n17 [label=&quot;0&quot;, fontsize=9];
  n17 -&gt; n18 [label=&quot;0&quot;, fontsize=9];
  n18 -&gt; n19 [label=&quot;8&quot;, fontsize=9];
  n17 -&gt; n20 [label=&quot;8&quot;, fontsize=9];
  n11 -&gt; n21 [label=&quot;0&quot;, fontsize=9];
  n14 -&gt; n21 [label=&quot;0&quot;, fontsize=9];
  n6 -&gt; n22 [label=&quot;0&quot;, fontsize=9];
  n22 -&gt; n23 [label=&quot;0&quot;, fontsize=9];
  n21 -&gt; n23 [label=&quot;0&quot;, fontsize=9];
  n23 -&gt; n24 [label=&quot;0&quot;, fontsize=9];
  n24 -&gt; n25 [label=&quot;8&quot;, fontsize=9];
  n23 -&gt; n26 [label=&quot;8&quot;, fontsize=9];
  n11 -&gt; n27 [label=&quot;0&quot;, fontsize=9];
  n14 -&gt; n27 [label=&quot;0&quot;, fontsize=9];
  n8 -&gt; n28 [label=&quot;0&quot;, fontsize=9];
  n28 -&gt; n29 [label=&quot;0&quot;, fontsize=9];
  n27 -&gt; n29 [label=&quot;0&quot;, fontsize=9];
  n29 -&gt; n30 [label=&quot;0&quot;, fontsize=9];
  n30 -&gt; n31 [label=&quot;8&quot;, fontsize=9];
  n29 -&gt; n32 [label=&quot;8&quot;, fontsize=9];
  n10 -&gt; n33 [label=&quot;0&quot;, fontsize=9];
  n33 -&gt; n34 [label=&quot;250&quot;, fontsize=9];
  n13 -&gt; n35 [label=&quot;0&quot;, fontsize=9];
  n35 -&gt; n36 [label=&quot;250&quot;, fontsize=9];
}
</pre><script src="https://cdn.jsdelivr.net/npm/@viz-js/viz@3.2.4/lib/viz-standalone.js"></script><script>(async()=>{for(const e of document.querySelectorAll('.qt-dot-src:not([data-done])')){e.dataset.done=1;const v=await Viz.instance();e.parentElement.appendChild(v.renderSVGElement(e.textContent));}})()</script></div>

## 2. Solver tiers
Obligations go through up to three solvers: **Tier 0** exact evaluation, **Tier 1** interval abstraction (can only prove), **Tier 2** the Z3 SMT solver (proves or refutes). We use `--policy eq` (every branch must take equal time), which this program satisfies under the vendor latency assumption, and count which tier closed each obligation.

```python
def tiers(prog, *opts, policy="eq"):
    code, out = _show.run("check", prog, "--contract", "ibm_heron", "--policy", policy,
                          "--format", "json", *opts, show=False)
    d = json.loads(out)
    return code, d["verdict"], Counter(
        "unknown" if o["result"] == "unknown" else f"tier {o['tier']}" for o in d["obligations"])

cases = [("default", ()), ("--no-tier1", ("--no-tier1",)), ("--no-tier2", ("--no-tier2",)),
         ("--no-tier1 --no-tier2", ("--no-tier1", "--no-tier2"))]
rows = {name: tiers(R3, *o) for name, o in cases}
for name, (code, verdict, c) in rows.items():
    print(f"{name:24} exit {code}  {verdict:13} {dict(sorted(c.items()))}")
```

    default                  exit 0  PROVED-UNDER  {'tier 0': 14, 'tier 1': 66}
    --no-tier1               exit 0  PROVED-UNDER  {'tier 0': 14, 'tier 2': 66}
    --no-tier2               exit 0  PROVED-UNDER  {'tier 0': 14, 'tier 1': 66}
    --no-tier1 --no-tier2    exit 3  UNKNOWN       {'tier 0': 14, 'unknown': 66}
    

```python
assert rows["default"][1] == "PROVED-UNDER" and rows["default"][2]["tier 1"] > 0
assert rows["--no-tier1"][1] == "PROVED-UNDER" and rows["--no-tier1"][2]["tier 1"] == 0 and rows["--no-tier1"][2]["tier 2"] > 0
assert rows["--no-tier2"][1] == "PROVED-UNDER"
assert rows["--no-tier1 --no-tier2"][0] == 3 and rows["--no-tier1 --no-tier2"][1] == "UNKNOWN"
```

The tier mix as a bar (hand-made SVG; one bar per run):

```python
from IPython.display import HTML, display
COL = {"tier 0": "#4c78a8", "tier 1": "#59a14f", "tier 2": "#f28e2b", "unknown": "#b0b0b0"}
W, y, parts = 520, 0, []
for name, (_, _, c) in rows.items():
    tot, x = sum(c.values()), 150
    parts.append(f'<text x="0" y="{y+16}" font-size="12" fill="currentColor">{name}</text>')
    for k in COL:
        w = W * c.get(k, 0) / tot
        if w:
            parts.append(f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="22" fill="{COL[k]}"><title>{k}: {c[k]}</title></rect>')
            if w > 24:
                parts.append(f'<text x="{x+w/2:.1f}" y="{y+16}" font-size="11" text-anchor="middle" fill="#fff">{c[k]}</text>')
            x += w
    y += 32
leg = "".join(f'<rect x="{150+i*90}" y="{y+6}" width="12" height="12" fill="{v}"/><text x="{150+i*90+16}" y="{y+16}" font-size="11" fill="currentColor">{k}</text>' for i, (k, v) in enumerate(COL.items()))
display(HTML(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W+160} {y+28}" width="{W+160}" role="img" aria-label="Obligations closed per solver tier">{"".join(parts)}{leg}</svg>'))
```

<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 680 156" width="680" role="img" aria-label="Obligations closed per solver tier"><text x="0" y="16" font-size="12" fill="currentColor">default</text><rect x="150.0" y="0" width="91.0" height="22" fill="#4c78a8"><title>tier 0: 14</title></rect><text x="195.5" y="16" font-size="11" text-anchor="middle" fill="#fff">14</text><rect x="241.0" y="0" width="429.0" height="22" fill="#59a14f"><title>tier 1: 66</title></rect><text x="455.5" y="16" font-size="11" text-anchor="middle" fill="#fff">66</text><text x="0" y="48" font-size="12" fill="currentColor">--no-tier1</text><rect x="150.0" y="32" width="91.0" height="22" fill="#4c78a8"><title>tier 0: 14</title></rect><text x="195.5" y="48" font-size="11" text-anchor="middle" fill="#fff">14</text><rect x="241.0" y="32" width="429.0" height="22" fill="#f28e2b"><title>tier 2: 66</title></rect><text x="455.5" y="48" font-size="11" text-anchor="middle" fill="#fff">66</text><text x="0" y="80" font-size="12" fill="currentColor">--no-tier2</text><rect x="150.0" y="64" width="91.0" height="22" fill="#4c78a8"><title>tier 0: 14</title></rect><text x="195.5" y="80" font-size="11" text-anchor="middle" fill="#fff">14</text><rect x="241.0" y="64" width="429.0" height="22" fill="#59a14f"><title>tier 1: 66</title></rect><text x="455.5" y="80" font-size="11" text-anchor="middle" fill="#fff">66</text><text x="0" y="112" font-size="12" fill="currentColor">--no-tier1 --no-tier2</text><rect x="150.0" y="96" width="91.0" height="22" fill="#4c78a8"><title>tier 0: 14</title></rect><text x="195.5" y="112" font-size="11" text-anchor="middle" fill="#fff">14</text><rect x="241.0" y="96" width="429.0" height="22" fill="#b0b0b0"><title>unknown: 66</title></rect><text x="455.5" y="112" font-size="11" text-anchor="middle" fill="#fff">66</text><rect x="150" y="134" width="12" height="12" fill="#4c78a8"/><text x="166" y="144" font-size="11" fill="currentColor">tier 0</text><rect x="240" y="134" width="12" height="12" fill="#59a14f"/><text x="256" y="144" font-size="11" fill="currentColor">tier 1</text><rect x="330" y="134" width="12" height="12" fill="#f28e2b"/><text x="346" y="144" font-size="11" fill="currentColor">tier 2</text><rect x="420" y="134" width="12" height="12" fill="#b0b0b0"/><text x="436" y="144" font-size="11" fill="currentColor">unknown</text></svg>

Turning Tier 1 off pushes its obligations to Z3: same verdict, different workhorse. Turning Tier 2 off is only safe when Tier 1 is enough; where it is not, the obligation is UNKNOWN, never guessed. Turning both off leaves just exact Tier 0, so the verdict is UNKNOWN (exit 3).

Tier 2 is also what produces counterexamples. Under the default `sync` policy the same program is refuted, and without Tier 2 that refutation becomes UNKNOWN:

```python
for name, o in [("default", ()), ("--no-tier2", ("--no-tier2",))]:
    code, verdict, c = tiers(R3, *o, policy="sync")
    print(f"sync {name:12} exit {code}  {verdict:8} {dict(sorted(c.items()))}")
    if name == "default":
        assert (code, verdict) == (1, "REFUTED")
    else:
        assert (code, verdict) == (3, "UNKNOWN")
```

    sync default      exit 1  REFUTED  {'tier 0': 11, 'tier 1': 18, 'tier 2': 15}
    

    sync --no-tier2   exit 3  UNKNOWN  {'tier 0': 11, 'tier 1': 18, 'unknown': 15}
    

## 3. `--timeout`
`--timeout S` bounds each SMT query (default 10 s). A query that runs out of time is UNKNOWN, not a guess. With an absurdly small budget:

```python
code, verdict, c = tiers(R3, "--no-tier1", "--timeout", "0.001")
assert (code, verdict) == (3, "UNKNOWN") and c["unknown"] > 0  # exact split depends on machine speed, so not printed
print(code, verdict)
```

    3 UNKNOWN
    

## 4. Windowing
Unrolling a hundred rounds would build a graph about thirty times the size of the three-round one. For IBM, qtiming instead checks **one iteration window**, provided the loop is bracketed by full joins (the cut rules of [T4](../theory/T4-windowing.md)). The three-round loop is small enough to unroll; the hundred-round loop exceeds the unroll limit of 64 and is windowed.

```python
code, out = _show.run("check", R100, "--contract", "ibm_heron", "--policy", "eq")
assert code == 0 and out.startswith("PROVED-UNDER") and "window: loop of 100 iterations" in out
```

    PROVED-UNDER  (contract ibm_heron, policy eq, sha256 9cf4d27a06ae)
      assumptions (weakest class: vendor):
        ff.default: [0 ns, 600 ns]  vendor: IBM blog, 2025-11-19 (feedforward about 600 ns); vendor claim, not a certified bound
      O2b: 3 obligation(s): proved (tier 1, margin 0 ns)
      O4: 20 obligation(s): proved (tier 0, margin 0 ns); proved (tier 1, margin 0 ns)
      O7: 3 obligation(s): proved (tier 1, margin 0 ns)
      note: window: loop of 100 iterations summarised by one iteration window (cut rules 1, 3, 4, 5 hold)
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 0]
    

Same verdict as the 3-round program, with 20 O4 obligations instead of 62. Now forbid windowing:

```python
code, out = _show.run("check", R100, "--contract", "ibm_heron", "--policy", "eq", "--no-window")
assert code == 2 and "E-ELAB-LOOP-LIMIT" in out
```

    error: E-ELAB-LOOP-LIMIT: for loop of 100 > unroll limit 64
      hint: raise the unroll limit, or omit --no-window (IBM windowing)
    [exit 2]
    

Without windowing a long loop is not silently truncated: it fails with a usage error (exit 2). Windowing is only sound for IBM; other personalities refuse to window and report UNKNOWN (`E-GRAPH-CUT`).

Note `explain` does not window: asking it for the 100-round graph gives the same error.

```python
code, out = _show.run("explain", R100, "--contract", "ibm_heron")
assert code == 2 and "E-ELAB-LOOP-LIMIT" in out
```

    error: E-ELAB-LOOP-LIMIT: for loop of 100 > unroll limit 64
      hint: raise the unroll limit, or omit --no-window (IBM windowing)
    [exit 2]
    

## What just happened
- The event graph is the shared intermediate form; `explain --graph dot` exposes it.
- Obligations are discharged by the cheapest solver that can: exact, interval, then SMT. Interval only proves; only exact and SMT refute.
- Disabling a tier trades speed for UNKNOWNs, never for wrong answers.
- Windowing lets `rep_d3_r100` be checked in about the cost of one round, under the IBM cut rules.

Next: [Reference: CLI](../cli.md).
