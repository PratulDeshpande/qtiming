# %% [markdown]
# # Real workloads
#
# **Question:** qtiming has been shown on one program at a time. What does it say about a *whole suite* of programs, on every hardware stack it knows about?
#
# The repository ships 56 benchmark programs in 8 families (`benchmarks/families/`) and a harness, `qtiming-bench`, that runs one verdict per **cell** = (program, contract, policy). Reference: [Command reference](../cli.md), `benchmarks/README.md`.
#
# **Honest scope.** The programs are toy circuits with the *timing shape* of each protocol, written by the qtiming authors. They are not validated physical protocols, and a verdict here says nothing about a real device.
#
# **Runtime.** The full run (672 cells) takes about a minute and a half. It runs in a temporary directory, so nothing is written into the repository.

# %%
import collections, contextlib, io, json, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent))
import _show
from IPython.display import HTML, display
from qtiming.bench import main as bench

ROOT = _show.ROOT
progs = sorted(_show.FAMILIES.rglob("*.qasm"))
fams = collections.Counter(p.parent.name for p in progs)
print(len(progs), "programs")
for f, n in sorted(fams.items()):
    print(f"  {f:16s} {n}")
assert len(progs) == 56 and len(fams) == 8

# %% [markdown]
# ## One program from the suite
# An active-reset program: measure a qubit and flip it back if it read 1.

# %%
_show.source("active_reset/reset_basic.qasm")

# %% [markdown]
# ## Run the whole suite
# `--contracts all` means the four shipped stacks (`artiq`, `ibm_heron`, `q1`, `qua`). `--policies eq,sync,exp` tries each unannotated branch under each policy (a program that carries its own annotation ignores this flag). Verdicts come from the same solvers as `qtiming check`.

# %%
tmp = tempfile.TemporaryDirectory()
res = Path(tmp.name) / "run"
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc = bench(["run", "--suite", str(_show.FAMILIES), "--contracts", "all",
                "--policies", "eq,sync,exp", "--repeat", "1", "--out", str(res)])
print(buf.getvalue().strip().splitlines()[-1])
rows = [json.loads(l) for l in (res / "results.jsonl").read_text(encoding="utf-8").splitlines()]
assert rc == 0 and len(rows) == 56 * 4 * 3

# %% [markdown]
# ## The heat-map: family x stack
# Each cell stacks the verdicts of every (program, policy) pair in that family on that stack. Green is `PROVED-UNDER`, red is a timing `REFUTED` (a counterexample exists), orange is a `REFUTED` that is only a **policy refusal** (see below), grey is `unsupported`. The number inside is the cell count.

# %%
def kind(r):
    if r["status"] == "REFUTED" and r["reasons"][0].startswith("policy-incompatible"):
        return "policy"
    return r["status"]

COL = {"PROVED": "#2e7d32", "PROVED-UNDER": "#388e3c", "REFUTED": "#c62828", "policy": "#ef6c00",
       "UNKNOWN": "#f9a825", "unsupported": "#757575"}
LABEL = {"PROVED": "PROVED", "PROVED-UNDER": "PROVED-UNDER", "REFUTED": "REFUTED (timing)",
         "policy": "REFUTED (policy refused)", "UNKNOWN": "UNKNOWN", "unsupported": "unsupported"}
stacks = sorted({r["contract"] for r in rows})
famnames = sorted(fams)
cnt = collections.Counter((r["family"], r["contract"], kind(r)) for r in rows)

def cell(f, s):
    parts = []
    for k in COL:
        n = cnt[(f, s, k)]
        if n:
            parts.append(f'<div title="{LABEL[k]}: {n}" style="flex:{n};background:{COL[k]};color:#fff;'
                         f'text-align:center;padding:6px 0;font-size:12px;min-width:22px">{n}</div>')
    return ('<div style="display:flex;border-radius:4px;overflow:hidden;min-width:120px">'
            + "".join(parts) + "</div>")

th = "padding:6px 10px;text-align:left"
html = ['<div style="overflow-x:auto"><table style="border-collapse:separate;border-spacing:4px"><tr>',
        f'<th style="{th}">family</th>'] + [f'<th style="{th}">{s}</th>' for s in stacks] + ["</tr>"]
for f in famnames:
    html.append(f'<tr><td style="{th}"><code>{f}</code></td>')
    html += [f"<td>{cell(f, s)}</td>" for s in stacks] + ["</tr>"]
html.append("</table></div><p style='font-size:12px'>" + " &nbsp; ".join(
    f'<span style="background:{COL[k]};color:#fff;padding:2px 8px;border-radius:3px">{LABEL[k]}</span>'
    for k in COL if any(v for (f, s, kk), v in cnt.items() if kk == k)) + "</p>")
display(HTML("".join(html)))

tot = collections.Counter(kind(r) for r in rows)
print(dict(sorted(tot.items())))
# every cell on the three non-IBM stacks is `unsupported`; only ibm_heron produces verdicts
assert all(r["status"] == "unsupported" for r in rows if r["contract"] != "ibm_heron")
assert sum(1 for r in rows if r["contract"] == "ibm_heron" and r["status"] != "unsupported") > 0
assert not any(r["status"] == "PROVED" for r in rows)

# %% [markdown]
# ## Reading the picture
# - **Three of four columns are grey, and that is the honest answer.** Only the IBM contract publishes gate durations (from an *unofficial* snapshot). On `artiq`, `q1` and `qua` the contracts leave gate durations absent, so qtiming refuses to guess and reports `unsupported` instead of inventing numbers. The reasons, counted:

# %%
for (c, why), n in sorted(collections.Counter(
        (r["contract"], r["reasons"][0].split("'")[-2])
        for r in rows if r["status"] == "unsupported" and r["reasons"][0].startswith("E-CT-MISSING")).items()):
    print(f"{n:4d}  {c:6s} has no duration for gate '{why}'")
assert all(r["reasons"][0].startswith("E-CT-MISSING") for r in rows
           if r["status"] == "unsupported" and r["contract"] != "ibm_heron")

# %% [markdown]
# - **No cell is `PROVED`.** Every IBM verdict rests on the feed-forward latency, which is a vendor claim, so the best outcome is `PROVED-UNDER`. The harness counts that dependence:

# %%
ib = [r for r in rows if r["contract"] == "ibm_heron" and r["status"] != "unsupported"]
print("IBM cells with a verdict:", len(ib), "| resting on a non-certified number:", sum(r["uncertified"] > 0 for r in ib))
assert all(r["status"] != "PROVED" for r in ib)

# %% [markdown]
# - **Orange is not a timing bug.** Any program run under the experiment-timeline (`exp`) policy, including the whole `artiq` family, is refused on IBM: a restricted backend cannot honour it. The result is `REFUTED` with *no obligations checked*, only a refusal:

# %%
r0 = next(r for r in rows if r["program"] == "artiq_burst" and r["contract"] == "ibm_heron" and r["policy"] == "eq")
print(r0["status"], r0["obligations"], "obligations |", r0["reasons"][0])
assert kind(r0) == "policy" and r0["obligations"] == 0

# %% [markdown]
# - **Some cells are structurally unsupported on IBM.** `while`-loop RUS programs need nested ifs and measurement inside a branch, which IBM does not allow:

# %%
loops = sorted({r["program"] for r in rows if r["contract"] == "ibm_heron" and r["status"] == "unsupported"})
print(loops)
assert loops and all(p.startswith("rus_while") for p in loops)

# %% [markdown]
# ## Per-stack tables from `qtiming-bench report`
# `report` derives its tables from the same `results.jsonl`; nothing is typed in by hand.

# %%
tab = Path(tmp.name) / "tables"
with contextlib.redirect_stdout(io.StringIO()):
    assert bench(["report", str(res), "--tables", str(tab)]) == 0
for t in ("verdicts_per_contract", "headline_provenance"):
    print((tab / f"{t}.md").read_text(encoding="utf-8").strip().replace("\r", "") + "\n")

# %% [markdown]
# ## One real counterexample
# A genuine timing `REFUTED` from the heat-map, `reset_within_tight`: the correction has a deadline tighter than the vendor-claimed feed-forward latency allows.

# %%
code, out = _show.run("check", _show.FAMILIES / "active_reset/reset_within_tight.qasm", "--contract", "ibm_heron")
assert code == 1 and out.startswith("REFUTED")

# %% [markdown]
# ## Is the suite's answer "right"?
# `benchmarks/expected.json` lets `qtiming-bench check` flag any cell whose verdict *changed* since the file was generated:

# %%
with contextlib.redirect_stdout(io.StringIO()) as o:
    rc = bench(["check", str(res), "--golden", str(ROOT / "benchmarks/expected.json")])
print(o.getvalue().strip())
assert rc == 0

# %% [markdown]
# That file is a **regression snapshot of the checker itself**, not ground truth: matching it says the verdicts did not drift, not that they are correct. Independent evidence comes from the separately-written reference executor, the differential and property tests, and `qtiming-bench truth` / `diff` (see [Counterexamples](07-counterexamples.md)).

# %% [markdown]
# ## What just happened
# - `qtiming-bench run` produced 672 verdicts (56 programs x 4 stacks x 3 policies) and `report` tabulated them.
# - Only IBM yields verdicts, all conditional on a vendor-claimed latency; the other three stacks are `unsupported` because their contracts omit gate durations, and qtiming does not fill gaps with guesses.
# - A red or orange cell can be a policy refusal rather than a timing violation; read the reason, not just the colour.
#
# **Not built yet** (so absent from the map): repeat-until-success wiring in `check` (the `rus_while_*` programs show up only as refusals), program synthesis, and the external Dynamarq workloads and hardware evidence.
#
# Next: [CI](10-ci.md).
