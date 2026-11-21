# %% [markdown]
# # Under the hood
#
# **Question:** what does `check` actually build and run, and what do the knobs `--no-tier1`, `--no-tier2`, `--timeout` and `--no-window` change?
#
# We use a distance-3 repetition code (`qec/rep_d3_r3` and `rep_d3_r100`, three and a hundred syndrome rounds) on IBM Heron. Reference: [Command reference](../cli.md), [Obligations](../obligations.md), [Windowing (T4)](../theory/T4-windowing.md).

# %%
import json, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent))
import _show

R3 = _show.FAMILIES / "qec/rep_d3_r3.qasm"
R100 = _show.FAMILIES / "qec/rep_d3_r100.qasm"

# %% [markdown]
# ## The program
# One syndrome round: entangle, measure two ancillas, apply a correction chosen by the outcomes, reset. `rep_d3_r100` is the same text with `for int i in [0:99]`.

# %%
_show.source("qec/rep_d3_r3.qasm")

# %% [markdown]
# ## 1. The event graph
# `explain` shows the pipeline's size summary: nodes are timed events (start, end, valid, join...), edges are ordering constraints with latency intervals, obligations are the claims to discharge.

# %%
code, out = _show.run("explain", R3, "--contract", "ibm_heron")
assert code == 0 and "115 nodes" in out and "44 obligations" in out

# %% [markdown]
# `--graph dot` prints the whole graph in Graphviz DOT. The three-round graph is too big to read, so we draw the **one-round** program (`rep_d3_r1`):

# %%
code, dot = _show.run("explain", _show.FAMILIES / "qec/rep_d3_r1.qasm", "--contract", "ibm_heron", "--graph", "dot", show=False)
assert code == 0 and dot.startswith("digraph lteg")
print(dot.count("->"), "edges")
_show.dot(dot, height=500)

# %% [markdown]
# ## 2. Solver tiers
# Obligations go through up to three solvers: **Tier 0** exact evaluation, **Tier 1** interval abstraction (can only prove), **Tier 2** the Z3 SMT solver (proves or refutes). We use `--policy eq` (every branch must take equal time), which this program satisfies under the vendor latency assumption, and count which tier closed each obligation.

# %%
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

# %%
assert rows["default"][1] == "PROVED-UNDER" and rows["default"][2]["tier 1"] > 0
assert rows["--no-tier1"][1] == "PROVED-UNDER" and rows["--no-tier1"][2]["tier 1"] == 0 and rows["--no-tier1"][2]["tier 2"] > 0
assert rows["--no-tier2"][1] == "PROVED-UNDER"
assert rows["--no-tier1 --no-tier2"][0] == 3 and rows["--no-tier1 --no-tier2"][1] == "UNKNOWN"

# %% [markdown]
# The tier mix as a bar (hand-made SVG; one bar per run):

# %%
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

# %% [markdown]
# Turning Tier 1 off pushes its obligations to Z3: same verdict, different workhorse. Turning Tier 2 off is only safe when Tier 1 is enough; where it is not, the obligation is UNKNOWN, never guessed. Turning both off leaves just exact Tier 0, so the verdict is UNKNOWN (exit 3).
#
# Tier 2 is also what produces counterexamples. Under the default `sync` policy the same program is refuted, and without Tier 2 that refutation becomes UNKNOWN:

# %%
for name, o in [("default", ()), ("--no-tier2", ("--no-tier2",))]:
    code, verdict, c = tiers(R3, *o, policy="sync")
    print(f"sync {name:12} exit {code}  {verdict:8} {dict(sorted(c.items()))}")
    if name == "default":
        assert (code, verdict) == (1, "REFUTED")
    else:
        assert (code, verdict) == (3, "UNKNOWN")

# %% [markdown]
# ## 3. `--timeout`
# `--timeout S` bounds each SMT query (default 10 s). A query that runs out of time is UNKNOWN, not a guess. With an absurdly small budget:

# %%
code, verdict, c = tiers(R3, "--no-tier1", "--timeout", "0.001")
assert (code, verdict) == (3, "UNKNOWN") and c["unknown"] > 0  # exact split depends on machine speed, so not printed
print(code, verdict)

# %% [markdown]
# ## 4. Windowing
# Unrolling a hundred rounds would build a graph about thirty times the size of the three-round one. For IBM, qtiming instead checks **one iteration window**, provided the loop is bracketed by full joins (the cut rules of [T4](../theory/T4-windowing.md)). The three-round loop is small enough to unroll; the hundred-round loop exceeds the unroll limit of 64 and is windowed.

# %%
code, out = _show.run("check", R100, "--contract", "ibm_heron", "--policy", "eq")
assert code == 0 and out.startswith("PROVED-UNDER") and "window: loop of 100 iterations" in out

# %% [markdown]
# Same verdict as the 3-round program, with 20 O4 obligations instead of 62. Now forbid windowing:

# %%
code, out = _show.run("check", R100, "--contract", "ibm_heron", "--policy", "eq", "--no-window")
assert code == 2 and "E-ELAB-LOOP-LIMIT" in out

# %% [markdown]
# Without windowing a long loop is not silently truncated: it fails with a usage error (exit 2). Windowing is only sound for IBM; other personalities refuse to window and report UNKNOWN (`E-GRAPH-CUT`).
#
# Note `explain` does not window: asking it for the 100-round graph gives the same error.

# %%
code, out = _show.run("explain", R100, "--contract", "ibm_heron")
assert code == 2 and "E-ELAB-LOOP-LIMIT" in out

# %% [markdown]
# ## What just happened
# - The event graph is the shared intermediate form; `explain --graph dot` exposes it.
# - Obligations are discharged by the cheapest solver that can: exact, interval, then SMT. Interval only proves; only exact and SMT refute.
# - Disabling a tier trades speed for UNKNOWNs, never for wrong answers.
# - Windowing lets `rep_d3_r100` be checked in about the cost of one round, under the IBM cut rules.
#
# Next: [Reference: CLI](../cli.md).
