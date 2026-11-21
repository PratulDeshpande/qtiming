# %% [markdown]
# # Automatic repair
#
# **Question:** qtiming says my ARTIQ program is REFUTED. Can it fix it for me, and can I trust the fix?
#
# `qtiming repair` proposes a patch for one kind of failure only: **O1**, the commit-lead (RTIO underflow) obligation. It inserts a declared `delay`, then **re-verifies** the patched program with the normal pipeline before showing it. It refuses O3 (deadlines). Reference: [Command reference](../cli.md), [Obligations](../obligations.md).

# %%
# hide
import difflib, json, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent))
import _show

# %% [markdown]
# ## The program and the numbers you have to supply
# `artiq_burst` fires four `x` gates back to back, then measures. It is a synthetic kernel written for this repo, not ARTIQ project code.

# %%
_show.source("artiq/artiq_burst.qasm")

# %% [markdown]
# The shipped `artiq` contract leaves `timeline.commit_lead`, gate durations and the `in2cpu` upper bound **absent**, because ARTIQ publishes no numbers for them. Without them `check` stops with a usage error, not a guess:

# %%
BURST = _show.FAMILIES / "artiq/artiq_burst.qasm"
SLACK = _show.FAMILIES / "artiq/artiq_slack_neg.qasm"
code, out = _show.run("check", BURST, "--contract", "artiq")
assert code == 2 and "E-CT-MISSING" in out

# %% [markdown]
# So they are supplied with `--assume`. **These values are illustrative, not ARTIQ numbers**: 32 ns per `x`, 1000 ns measurement, `commit_lead` 100 ns, `in2cpu` 0 to 300 ns. Every one is recorded as an assumption in the report.

# %%
A = ["durations.x=32", "durations.measure=1000", "timeline.commit_lead=100", "in2cpu=0:300"]
ASSUME = [x for a in A for x in ("--assume", a)]

# %% [markdown]
# ## 1. Before: REFUTED
# Each `x` is issued back to back, so the CPU is behind the timeline. The shortfall against the 100 ns commit lead is 100, 68, 36 and 4 ns for the four gates.

# %%
code, out = _show.run("check", BURST, "--contract", "artiq", *ASSUME)
assert code == 1 and out.startswith("REFUTED")
for s in ("short by 100 ns", "short by 68 ns", "short by 36 ns", "short by 4 ns"):
    assert s in out

# %% [markdown]
# This verdict has no timeline picture: the HTML report for it contains no timeline, only the per-obligation shortfalls above.

# %% [markdown]
# ## 2. `repair`
# `--out` sends the repair summary to a file (here a temporary directory, never the repo); `--verbose` prints the patched program's verdict on screen.

# %%
with tempfile.TemporaryDirectory() as d:
    summary = Path(d) / "repair.txt"
    code, out = _show.run("repair", BURST, "--contract", "artiq", *ASSUME, "--out", summary, "--verbose")
    saved = summary.read_text(encoding="utf-8")
print("--- contents of the --out file ---")
print(saved.rstrip())
assert "before: REFUTED  after: UNKNOWN" in saved
assert "insert before line 7:  delay[100ns] $0;  (100 dt)" in saved
assert code == 3 and out.startswith("UNKNOWN")

# %% [markdown]
# The patch is one declared delay of exactly the largest shortfall, 100 ns, before the first `x`. The **after** verdict is UNKNOWN, not PROVED, and the exit code is 3. In the patched verdict above all five O1 obligations are proved, and the only open item is **O5, which this build does not encode yet** (`Tier 2 does not encode Events (O5) yet`). qtiming reports that honestly instead of calling the patch proved.

# %% [markdown]
# ## 3. The patch as a diff
# `repair` prints the hunk; it does not write patched QASM. Applying the hunk by hand (`$0` is `q[0]`) gives the diff below, and checking that hand-patched file gives the same verdict as the one `repair` re-verified.

# %%
src = BURST.read_text(encoding="utf-8").splitlines()
i = next(n for n, ln in enumerate(src) if ln.startswith("x q[0]"))
new = src[:i] + ["delay[100ns] q[0];"] + src[i:]
print("\n".join(difflib.unified_diff(src, new, "artiq_burst.qasm", "artiq_burst.patched.qasm", lineterm="", n=1)))
with tempfile.TemporaryDirectory() as d:
    p = Path(d) / "burst_patched.qasm"
    p.write_text("\n".join(new) + "\n", encoding="utf-8")
    code, out = _show.run("check", p, "--contract", "artiq", *ASSUME, show=False)
    for ln in out.splitlines():
        if ln.startswith(("UNKNOWN", "REFUTED", "  O1:", "  why:")):
            print(ln.split("  (")[0] if ln[0] != " " else ln)
    assert out.startswith("UNKNOWN") and "O5" in out and "refuted" not in out
    _show.report_svg(p, "artiq", *A)

# %% [markdown]
# The picture is the patched program's report (a typical run, as the report labels it). The text report above it shows the patched O1 margins: 0, 32, 64, 96 ns, none negative.

# %% [markdown]
# ## 4. When it will not patch: `artiq_slack_neg`
# Here the feedback is issued right after the measurement with no slack. With `in2cpu` bounded at 0 to 300 ns, `check` refutes O1 (found by the Tier 2 solver, which needs the `z3` extra).

# %%
code, out = _show.run("check", SLACK, "--contract", "artiq", *ASSUME)
assert code == 1 and out.startswith("REFUTED") and "O1 failed" in out

# %%
code, out = _show.run("repair", SLACK, "--contract", "artiq", *ASSUME)
assert code == 1 and "unsupported: no automatic patch for O1" in out

# %% [markdown]
# `repair` gives up. Its search only pads shortfalls it can compute exactly (Tier 0 counterexamples with a fixed `short by N ns`); this one comes from the solver and depends on the `in2cpu` range, so there is no exact number to pad. This build reports "no automatic patch" for this case, and the page shows that as it is. Without the `in2cpu` bound the verdict is not even REFUTED:

# %%
NOIN = ["--assume", "durations.x=32", "--assume", "durations.measure=1000",
        "--assume", "timeline.commit_lead=100"]
code, out = _show.run("check", SLACK, "--contract", "artiq", *NOIN)
assert code == 3 and out.startswith("UNKNOWN") and "fails if in2cpu is large enough" in out
code, out = _show.run("repair", SLACK, "--contract", "artiq", *NOIN)
assert code == 3 and "before: UNKNOWN  after: UNKNOWN" in out

# %% [markdown]
# `repair` needs a REFUTED program; an UNKNOWN one comes back unchanged (exit 3).

# %% [markdown]
# ## 5. O3 is refused on purpose
# A deadline (`@timing.within`) fails when the work starts too *late*, and a delay makes that worse. The O3 refusal needs a program with a deadline, so this one uses IBM's `tp_basic` (3000 ns deadline) with an assumed, illustrative 0 to 5000 ns feed-forward latency. The plan lists ARTIQ only for this tutorial; this is the one place it uses `ibm_heron`.

# %%
TP = _show.FAMILIES / "teleportation/tp_basic.qasm"
code, out = _show.run("check", TP, "--contract", "ibm_heron", "--assume", "ff.default=0:5000")
assert code == 1 and "O3 failed" in out

# %%
code, out = _show.run("repair", TP, "--contract", "ibm_heron", "--assume", "ff.default=0:5000")
assert code == 1 and "unsupported: O3 (deadline): a delay makes it worse" in out
assert "before: REFUTED  after: REFUTED" in out

# %% [markdown]
# ## What just happened
# - `repair` fixed `artiq_burst`: one inserted 100 ns delay, re-verified by the full pipeline. The result is UNKNOWN only because O5 is not encoded in this build; no O1 obligation is left failing.
# - It declined `artiq_slack_neg` (solver-found O1 failure, no exact shortfall) and `tp_basic` (O3: a delay would worsen it), and said why.
# - Every number on the ARTIQ side was supplied by `--assume` and is illustrative, not vendor data.
#
# See also [Command reference](../cli.md) and [Obligations](../obligations.md).
