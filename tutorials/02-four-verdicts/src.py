# %% [markdown]
# # The four verdicts
#
# **Question:** `check` printed `PROVED-UNDER` (or `UNKNOWN`). Is that a pass? What would make it `PROVED`?
#
# Every `check` ends in exactly one of four verdicts. This tutorial produces each one from a real program, on IBM Heron and on ARTIQ, and shows how `--strict-proved` and `--assume` change what you get. Reference: [Reading a verdict](../verdicts.md), [Contracts](../contracts.md), [Command reference](../cli.md).

# %%
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent))
import _show
from IPython.display import HTML, display

TUT = Path.cwd().relative_to(_show.ROOT)  # tutorials/02-four-verdicts, repo-relative
FAM = _show.FAMILIES


def card(rows):
    """Verdict cards, one per (title, exit code, report text). The label is text, not just colour."""
    import html
    css = ("<style>.qv{display:grid;grid-template-columns:repeat(auto-fit,minmax(15rem,1fr));gap:.6rem}"
           ".qv div{border:1px solid #8886;border-left:6px solid var(--c);border-radius:6px;padding:.5rem .7rem}"
           ".qv b{font-size:1.05em}.qv small{display:block;opacity:.8}</style>")
    colour = {"PROVED": "#1a7f37", "PROVED-UNDER": "#9a6700", "REFUTED": "#cf222e", "UNKNOWN": "#6e7781"}
    out = []
    for title, code, text in rows:
        v = text.split()[0]
        out.append(f'<div style="--c:{colour[v]}"><b>{html.escape(v)}</b> (exit {code})'
                   f'<small>{html.escape(title)}</small></div>')
    display(HTML(css + '<div class="qv">' + "".join(out) + "</div>"))


# %% [markdown]
# ## How a program gets its verdict
# `check` generates timing obligations and the result is the **weakest** of them, in the order `REFUTED`, `UNKNOWN`, `PROVED-UNDER`, `PROVED`. One failing obligation refutes the whole program; one undecided obligation makes it unknown even if the rest passed.

# %% [markdown]
# ## 1. PROVED: nothing depends on a latency
# A branch-free Bell circuit. No feed-forward, so no obligation depends on an unpublished or vendor-claimed number.

# %%
_show.source(TUT / "plain.qasm")

# %%
code, out = _show.run("check", TUT / "plain.qasm", "--contract", "ibm_heron")
assert code == 0 and out.startswith("PROVED ") and "assumptions" not in out
proved = (code, out)

# %% [markdown]
# No `assumptions:` block: the result was decided by exact evaluation (tier 0). This is the only way a program reaches `PROVED` with the shipped contracts: every shipped contract states its latencies at the `vendor` class, and only `cyc` or `cert` evidence can discharge a latency-dependent obligation (see [assumption classes](../verdicts.md#assumptions-and-evidence-classes)). I found no family program with a branch that is PROVED, and `--assume` cannot raise a number above `vendor`.

# %% [markdown]
# ## 2. PROVED-UNDER: true if the vendor number is
# Teleportation with a correction branch. It holds if the feed-forward latency stays within IBM's public claim.

# %%
code, out = _show.run("check", FAM / "teleportation/tp_basic.qasm", "--contract", "ibm_heron")
assert code == 0 and out.startswith("PROVED-UNDER") and "weakest class: vendor" in out
under = (code, out)

# %% [markdown]
# Read the assumption line: key `ff.default`, interval `[0 ns, 600 ns]`, class `vendor`, and the citation labelled *vendor claim, not a certified bound*. Exit code is 0, so a CI gate would pass. If that is too weak for you, add `--strict-proved`:

# %%
code, out = _show.run("check", FAM / "teleportation/tp_basic.qasm", "--contract", "ibm_heron", "--strict-proved")
assert code == 1 and out.startswith("PROVED-UNDER")
strict = (code, out)

# %% [markdown]
# Same verdict text, exit 1. And `--strict-proved` leaves a real `PROVED` alone:

# %%
code, out = _show.run("check", TUT / "plain.qasm", "--contract", "ibm_heron", "--strict-proved")
assert code == 0 and out.startswith("PROVED ")

# %% [markdown]
# ### Changing the assumption changes the verdict
# `--assume ff.default=LO:HI` overrides the latency for one run (always class `vendor`, and recorded in the report). The deadline in `tp_basic` is 3000 ns, so a much slower feed-forward should break it. The 4000 ns here is illustrative, not a vendor value.

# %%
code, out = _show.run("check", FAM / "teleportation/tp_basic.qasm", "--contract", "ibm_heron",
                      "--assume", "ff.default=0:4000")
assert code == 1 and out.startswith("REFUTED")

# %% [markdown]
# ## 3. REFUTED: a concrete counterexample
# `tp_sync` demands that the idle gap on `q2` not vary with the outcome. It does vary, by 2 ns.

# %%
code, out = _show.run("check", FAM / "teleportation/tp_sync.qasm", "--contract", "ibm_heron")
assert code == 1 and out.startswith("REFUTED") and "second execution" in out
refuted = (code, out)

# %%
_show.report_svg(FAM / "teleportation/tp_sync.qasm", "ibm_heron")

# %% [markdown]
# The two timelines are the counterexample (the report text above prints both). Every REFUTED is replayed in an independent executor before it is reported; see [tutorial 01](01-first-verdict.md).

# %% [markdown]
# ## 4. UNKNOWN: the tool will not guess
# Same program, but with the SMT solver (tier 2) switched off. Tier 1 can only prove, never refute, so the one obligation it cannot prove stays undecided.

# %%
code, out = _show.run("check", FAM / "teleportation/tp_sync.qasm", "--contract", "ibm_heron", "--no-tier2")
assert code == 3 and out.startswith("UNKNOWN") and "Tier 2 is disabled" in out
unknown = (code, out)

# %% [markdown]
# Exit 3 is neither pass nor fail. Treat it as "not checked". More reasons for UNKNOWN show up on ARTIQ.

# %% [markdown]
# ## ARTIQ: how absent numbers play out
# The `artiq` contract publishes no gate durations, no commit lead and no upper bound for `in2cpu`. Without durations the run stops with an error (exit 2). The programs are synthetic, written by the qtiming authors, not ARTIQ code, and every number I assume below is illustrative.

# %%
prog = FAM / "artiq/artiq_reset_fb.qasm"
_show.source(prog)

# %%
D = ["--assume", "durations.x=100", "--assume", "durations.measure=1000", "--assume", "durations.h=50"]
code, out = _show.run("check", prog, "--contract", "artiq")
assert code == 2 and "E-CT-MISSING" in out

# %% [markdown]
# Supply durations: now the commit lead is the missing number.

# %%
code, out = _show.run("check", prog, "--contract", "artiq", *D)
assert code == 3 and "missing contract field: timeline.commit_lead" in out
a1 = (code, out)

# %% [markdown]
# Supply the commit lead too: the `in2cpu` latency has no upper bound, so the counterexample needs an unbounded latency, and that is UNKNOWN, never REFUTED.

# %%
L = [*D, "--assume", "timeline.commit_lead=200"]
code, out = _show.run("check", prog, "--contract", "artiq", *L)
assert code == 3 and "fails if in2cpu is large enough" in out
a2 = (code, out)

# %% [markdown]
# Bound `in2cpu` at 300 ns. O1 is now proved (tier 1, margin 300 ns), but the verdict is still UNKNOWN: the symbolic encoding of O5 is not built, and this build says so instead of dropping the obligation.

# %%
code, out = _show.run("check", prog, "--contract", "artiq", *L, "--assume", "in2cpu=0:300")
assert code == 3 and "O1: 1 obligation(s): proved" in out and "Tier 2 does not encode Events (O5)" in out
a3 = (code, out)

# %% [markdown]
# Allow `in2cpu` up to 2000 ns: the result is now REFUTED for O1, even though O5 is still unknown (REFUTED outranks UNKNOWN).

# %%
code, out = _show.run("check", prog, "--contract", "artiq", *L, "--assume", "in2cpu=0:2000")
assert code == 1 and out.startswith("REFUTED") and "O5: 1 obligation(s): unknown" in out
a4 = (code, out)

# %% [markdown]
# ## All results side by side

# %%
card([
    ("plain.qasm, ibm_heron", *proved),
    ("tp_basic, ibm_heron", *under),
    ("tp_basic, ibm_heron, --strict-proved", *strict),
    ("tp_sync, ibm_heron", *refuted),
    ("tp_sync, ibm_heron, --no-tier2", *unknown),
    ("artiq_reset_fb, no commit_lead", *a1),
    ("artiq_reset_fb, in2cpu unbounded", *a2),
    ("artiq_reset_fb, in2cpu 0:300", *a3),
    ("artiq_reset_fb, in2cpu 0:2000", *a4),
])

# %% [markdown]
# ## What just happened
# - The verdict is the weakest obligation result: `REFUTED` > `UNKNOWN` > `PROVED-UNDER` > `PROVED`.
# - `PROVED` needs no latency-dependent obligation; `PROVED-UNDER` lists every assumption it used, with its evidence class.
# - `--strict-proved` only changes the exit code of `PROVED-UNDER` (0 to 1).
# - `UNKNOWN` means a missing number, an unbounded latency, a disabled tier, or an unbuilt encoding. It is never silently turned into a pass.
# - All ARTIQ results here depend on illustrative `--assume` numbers, not published ARTIQ values.
#
# Next: [Policies](03-policies.md).
