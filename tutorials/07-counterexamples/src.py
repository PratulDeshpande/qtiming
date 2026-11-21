# %% [markdown]
# # Counterexamples you can trust
#
# **Question:** `check` says REFUTED and shows two timelines. Why should I believe them?
#
# Because qtiming does not ask you to trust the solver. Every counterexample is a small JSON object that an independent executor re-runs. Reference: [Command reference](../cli.md), [Verdicts](../verdicts.md), [Policies](../policies.md).

# %%
# hide
import json, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent))
import _show

# %% [markdown]
# ## The program
# `tp_sync` is teleportation with the correction in a `sync` box: no padding, so the arm starts the moment the result arrives. The idle gap on `q2` then depends on how long feed-forward took, which obligation O4 forbids.

# %%
prog = _show.FAMILIES / "teleportation/tp_sync.qasm"
_show.source(prog)

# %% [markdown]
# ## 1. The verdict and its predicted timelines

# %%
code, out = _show.run("check", prog, "--contract", "ibm_heron")
assert code == 1 and out.startswith("REFUTED")

def timeline(text, title):
    lines = text.splitlines()
    i = next(k for k, l in enumerate(lines) if l.strip() == title)
    return [l.strip() for l in lines[i + 1 : i + 5]]

first = timeline(out, "timeline (counterexample):")
second = timeline(out, "timeline (second execution):")
assert first != second and first[0].endswith("2406") and second[0].endswith("2404")

# %% [markdown]
# The two executions differ by 2 ns (2406 vs 2404): the same outcomes, different feed-forward latency. Both latencies lie inside the contract's assumed range, `ff.default` in [0 ns, 600 ns], a *vendor claim* from IBM.

# %% [markdown]
# ## 2. The counterexample as data
# `--format json` writes the counterexample as plain JSON. It is small: one measurement outcome (`omega`) and the latency each feed-forward took (`theta`), once for the counterexample and once for the second execution.

# %%
tmp = tempfile.TemporaryDirectory()
cex = Path(tmp.name) / "cex.json"
_show.run("check", prog, "--contract", "ibm_heron", "--format", "json", "--out", cex, show=False)
report = json.loads(cex.read_text(encoding="utf-8"))
c = report["counterexamples"][0]
print(json.dumps({k: c[k] for k in ("obligation", "tier", "omega", "theta", "second")}, indent=1))
assert c["obligation"]["code"] == "O4" and c["tier"] == 2
assert c["omega"] == c["second"]["omega"]            # same outcomes
assert c["theta"] != c["second"]["theta"]            # only the latencies differ
assert c["theta"]["ff.default@m6"] == "1/2" and c["second"]["theta"]["ff.default@m6"] == "0"

# %% [markdown]
# ## 3. `replay --trace`: run it again, independently
# `replay` feeds exactly those outcomes and latencies to the reference executor, which never imports the graph or solver code (enforced by `lint-imports`). `--trace` prints the timeline it executed.

# %%
code, replayed = _show.run("replay", cex, prog, "--contract", "ibm_heron", "--trace")
assert code == 0 and replayed.startswith("REPRODUCED: O4")

# %% [markdown]
# ## 4. Executed vs predicted
# The solver predicted the first timeline; the executor produced its own. They must agree line for line.

# %%
# hide-input
executed = [l.strip() for l in replayed.splitlines()[1:5]]
rows = "".join(
    f"<tr><th><code>{n}</code></th><td><pre>{a}</pre></td><td><pre>{b}</pre></td></tr>"
    for n, (a, b) in zip(["", "q0", "q1", "q2"], zip(first, executed))
)
_show.figure(f"<table><tr><th></th><th>predicted (solver)</th><th>executed (replay)</th></tr>{rows}</table>")
assert executed == first

# %% [markdown]
# ## 5. A wrong counterexample is rejected
# Edit the JSON so the second execution uses the same latency as the first, and nothing differs any more. The executor says so rather than agreeing.

# %%
bad = Path(tmp.name) / "bad.json"
bad.write_text(cex.read_text(encoding="utf-8").replace('"1/2"', '"0"'), encoding="utf-8")
code, out = _show.run("replay", bad, prog, "--contract", "ibm_heron")
assert code == 1 and out.startswith("NOT REPRODUCED")

# %% [markdown]
# Replaying the real counterexample against a different program fails the same way:

# %%
code, out = _show.run("replay", cex, _show.FAMILIES / "teleportation/tp_basic.qasm", "--contract", "ibm_heron")
assert code == 1 and out.startswith("NOT REPRODUCED")
tmp.cleanup()

# %% [markdown]
# If the solver and executor ever disagreed on a genuine REFUTED, `check` itself would stop with `I-REPLAY-MISMATCH` (exit 4) instead of printing a verdict.

# %% [markdown]
# ## 6. The same program on QUA
# The QUA contract is built on a different personality, but it does not publish a duration for `h`, so qtiming refuses to guess:

# %%
code, out = _show.run("check", prog, "--contract", "qua")
assert code == 2 and "E-CT-MISSING" in out

# %% [markdown]
# That is a usage error (exit 2), not a verdict: there is no QUA counterexample to replay here. Fill the missing duration in a contract and the same pipeline applies; see [Contracts](../contracts.md).

# %% [markdown]
# ## What just happened
# - The solver (tier 2) found two executions of `tp_sync` that differ on `q2` timing.
# - The counterexample is a small JSON object: outcomes plus per-feed-forward latencies.
# - `replay --trace` re-executed it in an independent executor and reproduced the same timeline (exit 0); tampered or mismatched input gives `NOT REPRODUCED` (exit 1).
#
# Next: [tutorials index](index.md).
