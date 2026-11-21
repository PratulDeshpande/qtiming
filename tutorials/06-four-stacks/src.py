# %% [markdown]
# # Same circuit, four stacks
#
# **Question:** I have one dynamic circuit. What does qtiming say about it on IBM Heron, Quantum Machines QUA, Qblox Q1 and ARTIQ?
#
# The answer is four different outcomes, because the four controllers handle the timing of a branch differently. Reference: [Contracts](../contracts.md), [Command reference](../cli.md), [Reading a verdict](../verdicts.md), [Error codes](../errors.md).
#
# **Read this first.** Only the IBM contract publishes gate durations (from an unofficial snapshot). On the other three stacks the durations below are **illustrative `--assume` values chosen for this tutorial**, not vendor numbers. The verdicts show how qtiming behaves, not how fast any real controller is.

# %%
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent))
import _show

TP = _show.FAMILIES / "teleportation/tp_basic.qasm"
TP_Q1 = _show.FAMILIES / "teleportation/tp_q1.qasm"
# Illustrative gate durations (ns) for the three contracts that publish none.
DUR = ["durations.h=32", "durations.cx=64", "durations.x=32", "durations.measure=1000"]


def check(prog, contract, *assume, show=True):
    args = ["check", prog, "--contract", contract]
    for a in assume:
        args += ["--assume", a]
    return _show.run(*args, show=show)

# %% [markdown]
# ## The program
# `tp_basic` is teleportation with one classical correction. It has no timing policy of its own, so each contract's default branch policy applies.

# %%
_show.source("teleportation/tp_basic.qasm")

# %% [markdown]
# ## Stack 1: IBM Heron
# The contract carries gate durations from an IBM Target snapshot. The only assumption is IBM's public claim that feed-forward takes about 600 ns. It is labelled *vendor*, so the verdict is PROVED-UNDER.

# %%
code, ibm = check(TP, "ibm_heron")
assert code == 0 and ibm.startswith("PROVED-UNDER") and "ff.default" in ibm

# %% [markdown]
# ## Stack 2: Quantum Machines QUA
# With no assumptions the run stops: the QUA contract has no duration for `h`. That is `E-CT-MISSING`, an exit 2, not a verdict.

# %%
code, qua0 = check(TP, "qua")
assert code == 2 and "E-CT-MISSING" in qua0

# %% [markdown]
# Supplying durations with `--assume` gets a verdict. The only latency the verdict leans on is QM's vendor claim of 224 ns for active reset.

# %%
code, qua = check(TP, "qua", *DUR)
assert code == 0 and qua.startswith("PROVED-UNDER") and "active_reset" in qua

# %% [markdown]
# ## Stack 3: Qblox Q1
# Q1 sequencers have no real branches. Both arms of an `if` are predicated, so the arms must take the same time. `tp_basic` has an `x` in one arm and nothing in the other, so qtiming refuses to build the graph: `E-ELAB-Q1-NOT-EQUALISABLE`, exit 2. This is a statement about the program on this stack, not a timing verdict.

# %%
code, q1 = check(TP, "q1", *DUR)
assert code == 2 and "E-ELAB-Q1-NOT-EQUALISABLE" in q1

# %% [markdown]
# `tp_q1.qasm` is the same teleportation rewritten for Q1. Both arms hold one real-time instruction of the same duration, and the `eq` policy is declared.

# %%
_show.source("teleportation/tp_q1.qasm")

# %%
code, q1v = check(TP_Q1, "q1", *DUR)
assert code == 0 and q1v.startswith("PROVED-UNDER") and "trigger.network" in q1v

# %% [markdown]
# The assumption here is Qblox's documented trigger-network latency (212 to 240 ns, class *vendor*; the contract notes the documentation page path still needs verifying).

# %% [markdown]
# ## Stack 4: ARTIQ
# ARTIQ's RTIO needs the *commit lead*: how long before its timestamp an event must be committed. The shipped contract does not publish it, so the dependent obligations are UNKNOWN and the report says which field is missing.

# %%
code, art = check(TP, "artiq", *DUR)
assert code == 3 and art.startswith("UNKNOWN") and "timeline.commit_lead" in art

# %% [markdown]
# Assuming a commit lead moves the run on. The two values below are **illustrative**.
# - `commit_lead=0`: the O1 checks that do not depend on the CPU-to-RTIO latency pass, but that latency (`in2cpu`) has no published upper bound, so one check stays UNKNOWN.
# - `commit_lead=50`: the first events in the program are issued with no slack, so O1 fails and the verdict is REFUTED.

# %%
code, art0 = check(TP, "artiq", *DUR, "timeline.commit_lead=0")
assert code == 3 and art0.startswith("UNKNOWN") and "in2cpu is large enough" in art0

# %%
code, art50 = check(TP, "artiq", *DUR, "timeline.commit_lead=50")
assert code == 1 and art50.startswith("REFUTED") and "short by 50 ns" in art50

# %% [markdown]
# ## Side by side
# The table is computed from real runs of both programs on all four contracts. Nothing is typed in by hand. IBM runs with no `--assume`; the other three use the illustrative durations above, and ARTIQ has no commit lead.

# %%
from IPython.display import HTML, display

STACKS = [("ibm_heron", []), ("qua", DUR), ("q1", DUR), ("artiq", DUR)]
ROWS = [("tp_basic", TP), ("tp_q1", TP_Q1)]


def outcome(prog, contract, assume):
    code, out = check(prog, contract, *assume, show=False)
    first = out.splitlines()[0]
    if first.startswith("error:"):
        return first.split(":")[1].strip(), "error", code
    return first.split()[0], "verdict", code


grid = {(p, c): outcome(path, c, a) for p, path in ROWS for c, a in STACKS}
COLOUR = {"PROVED-UNDER": "#1b7f3b", "PROVED": "#1b7f3b", "REFUTED": "#b3261e", "UNKNOWN": "#8a6d00"}
CELL = "padding:6px 10px;border:1px solid #8884"


def td(v):
    return f'<td style="{CELL}"><b style="color:{COLOUR.get(v[0], "#555")}">{v[0]}</b><br><small>{v[1]}, exit {v[2]}</small></td>'


head = "".join(f'<th style="{CELL}">{c}</th>' for c, _ in STACKS)
body = "".join(
    f'<tr><th style="{CELL};text-align:left">{p}</th>' + "".join(td(grid[p, c]) for c, _ in STACKS) + "</tr>"
    for p, _ in ROWS
)
display(HTML(f'<table style="border-collapse:collapse"><tr><th></th>{head}</tr>{body}</table>'))

# %%
assert grid["tp_basic", "ibm_heron"] == ("PROVED-UNDER", "verdict", 0)
assert grid["tp_basic", "qua"] == ("PROVED-UNDER", "verdict", 0)
assert grid["tp_basic", "q1"] == ("E-ELAB-Q1-NOT-EQUALISABLE", "error", 2)
assert grid["tp_basic", "artiq"] == ("UNKNOWN", "verdict", 3)
assert grid["tp_q1", "q1"] == ("PROVED-UNDER", "verdict", 0)
assert grid["tp_q1", "artiq"] == ("UNKNOWN", "verdict", 3)

# %% [markdown]
# The `tp_q1` row is the Q1-shaped variant. It is also accepted on the other stacks, where it behaves like `tp_basic`.

# %% [markdown]
# ## What just happened
# - One circuit, four contracts, four different answers. PROVED-UNDER on IBM and QUA (each rests on a **vendor claim**), a structural refusal on Q1, UNKNOWN on ARTIQ.
# - `E-CT-MISSING` and UNKNOWN are how qtiming reports numbers a vendor has not published. Supplying a value with `--assume` is your own claim, and the report records it.
# - The `--assume` values used here (gate durations, `commit_lead`) are illustrative. The verdicts on QUA, Q1 and ARTIQ say nothing about real hardware speed.
# - Q1 needs the program written for predication (`tp_q1`); the other stacks accept `tp_basic`.
#
# Try other programs and sweep the main latency of each stack on the [comparison page](compare.md). More on the contracts behind these numbers: [Contracts](../contracts.md).
