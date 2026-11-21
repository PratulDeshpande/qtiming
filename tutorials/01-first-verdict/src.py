# %% [markdown]
# # Your first verdict
#
# **Question:** I have a dynamic circuit. Will its timing hold on IBM Heron?
#
# This tutorial walks the four everyday commands: `lint`, `explain`, `check`, `replay`. Reference: [Quickstart](../quickstart.md), [Command reference](../cli.md).

# %%
import json, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent))
import _show

# %% [markdown]
# ## The program
# Teleportation with one classical correction. The `@timing.within` annotation says the correction must be issued within 3000 ns of the measurement result arriving.

# %%
_show.source("teleportation/tp_basic.qasm")

# %% [markdown]
# ## 1. `lint`: is the front end happy?

# %%
code, out = _show.run("lint", _show.FAMILIES / "teleportation/tp_basic.qasm", "--contract", "ibm_heron")
assert code in (0, 1)

# %% [markdown]
# ## 2. `explain`: what did qtiming build from it?

# %%
code, out = _show.run("explain", _show.FAMILIES / "teleportation/tp_basic.qasm", "--contract", "ibm_heron")
assert code == 0 and "obligations" in out

# %% [markdown]
# ## 3. `check`: the verdict
# `PROVED-UNDER` means the claim holds **if** the listed assumptions do. Here the only assumption is IBM's public claim that feed-forward takes about 600 ns; it is labelled *vendor*, not a certified bound.

# %%
code, out = _show.run("check", _show.FAMILIES / "teleportation/tp_basic.qasm", "--contract", "ibm_heron")
assert code == 0 and out.startswith("PROVED-UNDER") and "ff.default" in out

# %% [markdown]
# The same report as HTML carries an SVG timeline:

# %%
_show.report_svg(_show.FAMILIES / "teleportation/tp_basic.qasm", "ibm_heron")

# %% [markdown]
# ## 4. A program that fails: `tp_sync`
# The same teleportation, but with the idle time on `q2` required to be identical across measurement outcomes (`sync`). It is not.

# %%
prog = _show.FAMILIES / "teleportation/tp_sync.qasm"
code, out = _show.run("check", prog, "--contract", "ibm_heron")
assert code == 1 and out.startswith("REFUTED")

# %% [markdown]
# The two timelines above are the counterexample: two executions that differ by a few nanoseconds on `q2`. Exit code **1** means refuted; the full list is `0` proved, `1` refuted, `2` usage error, `3` unknown, `4` internal.

# %% [markdown]
# ## 5. `replay`: don't trust it, re-run it
# qtiming re-executes every counterexample in an independent executor that shares no code with the solver.

# %%
with tempfile.TemporaryDirectory() as d:
    cex = Path(d) / "cex.json"
    _show.run("check", prog, "--contract", "ibm_heron", "--format", "json", "--out", cex, show=False)
    assert json.loads(cex.read_text(encoding="utf-8"))["verdict"] == "REFUTED"
    code, out = _show.run("replay", cex, prog, "--contract", "ibm_heron")
assert code == 0

# %% [markdown]
# ## What just happened
# - `check` turned the program into an event graph, generated timing obligations, and discharged them.
# - `tp_basic` held under a vendor-claimed latency, so it is PROVED-UNDER, not PROVED.
# - `tp_sync` was REFUTED with a concrete pair of executions, confirmed by replay.
#
# Next: [The four verdicts](02-four-verdicts.md).
