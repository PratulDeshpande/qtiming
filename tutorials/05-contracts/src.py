# %% [markdown]
# # Contracts are claims
#
# **Question:** where do the numbers behind a verdict come from, and what happens when I change them?
#
# A *contract* is a TOML file of hardware timing numbers. qtiming uses only what it states. Every latency carries an evidence class and a source string; a number the contract leaves out is *absent*, never guessed. Reference: [Contracts](../contracts.md), [Reading a verdict](../verdicts.md), [Errors](../errors.md).

# %%
# hide
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent))
import _show

# %%
TP = _show.FAMILIES / "teleportation/tp_basic.qasm"

# %% [markdown]
# ## The program
# The same teleportation as in tutorial 01: the correction must start within 3000 ns of the measurement result arriving.

# %%
_show.source("teleportation/tp_basic.qasm")

# %% [markdown]
# ## 1. Inspect: `contract show`
# Durations and latencies are printed in dt (IBM dt is 4 ns). The one IBM latency is `ff.default`, 150 dt = 600 ns, class `vendor`: IBM's public "about 600 ns" claim. Gate durations here come from an *unofficial offline snapshot*, a fixture, not a live backend.

# %%
code, out = _show.run("contract", "show", "ibm_heron")
shown = json.loads(out.rsplit("[exit", 1)[0])
assert code == 0 and shown["latencies"]["ff.default"] == [0, 150, "vendor"] and shown["missing"] == []

# %% [markdown]
# ## 2. Validate and see what is absent
# `validate` reports `missing` fields. ARTIQ's contract has no `commit_lead` and no upper bound for `in2cpu`, and no stack except IBM ships gate durations. These are left absent on purpose.

# %%
inst = "src/qtiming/contract/instances"
code, out = _show.run("contract", "validate", *[f"{inst}/{n}.toml" for n in ("ibm_heron", "q1", "artiq", "qua")])
assert code == 0 and "missing: timeline.commit_lead" in out and "placeholders=3" in out

# %% [markdown]
# ## 3. Absent means stop or UNKNOWN, not a guess
# Without gate durations the three non-IBM stacks refuse to run `tp_basic`:

# %%
for c in ("artiq", "q1", "qua"):
    code, out = _show.run("check", TP, "--contract", c)
    assert code == 2 and "E-CT-MISSING" in out

# %% [markdown]
# ## 4. `--assume`: supply a number for one run
# `--assume durations.NAME=NS` supplies a gate duration. **These numbers are illustrative, not vendor values** (the report says so with `note: contract assumed value`). With them each stack gives its own answer for the *same* program:

# %%
DUR = ["--assume", "durations.h=32", "--assume", "durations.cx=200",
       "--assume", "durations.measure=1000", "--assume", "durations.x=32"]
code, out = _show.run("check", TP, "--contract", "qua", *DUR)
assert code == 0 and out.startswith("PROVED-UNDER") and "active_reset" in out

# %% [markdown]
# QUA is PROVED-UNDER its vendor claim for `active_reset`. ARTIQ has no `commit_lead`, so an obligation that needs it is UNKNOWN and the `why:` line names the key:

# %%
code, out = _show.run("check", TP, "--contract", "artiq", *DUR)
assert code == 3 and out.startswith("UNKNOWN") and "timeline.commit_lead" in out

# %% [markdown]
# Supply `commit_lead` (illustrative, 200 ns) and a bound for `in2cpu` (`KEY=LO:HI`) and ARTIQ now *refutes*: an RTIO event is committed too late. The `short by` figures come from the invented numbers, so read this as "if the lead were 200 ns", not as a fact about ARTIQ. O5 stays UNKNOWN because the symbolic encoding is not built.

# %%
code, out = _show.run("check", TP, "--contract", "artiq", *DUR,
                      "--assume", "timeline.commit_lead=200", "--assume", "in2cpu=0:300")
assert code == 1 and out.startswith("REFUTED") and "short by 200 ns" in out and "unknown (tier -)" in out

# %% [markdown]
# Q1 is predicated, and `tp_basic` has an `x` arm and an empty `else` arm. With a 32 ns `x` the two arms cannot be equalised, and the elaborator says so. Only when `x` is one RT instruction (4 ns, again illustrative) are the arms the same length:

# %%
code, out = _show.run("check", TP, "--contract", "q1", *DUR)
assert code == 2 and "E-ELAB-Q1-NOT-EQUALISABLE" in out
Q1 = ["--assume", "durations.h=32", "--assume", "durations.cx=200",
      "--assume", "durations.measure=1000", "--assume", "durations.x=4"]
code, out = _show.run("check", TP, "--contract", "q1", *Q1)
assert code == 0 and out.startswith("PROVED-UNDER") and "trigger.network" in out

# %% [markdown]
# ## 5. Guard rails on what `--assume` may do
# An assumption can only be class `vendor`, so a typed number can never make a verdict PROVED. And an assumption cannot silently override the Target: the snapshot says `h` is 32 ns, so `durations.h=40` is a conflict, not an override.

# %%
code, out = _show.run("contract", "validate", f"{inst}/ibm_heron.toml", "--assume", "ff.default=0:600:cyc")
assert code == 1 and "E-CT-ASSUME" in out
code, out = _show.run("contract", "validate", f"{inst}/ibm_heron.toml", "--assume", "durations.h=40")
assert code == 1 and "E-CT-TARGET-CONFLICT" in out

# %% [markdown]
# ## 6. Compare: `contract diff`
# Exit 1 means the contracts differ. The IBM numbers are dt-denominated from the snapshot; QUA has none.

# %%
code, out = _show.run("contract", "diff", "ibm_heron", "qua")
assert code == 1 and "personality: 'ibm' -> 'qua'" in out

# %% [markdown]
# ## 7. Sweep the claim: where does the verdict flip?
# The only IBM latency is a vendor claim of at most 600 ns. What if it were larger? `--assume ff.default=0:N` re-runs the check with upper bound N. The program's deadline is 3000 ns.

# %%
NS = [200, 600, 1000, 1500, 2000, 2500, 2900, 3000, 3004, 3100, 3500, 4000]
rows = []
for n in NS:
    _, out = _show.run("check", TP, "--contract", "ibm_heron", "--assume", f"ff.default=0:{n}", show=False)
    m = re.search(r"O3: .*?margin (-?\d+) ns", out)
    rows.append((n, out.split()[0], int(m.group(1)) if m else None))
print("ff upper bound (ns)  verdict        O3 margin (ns)")
for n, v, g in rows:
    print(f"{n:>19}  {v:<13}  {'' if g is None else g}")
flip = [n for n, v, _ in rows if v == "REFUTED"]
assert all(v == "PROVED-UNDER" for n, v, _ in rows if n <= 3000)
assert min(flip) == 3004 and dict((n, g) for n, _, g in rows)[3000] == 0

# %% [markdown]
# The same data drawn: blue dots are PROVED-UNDER and sit on the O3 margin line, which falls one nanosecond per nanosecond until it hits zero at the deadline. Crosses on the bottom row are REFUTED.

# %%
# hide-input
W, H, L, R, T, B = 620, 220, 60, 24, 20, 50  # fits the 622px reading column
xs = lambda n: L + (W - L - R) * n / 4000
ys = lambda g: T + (H - T - B) * (1 - g / 3000)
pts = [(n, g) for n, _, g in rows if g is not None]
line = " ".join(f"{xs(n):.1f},{ys(g):.1f}" for n, g in pts)
INK, BLUE, MUTED = "#111418", "#0B5FA5", "#4A5563"  # docs theme tokens


def mark(n, v, g):
    x = xs(n)
    if v == "REFUTED":  # a cross, not just a colour, on its own labelled row
        y = H - B + 14
        return (f'<path d="M{x-4:.1f},{y-4} l8,8 m0,-8 l-8,8" stroke="{INK}" stroke-width="2">'
                f'<title>{n} ns: {v}</title></path>')
    return f'<circle cx="{x:.1f}" cy="{ys(g):.1f}" r="4.5" fill="{BLUE}"><title>{n} ns: {v}</title></circle>'


dots = "".join(mark(n, v, g) for n, v, g in rows)
ticks = "".join(
    f'<text x="{xs(n):.1f}" y="{H - B + 36}" font-size="11" text-anchor="middle">{n}</text>'
    for n in (0, 1000, 2000, 3000, 4000))
svg = (
    f'<svg viewBox="0 0 {W} {H}" width="{W}" role="img" aria-label="O3 margin against the assumed feed-forward '
    f'upper bound: PROVED-UNDER up to 3000 ns with the margin falling to 0, REFUTED from 3004 ns">'
    f'<line x1="{L}" y1="{H - B}" x2="{W - R}" y2="{H - B}" stroke="{INK}"/>'
    f'<line x1="{xs(3000):.1f}" y1="{T}" x2="{xs(3000):.1f}" y2="{H - B}" stroke="{INK}" stroke-dasharray="4"/>'
    f'<text x="{xs(3000) + 4:.1f}" y="{T + 10}" font-size="11">deadline 3000 ns</text>'
    f'<line x1="{xs(600):.1f}" y1="{T}" x2="{xs(600):.1f}" y2="{H - B}" stroke="{MUTED}" stroke-dasharray="2"/>'
    f'<text x="{xs(600) + 4:.1f}" y="{T + 10}" font-size="11" fill="{MUTED}">vendor claim 600 ns</text>'
    f'<polyline points="{line}" fill="none" stroke="{BLUE}" stroke-width="1.5"/>{dots}{ticks}'
    f'<text x="{L - 8}" y="{ys(3000) + 4:.1f}" font-size="11" text-anchor="end">3000</text>'
    f'<text x="{L - 8}" y="{ys(0) + 4:.1f}" font-size="11" text-anchor="end">0</text>'
    f'<text x="{L - 8}" y="{H - B + 18}" font-size="11" text-anchor="end">refuted</text>'
    f'<text x="{(L + W - R) / 2}" y="{H - 4}" font-size="12" text-anchor="middle">'
    f'assumed ff.default upper bound (ns); line = O3 margin (ns)</text></svg>')
_show.figure(svg)

# %% [markdown]
# ## 8. `--max-safe`: ask for the flip point directly
# Instead of sweeping, bisect. The answer must equal the largest bound the sweep still proved.

# %%
code, out = _show.run("check", TP, "--contract", "ibm_heron", "--max-safe", "ff.default")
assert code == 0 and "max safe ff.default.hi: 750 dt = 3000 ns" in out

# %% [markdown]
# ## What just happened
# - A contract is a set of claims, each with an evidence class and a source. `show`, `validate` and `diff` expose them.
# - Absent numbers stop the run (`E-CT-MISSING`) or make the dependent obligation UNKNOWN. Nothing is filled in.
# - `--assume` is a vendor-class, per-run override. It cannot raise a verdict to PROVED and cannot contradict the Target (`E-CT-TARGET-CONFLICT`). The numbers used for ARTIQ, Q1 and the durations are illustrative.
# - The verdict flips from PROVED-UNDER to REFUTED exactly past the deadline, and `--max-safe` finds that point without a sweep. The 600 ns is a vendor claim: the proof is only as good as it.
#
# Previous: [The four verdicts](02-four-verdicts.md).
