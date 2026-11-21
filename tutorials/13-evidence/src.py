# %% [markdown]
# # Evidence from hardware jobs
#
# **Question:** the IBM Heron contract carries a *vendor-claimed* feed-forward latency. How would measured scheduler data replace it, and how would qtiming keep the two apart?
#
# > **Everything on this page uses SYNTHETIC test fixtures** (`tests/fixtures/evidence/`). They are hand-made, flagged `"synthetic": true`, use backend `synthetic_backend` and date `2000-01-01`. **No real IBM hardware data is shown or claimed.** The repository contains none, so `qtiming evidence` has not been run on real jobs. Reference: [CLI](../cli.md), [Contracts](../contracts.md), [Status](../status.md).
#
# What works: `evidence report`, `evidence ingest` (to a patch), the synthetic guard. What does **not** exist as a command: applying the patch to a contract. `apply_patch` is a Python library function only, and `check` never reads a patch.

# %%
# hide
import difflib, json, sys, tomllib
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent))
import _show

# %%
FX = "tests/fixtures/evidence"

# %% [markdown]
# ## A job record (synthetic)
# Each job holds the scheduler's instruction start/stop times in `dt`. This one has an if/else whose arms differ (100 dt vs 40 dt) and took the shorter arm.

# %%
_show.source(f"{FX}/conclusive/pad1.json")

# %% [markdown]
# ## 1. The guard: synthetic jobs are refused by default

# %%
code, out = _show.run("evidence", "ingest", f"{FX}/conclusive/ff1.json")
assert code == 2 and "synthetic" in out

# %% [markdown]
# ## 2. `evidence report`
# Observed feed-forward is the gap between a measure's end and the start of the conditional block. The `join` column says whether the unequal-arm job looks like `pad` (block lasts as long as the longest arm) or `restart`. Rows are tagged `[SYNTHETIC]`.

# %%
code, out = _show.run("evidence", "report", *[f"{FX}/conclusive/{f}.json" for f in ("ff1", "ff2", "pad1", "pad2")])
assert code == 0 and out.count("[SYNTHETIC]") == 4 and "450" in out and "pad" in out

# %% [markdown]
# ## 3. `evidence ingest --allow-synthetic`: the patch
# The patch is TOML, sorted and byte-reproducible (input SHA-256 recorded, no timestamp). Note `synthetic = true` and the `SYNTHETIC TEST DATA` text inside every `source`. Provenance class is `sched` (read from a schedule), distinct from the contract's `vendor`.

# %%
conclusive = [f"{FX}/conclusive/{f}.json" for f in ("ff1", "ff2", "pad1", "pad2")]
code, patch_text = _show.run("evidence", "ingest", *conclusive, "--allow-synthetic")
patch = tomllib.loads(patch_text)
assert code == 0 and patch["patch"]["synthetic"] is True
(lat,) = patch["latency"]
assert (lat["lo_ns"], lat["hi_ns"], lat["prov"], lat["n"]) == ("450", "520", "sched", 4)
assert patch["personality_params"]["ibm"]["join_behavior"] == "pad_to_longest_block"

# %% [markdown]
# ## 4. The patch as a diff
# The shipped `ibm_heron` contract against what the patch would replace it with (done here with the library's `apply_patch`; there is no CLI for this step). The patched numbers are strings in the patch; they are shown as emitted.

# %%
from qtiming.evidence import apply_patch
base = tomllib.loads((_show.ROOT / "src/qtiming/contract/instances/ibm_heron.toml").read_text(encoding="utf-8"))
new = apply_patch(base, patch)
def view(c):
    keep = {"latency": c["latency"], "join": c["personality_params"]["ibm"]}
    return json.dumps(keep, indent=1, sort_keys=True).replace("\\", "/").splitlines()
diff = list(difflib.unified_diff(view(base), view(new), "ibm_heron (shipped)", "patched (SYNTHETIC)", lineterm="", n=0))
print("\n".join(diff))
assert any(l.startswith('-  "hi_ns": 600') or '"hi_ns": 600' in l and l.startswith("-") for l in diff)
assert any('"hi_ns": "520"' in l and l.startswith("+") for l in diff)

# %%
# hide-input
def bar(y, lo, hi, fill, stroke, label, dash=""):  # docs theme tokens; synthetic data is drawn dashed
    x0, x1 = 120 + lo * 0.7, 120 + hi * 0.7
    return (f'<rect x="{x0:.0f}" y="{y}" width="{x1 - x0:.0f}" height="26" fill="{fill}" stroke="{stroke}"{dash}/>'
            f'<text x="8" y="{y + 18}" font-size="12">{label}</text>'
            f'<text x="{x1 + 6:.0f}" y="{y + 18}" font-size="12">{lo}-{hi} ns</text>')
svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 620 110" width="620" role="img" '
       'aria-label="Vendor claimed feed-forward range 0 to 600 ns versus synthetic observed range 450 to 520 ns">'
       + bar(10, 0, 600, "#F4F6F9", "#111418", "vendor claim")
       + bar(50, 450, 520, "#EAF2FA", "#0B5FA5", "SYNTHETIC obs.", ' stroke-dasharray="4 3"')
       + '<text x="120" y="102" font-size="11">feed-forward latency, ns (synthetic data is test-only)</text></svg>')
_show.figure(svg)

# %% [markdown]
# The observed range sits inside the vendor claim, as it should if the claim were sound. The patch records *what was seen* (min and max over n jobs), not a guaranteed bound.

# %% [markdown]
# ## 5. Inconclusive evidence is not hidden
# Here the two unequal-arm jobs disagree (`pad` vs `restart`). qtiming does not pick one.

# %%
inc = [f"{FX}/inconclusive/{f}.json" for f in ("ff1", "pad1", "restart1")]
code, out = _show.run("evidence", "report", *inc)
assert "pad" in out and "restart" in out
code, text = _show.run("evidence", "ingest", *inc, "--allow-synthetic", show=False)
p2 = tomllib.loads(text)
prov = p2["personality_params"]["ibm"]
assert "join_behavior" not in prov and prov["join_behavior_prov"]["prov"] == "vendor"
print(prov["join_behavior_prov"]["source"])

# %% [markdown]
# ## What just happened
# - `evidence report` and `evidence ingest` turned job records into a readable table and a deterministic TOML patch; everything carried a SYNTHETIC label.
# - Conclusive jobs produced a `sched`-provenance latency range and a join behaviour; conflicting jobs produced no change except a note.
# - **Not done:** the patch is not applied by any command, and `check` ignores it. No real hardware data exists in the repo, so none of this is a measurement of IBM.
#
# Next: back to the [tutorial index](index.md).
