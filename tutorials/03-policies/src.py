# %% [markdown]
# # Policies and annotations
#
# **Question:** a branch on a measurement result takes different times on its two arms. How do I tell qtiming what I expect, and what does it do about it?
#
# Three policies (`eq`, `sync`, `exp`) and three annotations that matter here (`within`, `hard`, `cap`). Reference: [Policies and annotations](../policies.md), [Command reference](../cli.md).

# %%
# hide
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent))
import _show

# %%
TP = _show.FAMILIES / "teleportation"
MS = _show.FAMILIES / "magic_state"
QUA = ["--contract", "qua", "--assume", "durations.h=32", "--assume", "durations.cx=64",
       "--assume", "durations.x=32", "--assume", "durations.measure=1000"]

# %% [markdown]
# ## The program, with policy `eq`
# `@timing.policy eq` says both arms of the branch must take the same time. `@timing.within 3000ns c[1]` is a deadline: the correction must start within 3000 ns of the result.

# %%
_show.source("teleportation/tp_basic.qasm")

# %% [markdown]
# ## Before and after: what `eq` does to the program
# `explain --elaborated` prints the program after qtiming rewrote it. Lines marked `synth(from n9)` did not exist in your source: a barrier, a delay equal to the **upper bound of the feedback latency**, and a delay on the `else` arm to match the `x` gate on the `then` arm. On IBM Heron that delay is 150 dt, which is the vendor-claimed 600 ns at 4 ns per dt.

# %%
code, out = _show.run("explain", TP / "tp_basic.qasm", "--contract", "ibm_heron", "--elaborated")
assert code == 0
assert "Barrier n15" in out and "Delay n16 qubits=(2,) dur=150" in out and "Delay n13 qubits=(2,) dur=8" in out

# %% [markdown]
# The synthesised delay comes from the contract, so another backend gives another number. On QUA (with the gate durations supplied by `--assume`, since the contract leaves them absent) the claimed 224 ns active reset becomes 56 dt:

# %%
code, out = _show.run("explain", TP / "tp_basic.qasm", *QUA, "--elaborated")
assert code == 0 and "Delay n16 qubits=(2,) dur=56" in out

# %% [markdown]
# ## The verdict for `eq`, and its timeline
# The idle time on `q2` is now the same for every outcome and every latency, so O4 is proved. The only assumption is the vendor latency claim, hence PROVED-UNDER.

# %%
code, out = _show.run("check", TP / "tp_basic.qasm", "--contract", "ibm_heron")
assert code == 0 and out.startswith("PROVED-UNDER") and "O4: 11" in out and "ff.default" in out

# %%
_show.report_svg(TP / "tp_basic.qasm", "ibm_heron")

# %% [markdown]
# ## The same circuit under `sync`
# `sync` pads nothing: each arm runs as soon as the result is there. `tp_sync` is the same teleportation with `@timing.policy sync` and the requirement that idle time on `q2` not vary. It varies, so it is REFUTED, and the text report draws the two executions that differ.

# %%
code, out = _show.run("check", TP / "tp_sync.qasm", "--contract", "ibm_heron")
assert code == 1 and out.startswith("REFUTED") and "O4" in out and "timeline (second execution)" in out

# %% [markdown]
# Same program, same verdict on QUA, where `sync` is the native policy (an align is inserted after the branch, see the elaborated output below). The refutation is about the program asking for constant idle time, not about the backend:

# %%
code, out = _show.run("check", TP / "tp_sync.qasm", *QUA)
assert code == 1 and out.startswith("REFUTED")
code, out = _show.run("explain", TP / "tp_sync.qasm", *QUA, "--elaborated")
assert "Barrier n13" in out

# %% [markdown]
# ## `exp`: you own the timeline
# `tp_exp` writes its delays by hand and asks for `exp`. Per the compatibility table, only an exposed-timeline backend (ARTIQ) accepts that. IBM and QUA refuse it up front:

# %%
code, out = _show.run("check", TP / "tp_exp.qasm", "--contract", "ibm_heron")
assert code == 1 and "policy-incompatible" in out

# %%
code, out = _show.run("check", TP / "tp_exp.qasm", *QUA)
assert code == 1 and "policy-incompatible" in out

# %% [markdown]
# On ARTIQ the policy is accepted, but the verdict is **UNKNOWN**: the shipped contract has no `timeline.commit_lead` and no gate durations, and qtiming does not guess them. That is the honest state of the contract, not a pass.

# %%
code, out = _show.run("check", TP / "tp_exp.qasm", "--contract", "artiq",
                      "--assume", "durations.h=32", "--assume", "durations.cx=64",
                      "--assume", "durations.x=32", "--assume", "durations.measure=1000")
assert code == 3 and out.startswith("UNKNOWN") and "timeline.commit_lead" in out

# %% [markdown]
# ## `within` and `hard`: deadlines
# The magic-state injection family puts a conditional fix-up inside a `within` box. `msi_hard_3000` has no policy annotation, so `--policy` decides. Under the default (`sync`) it fails O4 for the reason above; under `eq` the 3000 ns deadline is met with a margin of 2400 ns (3000 ns minus the 600 ns latency bound).

# %%
_show.source("magic_state/msi_hard_3000.qasm")

# %%
code, out = _show.run("check", MS / "msi_hard_3000.qasm", "--contract", "ibm_heron")
assert code == 1 and "O4" in out
code, out = _show.run("check", MS / "msi_hard_3000.qasm", "--contract", "ibm_heron", "--policy", "eq")
assert code == 0 and out.startswith("PROVED-UNDER") and "margin 2400 ns" in out

# %% [markdown]
# `@timing.hard` marks the deadline as one that only `cyc` or `cert` evidence should discharge. In this build `msi_hard_3000` still comes out PROVED-UNDER on a vendor bound, exactly like the soft version `msi_soft_within`, so the flag does not change the verdict here (it is recorded for the evidence phase, which is not built yet).

# %%
code, soft = _show.run("check", MS / "msi_soft_within.qasm", "--contract", "ibm_heron", "--policy", "eq", show=False)
assert code == 0 and soft.startswith("PROVED-UNDER")

# %% [markdown]
# A deadline tighter than the latency is refuted with a counterexample. `msi_hard_tight` under `eq`:

# %%
code, out = _show.run("check", MS / "msi_hard_tight.qasm", "--contract", "ibm_heron", "--policy", "eq")
assert code == 1 and "O3 failed" in out

# %% [markdown]
# ## `cap`
# `@timing.cap N` bounds a `while` loop, and a `while` without it fails with `E-FE-UNBOUNDED-WHILE`. The unrolled loop and the QUA run are in [Policies and annotations](../policies.md#annotations). Note that RUS loops are not wired into `check` yet, so this tutorial does not demo one.

# %% [markdown]
# ## What just happened
# - `eq` rewrote the program: barrier, a latency-bound delay, and a padding delay on the short arm (`explain --elaborated`, `synth(from ...)` lines). The delay size comes from the contract (150 dt on IBM, 56 dt on QUA).
# - `sync` adds nothing, so a requirement of constant idle time is REFUTED with two replayable executions.
# - `exp` is accepted only by ARTIQ, and there the verdict is UNKNOWN because the contract omits numbers.
# - `within` generates a deadline obligation; the margin is the deadline minus the vendor latency bound. `hard` does not yet change the verdict.
#
# Next: [Backends and contracts](04-obligations.md).
