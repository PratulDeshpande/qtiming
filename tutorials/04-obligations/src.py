# %% [markdown]
# # Obligation tour
#
# **Question:** a report says `O4: 11 obligation(s): proved`. What *is* an obligation, which hardware stack produces which one, and what does a failure of each look like?
#
# An obligation is one small timing claim about the event graph of one program, checked against one hardware personality. This tour runs one small program per obligation kind. Reference: [Obligations](../obligations.md), [Reading a verdict](../verdicts.md), [Contracts](../contracts.md).
#
# | Code | Protects | Stack |
# | --- | --- | --- |
# | O1 | real-time queue never underflows | ARTIQ, Q1 |
# | O2a | condition result valid when the real-time core reads it | Q1 |
# | O2b | an equalised branch never stalls on the feedback latency | IBM, QUA |
# | O3 | reaction deadline (`timing.within`) | all four |
# | O4 | no idle gap whose length varies | IBM, QUA |
# | O5 | capacity | ARTIQ (SED lanes), Q1 (trigger network) |
# | O7 | equalised blocks end together for every outcome | IBM, Q1 |

# %%
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent))
import _show

HERE = Path.cwd()
TP = _show.FAMILIES / "teleportation/tp_basic.qasm"
RESET = _show.FAMILIES / "active_reset/reset_within_tight.qasm"

# ARTIQ and Q1 publish no gate durations. The numbers below are ILLUSTRATIVE assumptions
# passed with --assume (class `vendor`); they are not vendor values.
ARTIQ = ["durations.x=100", "durations.measure=1000", "durations.h=50", "in2cpu=0:300"]
Q1 = ["durations.x=32", "durations.measure=1000"]


def check(program, contract, *assume, policy=None):
    args = ["check", program, "--contract", contract]
    for a in assume:
        args += ["--assume", a]
    if policy:
        args += ["--policy", policy]
    return _show.run(*args)


def line(out, code):
    return next(l.strip() for l in out.splitlines() if l.strip().startswith(code + ":"))


# %% [markdown]
# Every report prints one `Ok:` line per obligation kind and ends with a line naming what this build does **not** check. That last line is covered at the end.

# %% [markdown]
# ## IBM Heron: O2b, O3, O4, O7
# Teleportation with one corrected branch, `@timing.policy eq`, deadline 3000 ns.

# %%
_show.source(TP)

# %%
code, out = check(TP, "ibm_heron")
assert code == 0 and out.startswith("PROVED-UNDER")
for k in ("O2b", "O3", "O4", "O7"):
    assert "proved" in line(out, k), k

# %% [markdown]
# Four kinds from one program. `O2b` says the inserted wait covers the 600 ns feedback latency (a **vendor** claim, shown under *assumptions*). `O4` has 11 obligations, one per idle gap. `O7` says the equalised branch ends at the same time for every outcome. Margin 0 ns on O2b, O4 and O7 means "equal", which is exactly what they demand.
#
# ### O3 failing
# `reset_within_tight` demands a reaction within 300 ns, tighter than the 600 ns feedforward claim.

# %%
_show.source(RESET)

# %%
code, out = check(RESET, "ibm_heron", policy="eq")
assert code == 1 and out.startswith("REFUTED") and "O3 failed at" in out
assert line(out, "O3").endswith("refuted (tier 2)")

# %%
_show.report_svg(RESET, "ibm_heron")

# %% [markdown]
# (The picture uses the default policy, so it shows the `sync` counterexample, which fails O4; the text above is the `eq` run. Under `eq` the branch starts only after the full 600 ns, so no 300 ns deadline can hold. The fix is a deadline of at least 600 ns, only if that is a real requirement.)
#
# ### O4 failing
# `tp_sync` asks for identical idle time on `q2` across outcomes; the two executions differ by 2 ns.

# %%
code, out = check(_show.FAMILIES / "teleportation/tp_sync.qasm", "ibm_heron", policy="eq")
assert code == 1 and "O4 failed at" in out and "O4 at node 11" in out

# %% [markdown]
# ## QUA: O2b, O3, O4 and a different latency
# The same `reset_within_tight` on QUA, with `x` and `measure` durations assumed. QUA's vendor claim is a 224 ns active reset, so a 300 ns deadline is met with 76 ns to spare. Same program, other contract, other verdict.

# %%
code, out = check(RESET, "qua", "durations.x=32", "durations.measure=1000", policy="eq")
assert code == 0 and out.startswith("PROVED-UNDER")
assert "margin 76 ns" in line(out, "O3")
for k in ("O2b", "O4"):
    assert "proved" in line(out, k)

# %% [markdown]
# ## Q1: O1, O2a, O3, O5, O7
# Q1 accepts only `eq`, with arms of equal real-time length; otherwise you get `E-ELAB-Q1-NOT-EQUALISABLE` (exit 2, see [Error codes](../errors.md)), which the shipped `tp_basic` hits on Q1. So this tutorial ships its own small program: two measure-and-correct steps, each branch padded with a `delay`, the second with a 500 ns deadline.

# %%
Q1PROG = HERE / "q1_two_triggers.qasm"
_show.source(Q1PROG)

# %%
code, out = check(Q1PROG, "q1", *Q1)
assert code == 0 and out.startswith("PROVED-UNDER")
for k in ("O1", "O2a", "O3", "O5", "O7"):
    assert "proved" in line(out, k), k

# %% [markdown]
# `O1`: each real-time event is issued early enough (8 events). `O2a`: the trigger-network result (212 to 239 ns, a **vendor** documented figure, not cycle-certified) is valid before the branch reads it. `O5`: the second trigger is not inside the first one's 252 ns network-busy window. `O7`: both arms take the same real-time time.
#
# `explain --obligations` lists the individual claims behind those lines. Here are the O5 and O7 ones:

# %%
code, out = _show.run("explain", Q1PROG, "--contract", "q1", *sum((["--assume", a] for a in Q1), []), "--obligations", show=False)
for l in out.splitlines():
    if l.startswith(("O5", "O7")):
        print(l)
assert any(l.startswith("O5") for l in out.splitlines())

# %% [markdown]
# A passing program has no counterexample timeline in the text report; the HTML report carries the schedule as an SVG:

# %%
_show.report_svg(Q1PROG, "q1", *Q1)

# %% [markdown]
# ## ARTIQ: O1 (fails) and O5 (unknown)
# `artiq_ramsey_fb` is a synthetic Ramsey kernel (written by the qtiming authors, not ARTIQ code) with a feedback correction. The ARTIQ contract publishes no commit lead, so we assume 200 ns (illustrative). The first `h` is at time 0, so nothing gives it any lead.

# %%
RAMSEY = _show.FAMILIES / "artiq/artiq_ramsey_fb.qasm"
_show.source(RAMSEY)

# %%
code, out = check(RAMSEY, "artiq", *ARTIQ, "timeline.commit_lead=200")
assert code == 1 and out.startswith("REFUTED")
assert "O1 failed at" in out and "short by 200 ns" in out
assert "refuted (tier 0, margin -200 ns)" in line(out, "O1")

# %% [markdown]
# O1 failed at source line 7 (the first `h`), short by 200 ns: the margin is negative. Compare `artiq_slack_neg`, where the feedback is issued with no slack after the measurement:

# %%
code, out = check(_show.FAMILIES / "artiq/artiq_slack_neg.qasm", "artiq", *ARTIQ, "timeline.commit_lead=200")
assert code == 1 and "O1 failed at" in out

# %% [markdown]
# ### O5 is not built symbolically
# With a commit lead of 0 the O1 failure goes away, and the verdict is still not PROVED:

# %%
code, out = check(RAMSEY, "artiq", *ARTIQ, "timeline.commit_lead=0")
assert code == 3 and out.startswith("UNKNOWN")
assert "Tier 2 does not encode Events (O5) yet" in out
assert "unknown" in line(out, "O5")

# %% [markdown]
# **The symbolic encoding of O5 is not built in this version.** O5 on ARTIQ (SED lane capacity) is UNKNOWN for every ARTIQ program I ran, even when all of O1 holds. Do not read an ARTIQ `UNKNOWN` of this kind as "probably fine". On Q1, O5 (trigger-network busy window) *is* checked, as above.

# %% [markdown]
# ## What is not checked by this build
# Every report ends with the same line. A verdict does not cover these:

# %%
code, out = check(TP, "ibm_heron")
last = out.strip().splitlines()[-1]
for k in ("O4a", "O6", "O8", "O9", "O7 for SYNC with a spread bound"):
    assert k in last, k

# %% [markdown]
# | Not checked | Meaning |
# | --- | --- |
# | O4a | off by default |
# | O6 | blocking calls |
# | O8 | timing grid |
# | O9 | loop windows |
# | O7 for `sync` with a spread bound | `delta` and `gap` are parsed and stored but no obligation uses them |
#
# ## What just happened
# - One program per obligation kind, on the stack that generates it: IBM (O2b, O3, O4, O7), QUA (O2b, O3, O4), Q1 (O1, O2a, O3, O5, O7), ARTIQ (O1, O5).
# - Failures name the kind, the node and the source line: O3 on IBM, O4 on IBM, O1 on ARTIQ.
# - The same program can pass on one contract and fail on another (O3 on QUA vs IBM), because the contracts carry different latencies, each labelled with its provenance.
# - O5 on ARTIQ is UNKNOWN: its symbolic encoding is not built. Numbers passed with `--assume` here are illustrative, not vendor values.
#
# Reference: [Obligations](../obligations.md), [Policies](../policies.md), [CLI](../cli.md).
