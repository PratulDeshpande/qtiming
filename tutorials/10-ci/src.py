# %% [markdown]
# # qtiming in CI
#
# **Question:** can I make a pull request fail when a circuit's timing breaks, and see the finding in GitHub?
#
# Yes: `check` has stable exit codes and four report formats, one of which is SARIF, the format GitHub code scanning reads. Reference: [Command reference](../cli.md), [Reading a verdict](../verdicts.md).

# %%
import json, sys, tempfile
from html import escape
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent))
import _show

# %% [markdown]
# ## The program
# `tp_sync` is teleportation whose idle time on `q2` must not depend on the measurement outcome. It does, so a CI gate should catch it.

# %%
_show.source("teleportation/tp_sync.qasm")

# %% [markdown]
# ## Exit codes are the gate
# A CI step fails on any non-zero exit. `check` exits `0` proved, `1` refuted, `2` usage error, `3` unknown, `4` internal.

# %%
prog = "benchmarks/families/teleportation/tp_sync.qasm"
basic = "benchmarks/families/teleportation/tp_basic.qasm"
code, out = _show.run("check", prog, "--contract", "ibm_heron")
assert code == 1 and out.startswith("REFUTED")

# %% [markdown]
# `tp_basic` is PROVED-UNDER (it relies on a vendor-claimed latency). By default that exits `0`; `--strict-proved` makes a gate that refuses assumptions exit `1`.

# %%
code, out = _show.run("check", basic, "--contract", "ibm_heron")
assert code == 0 and out.startswith("PROVED-UNDER")
code, out = _show.run("check", basic, "--contract", "ibm_heron", "--strict-proved")
assert code == 1

# %% [markdown]
# A missing file is a usage error, exit `2`, so a broken path in your workflow is distinguishable from a timing failure:

# %%
code, out = _show.run("check", "no_such_file.qasm", "--contract", "ibm_heron")
assert code == 2

# %% [markdown]
# ## Report formats
# `--format json` is for scripts, `sarif` for code scanning, `html` for a human (it embeds the SVG timeline), `text` is the default. `--out FILE` writes to a file instead of stdout.

# %%
d = Path(tempfile.mkdtemp())
for fmt in ("json", "sarif", "html"):
    code, _ = _show.run("check", prog, "--contract", "ibm_heron", "--format", fmt, "--out", d / f"r.{fmt}", show=False)
    assert code == 1 and (d / f"r.{fmt}").stat().st_size > 0
rep = json.loads((d / "r.json").read_text(encoding="utf-8"))
print(rep["verdict"], "| keys:", ", ".join(rep))
assert rep["verdict"] == "REFUTED" and "counterexamples" in rep

# %% [markdown]
# ## SARIF: one finding per failed obligation
# Each SARIF `result` has a rule id, a level, a message and a source location. The assumptions the verdict relies on are `note`-level results; lint findings are warnings.

# %%
sarif = json.loads((d / "r.sarif").read_text(encoding="utf-8"))
run = sarif["runs"][0]
for r in run["results"]:
    loc = r["locations"][0]["physicalLocation"]
    uri = loc["artifactLocation"]["uri"].replace("\\", "/")
    uri = uri[uri.find("benchmarks/"):] if "benchmarks/" in uri else uri
    line = loc.get("region", {}).get("startLine", "-")
    print(f'{r["level"]:8} {r["ruleId"]:16} {uri}:{line}')
errors = [r for r in run["results"] if r["level"] == "error"]
assert sarif["version"] == "2.1.0" and run["properties"]["verdict"] == "REFUTED"
assert len(errors) == 1 and errors[0]["ruleId"] == "V-O4"

# %% [markdown]
# The error finding as GitHub would show it, a hand-made rendering of the real SARIF above (not a GitHub screenshot):

# %%
from IPython.display import HTML, display

e = errors[0]
p = e["locations"][0]["physicalLocation"]
path = p["artifactLocation"]["uri"].replace("\\", "/")
path = path[path.find("benchmarks/"):] if "benchmarks/" in path else path
cex = e["properties"]["counterexample"]
card = f"""<div style="font:14px/1.5 system-ui,sans-serif;border:1px solid #d0d7de;border-radius:6px;max-width:640px;overflow:hidden">
<div style="background:#ffebe9;padding:8px 12px;border-bottom:1px solid #d0d7de;color:#82071e"><b>{escape(e['level'])}</b> &middot; {escape(e['ruleId'])}</div>
<div style="padding:12px;color:#1f2328">
<div style="margin-bottom:6px"><b>{escape(e['message']['text'])}</b></div>
<div><code>{escape(path)}:{p['region']['startLine']}:{p['region']['startColumn']}</code></div>
<div style="margin-top:8px;color:#59636e">Counterexample: outcomes <code>{escape(json.dumps(cex['omega']))}</code>, latencies <code>{escape(json.dumps(cex['theta']))}</code> (dt)</div>
<div style="margin-top:4px;color:#59636e">Tier {e['properties']['tier']}, policy {escape(e['properties']['policy'])}, fingerprint <code>{escape(e['partialFingerprints']['qtiming/v1'][:12])}</code></div>
</div></div>"""
display(HTML(card))

# %% [markdown]
# ## Example workflow
# Shown as text; this repository does not ship it under `.github`. `continue-on-error` lets the SARIF upload run even when the check fails, then a final step re-applies the failure.

# %%
WORKFLOW = """\
name: timing
on: [pull_request]
permissions:
  contents: read
  security-events: write
jobs:
  qtiming:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install "qtiming[z3]"
      - id: check
        run: qtiming check circuits/tp_sync.qasm --contract ibm_heron --format sarif --out qtiming.sarif
        continue-on-error: true
      - uses: github/codeql-action/upload-sarif@v3
        with: { sarif_file: qtiming.sarif }
      - if: steps.check.outcome == 'failure'
        run: exit 1
"""
print(WORKFLOW)
assert "--format sarif" in WORKFLOW

# %% [markdown]
# ## What just happened
# - Exit code `1` for REFUTED (and, with `--strict-proved`, for PROVED-UNDER), `2` for a usage error: a CI step needs no output parsing.
# - SARIF carries the REFUTED obligation as an `error` result at the offending source line, plus the vendor assumption as a `note`.
# - Z3 (the `z3` extra) is needed for Tier 2 refutations; with `--no-tier2` what Tier 1 cannot prove is UNKNOWN (exit `3`).
#
# See also: [Command reference](../cli.md). Next: the contract tutorials.
