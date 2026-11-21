# Evidence from hardware jobs

**Question:** the IBM Heron contract carries a *vendor-claimed* feed-forward latency. How would measured scheduler data replace it, and how would qtiming keep the two apart?

> **Everything on this page uses SYNTHETIC test fixtures** (`tests/fixtures/evidence/`). They are hand-made, flagged `"synthetic": true`, use backend `synthetic_backend` and date `2000-01-01`. **No real IBM hardware data is shown or claimed.** The repository contains none, so `qtiming evidence` has not been run on real jobs. Reference: [CLI](../cli.md), [Contracts](../contracts.md), [Status](../status.md).

What works: `evidence report`, `evidence ingest` (to a patch), the synthetic guard. What does **not** exist as a command: applying the patch to a contract. `apply_patch` is a Python library function only, and `check` never reads a patch.

```python
import difflib, json, sys, tomllib
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent))
import _show
FX = "tests/fixtures/evidence"
```

## A job record (synthetic)
Each job holds the scheduler's instruction start/stop times in `dt`. This one has an if/else whose arms differ (100 dt vs 40 dt) and took the shorter arm.

```python
_show.source(f"{FX}/conclusive/pad1.json")
```

    {
     "arms": {
      "else_dt": 40,
      "taken": "else",
      "then_dt": 100
     },
     "backend": "synthetic_backend",
     "circuit_qpy_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
     "dry_run": true,
     "dt_ns": "1",
     "family": "arms_unequal",
     "job_id": "syn-pad1",
     "qiskit_version": "0.0.0-synthetic",
     "runtime_version": "0.0.0-synthetic",
     "scheduler_timing": {
      "instructions": [
       {
        "block_id": null,
        "name": "measure",
        "qubits": [
         0
        ],
        "start_dt": 0,
        "stop_dt": 2000
       },
       {
        "block_id": 0,
        "name": "delay",
        "qubits": [
         1
        ],
        "start_dt": 2480,
        "stop_dt": 2520
       },
       {
        "block_id": 0,
        "name": "delay",
        "qubits": [
         1
        ],
        "start_dt": 2520,
        "stop_dt": 2580
       }
      ]
     },
     "schema": "qtiming-evidence-job/1",
     "submitted_date": "2000-01-01",
     "synthetic": true,
     "synthetic_note": "SYNTHETIC test fixture; not hardware data",
     "tier": "default",
     "transpiler_options": {}
    }
    

## 1. The guard: synthetic jobs are refused by default

```python
code, out = _show.run("evidence", "ingest", f"{FX}/conclusive/ff1.json")
assert code == 2 and "synthetic" in out
```

    error: synthetic job(s) ['tests/fixtures/evidence/conclusive/ff1.json']: pass allow_synthetic to ingest test data
    [exit 2]
    

## 2. `evidence report`
Observed feed-forward is the gap between a measure's end and the start of the conditional block. The `join` column says whether the unequal-arm job looks like `pad` (block lasts as long as the longest arm) or `restart`. Rows are tagged `[SYNTHETIC]`.

```python
code, out = _show.run("evidence", "report", *[f"{FX}/conclusive/{f}.json" for f in ("ff1", "ff2", "pad1", "pad2")])
assert code == 0 and out.count("[SYNTHETIC]") == 4 and "450" in out and "pad" in out
```

    job_id  family  backend  observed_ff_ns  join
    syn-ff1  ff_base  synthetic_backend  450  -  [SYNTHETIC]
    syn-ff2  ff_base  synthetic_backend  520  -  [SYNTHETIC]
    syn-pad1  arms_unequal  synthetic_backend  480  pad  [SYNTHETIC]
    syn-pad2  arms_unequal  synthetic_backend  500  pad  [SYNTHETIC]
    [exit 0]
    

## 3. `evidence ingest --allow-synthetic`: the patch
The patch is TOML, sorted and byte-reproducible (input SHA-256 recorded, no timestamp). Note `synthetic = true` and the `SYNTHETIC TEST DATA` text inside every `source`. Provenance class is `sched` (read from a schedule), distinct from the contract's `vendor`.

```python
conclusive = [f"{FX}/conclusive/{f}.json" for f in ("ff1", "ff2", "pad1", "pad2")]
code, patch_text = _show.run("evidence", "ingest", *conclusive, "--allow-synthetic")
patch = tomllib.loads(patch_text)
assert code == 0 and patch["patch"]["synthetic"] is True
(lat,) = patch["latency"]
assert (lat["lo_ns"], lat["hi_ns"], lat["prov"], lat["n"]) == ("450", "520", "sched", 4)
assert patch["personality_params"]["ibm"]["join_behavior"] == "pad_to_longest_block"
```

    [[evidence]]
    backend = "synthetic_backend"
    family = "ff_base"
    file = "ff1.json"
    job_id = "syn-ff1"
    runtime_version = "0.0.0-synthetic"
    sha256 = "62341d4b6c33fe5594ceb32e58d037fd630ff16151e59b146db44e8db4da6005"
    synthetic = true
    
    [[evidence]]
    backend = "synthetic_backend"
    family = "ff_base"
    file = "ff2.json"
    job_id = "syn-ff2"
    runtime_version = "0.0.0-synthetic"
    sha256 = "f7cc01333caf9ce07bad1b3244008e5848927a8ba83ef47b87eee88c52d833af"
    synthetic = true
    
    [[evidence]]
    backend = "synthetic_backend"
    family = "arms_unequal"
    file = "pad1.json"
    job_id = "syn-pad1"
    runtime_version = "0.0.0-synthetic"
    sha256 = "ecc7d45cf9129439c08f6ebdf591b9c79eddcee4161c3bace74faeab60cde2e3"
    synthetic = true
    
    [[evidence]]
    backend = "synthetic_backend"
    family = "arms_unequal"
    file = "pad2.json"
    job_id = "syn-pad2"
    runtime_version = "0.0.0-synthetic"
    sha256 = "239b198c1406c94700b3408ec369ff811399f92ad776e8b3963b74abdcf67cfc"
    synthetic = true
    
    [[latency]]
    data_dependent = false
    dst = "branch"
    hi_ns = "520"
    key = "ff.default"
    lo_ns = "450"
    n = 4
    prov = "sched"
    source = "SYNTHETIC TEST DATA, not hardware; scheduler_timing dry_run jobs, n=4; min/max; backends=['synthetic_backend'] runtime=['0.0.0-synthetic']"
    src = "measure"
    tier = "default"
    
    [patch]
    schema = "qtiming-evidence-patch/1"
    synthetic = true
    
    [personality_params.ibm]
    join_behavior = "pad_to_longest_block"
    
    [personality_params.ibm.join_behavior_prov]
    prov = "sched"
    source = "SYNTHETIC TEST DATA, not hardware; 2 unequal-arm job(s) all show pad; backends=['synthetic_backend'] runtime=['0.0.0-synthetic']"
    [exit 0]
    

## 4. The patch as a diff
The shipped `ibm_heron` contract against what the patch would replace it with (done here with the library's `apply_patch`; there is no CLI for this step). The patched numbers are strings in the patch; they are shown as emitted.

```python
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
```

    --- ibm_heron (shipped)
    +++ patched (SYNTHETIC)
    @@ -5,2 +5,2 @@
    -   "prov": "vendor",
    -   "source": "old fast-path stack docs; to be calibrated from scheduler_timing evidence (plan Section 18)"
    +   "prov": "sched",
    +   "source": "SYNTHETIC TEST DATA, not hardware; 2 unequal-arm job(s) all show pad; backends=['synthetic_backend'] runtime=['0.0.0-synthetic']"
    @@ -13 +13 @@
    -   "hi_ns": 600,
    +   "hi_ns": "520",
    @@ -15,3 +15,4 @@
    -   "lo_ns": 0,
    -   "prov": "vendor",
    -   "source": "IBM blog, 2025-11-19 (feedforward about 600 ns); vendor claim, not a certified bound",
    +   "lo_ns": "450",
    +   "n": 4,
    +   "prov": "sched",
    +   "source": "SYNTHETIC TEST DATA, not hardware; scheduler_timing dry_run jobs, n=4; min/max; backends=['synthetic_backend'] runtime=['0.0.0-synthetic']",
    

```python
from IPython.display import HTML, display
def bar(y, lo, hi, color, label):
    x0, x1 = 120 + lo * 0.7, 120 + hi * 0.7
    return (f'<rect x="{x0:.0f}" y="{y}" width="{x1 - x0:.0f}" height="26" fill="{color}"/>'
            f'<text x="8" y="{y + 18}" font-size="12" fill="currentColor">{label}</text>'
            f'<text x="{x1 + 6:.0f}" y="{y + 18}" font-size="12" fill="currentColor">{lo}-{hi} ns</text>')
svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 620 110" width="100%" role="img" '
       'aria-label="Vendor claimed feed-forward range 0 to 600 ns versus synthetic observed range 450 to 520 ns">'
       + bar(10, 0, 600, "#8a8f98", "vendor claim")
       + bar(50, 450, 520, "#d9822b", "SYNTHETIC obs.")
       + '<text x="120" y="102" font-size="11" fill="currentColor">feed-forward latency, ns (synthetic data is test-only)</text></svg>')
display(HTML(svg))
```

<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 620 110" width="100%" role="img" aria-label="Vendor claimed feed-forward range 0 to 600 ns versus synthetic observed range 450 to 520 ns"><rect x="120" y="10" width="420" height="26" fill="#8a8f98"/><text x="8" y="28" font-size="12" fill="currentColor">vendor claim</text><text x="546" y="28" font-size="12" fill="currentColor">0-600 ns</text><rect x="435" y="50" width="49" height="26" fill="#d9822b"/><text x="8" y="68" font-size="12" fill="currentColor">SYNTHETIC obs.</text><text x="490" y="68" font-size="12" fill="currentColor">450-520 ns</text><text x="120" y="102" font-size="11" fill="currentColor">feed-forward latency, ns (synthetic data is test-only)</text></svg>

The observed range sits inside the vendor claim, as it should if the claim were sound. The patch records *what was seen* (min and max over n jobs), not a guaranteed bound.

## 5. Inconclusive evidence is not hidden
Here the two unequal-arm jobs disagree (`pad` vs `restart`). qtiming does not pick one.

```python
inc = [f"{FX}/inconclusive/{f}.json" for f in ("ff1", "pad1", "restart1")]
code, out = _show.run("evidence", "report", *inc)
assert "pad" in out and "restart" in out
code, text = _show.run("evidence", "ingest", *inc, "--allow-synthetic", show=False)
p2 = tomllib.loads(text)
prov = p2["personality_params"]["ibm"]
assert "join_behavior" not in prov and prov["join_behavior_prov"]["prov"] == "vendor"
print(prov["join_behavior_prov"]["source"])
```

    job_id  family  backend  observed_ff_ns  join
    syn-ff1  ff_base  synthetic_backend  450  -  [SYNTHETIC]
    syn-pad1  arms_unequal  synthetic_backend  480  pad  [SYNTHETIC]
    syn-restart1  arms_unequal  synthetic_backend  490  restart  [SYNTHETIC]
    [exit 0]
    

    SYNTHETIC TEST DATA, not hardware; inconclusive: unequal-arm jobs gave ['pad', 'restart']; join_behavior left unchanged; backends=['synthetic_backend'] runtime=['0.0.0-synthetic']
    

## What just happened
- `evidence report` and `evidence ingest` turned job records into a readable table and a deterministic TOML patch; everything carried a SYNTHETIC label.
- Conclusive jobs produced a `sched`-provenance latency range and a join behaviour; conflicting jobs produced no change except a note.
- **Not done:** the patch is not applied by any command, and `check` ignores it. No real hardware data exists in the repo, so none of this is a measurement of IBM.

Next: back to the [tutorial index](index.md).
