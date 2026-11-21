# %% [markdown]
# # Why timing breaks dynamic circuits
#
# A dynamic circuit measures a qubit mid-circuit, sends the result to classical hardware, and then picks
# what to run next. The quantum part is fast and the classical part is slow and **not the same length every
# time**. Other qubits keep idling and decohering while they wait, so *when* things happen is part of
# whether the program is correct. qtiming checks that statically, against a **timing contract** that
# records what each controller stack promises.

# %%
# hide
#!pip install qtiming

# %%
# hide
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent))
import _show

# %% [markdown]
# ## The problem in one picture
# One qubit is measured. If the result is 1, a correction is applied to another qubit. The result takes
# between *a* and *b* nanoseconds to reach the control logic, so the correction lands at a different time
# on every shot. The bar is a sketch (not to scale, not a measurement).

# %%
# hide-input
_show.figure('''<svg viewBox="0 0 600 160" width="600" role="img" aria-label="Sketch: qubit q0 is measured; the result reaches the controller after a feed-forward latency of a to b ns; the correction x on q2 starts when it arrives, so q2 idles anywhere from the best-case to the worst-case length" font-size="12">
<line x1="40" y1="40" x2="580" y2="40" stroke="#111418"/><text x="4" y="44">q0</text>
<line x1="40" y1="100" x2="580" y2="100" stroke="#111418"/><text x="4" y="104">q2</text>
<rect x="56" y="28" width="74" height="24" fill="#EAF2FA" stroke="#0B5FA5"/><text x="93" y="44" text-anchor="middle">measure</text>
<rect x="130" y="62" width="220" height="16" fill="#F4F6F9" stroke="#4A5563" stroke-dasharray="4 3"/><text x="240" y="74" text-anchor="middle">feed-forward latency: a to b ns</text>
<rect x="350" y="88" width="64" height="24" fill="#111418"/><text x="382" y="104" text-anchor="middle" fill="#fff">x if c</text>
<rect x="130" y="124" width="90" height="10" fill="#0B5FA5"/><text x="228" y="133">best case: q2 idles this long</text>
<rect x="130" y="142" width="220" height="10" fill="#EAF2FA" stroke="#0B5FA5"/><text x="358" y="151">worst case: until the correction lands</text>
</svg>''')

# %% [markdown]
# ## What the tool answers
# Given a program and a contract, `check` returns one of four verdicts (see [Reading a verdict](../verdicts.md)):
#
# | Verdict | Meaning |
# |---|---|
# | **PROVED** | holds with no assumptions |
# | **PROVED-UNDER** | holds *if* the listed assumptions hold (for example a vendor-claimed latency) |
# | **REFUTED** | a concrete counterexample, replayed in an independent executor |
# | **UNKNOWN** | not decided; the reason is stated (often a number the contract leaves absent) |

# %% [markdown]
# ## Four stacks, four timing models
# Each stack handles the classical side differently, which is why one program can get four different outcomes
# ([Same circuit, four stacks](06-four-stacks.md), [compare page](compare.md)). The statements below were read
# on the cited vendor pages on 2026-11-22; the full list with quotes is in
# [sources.md](https://github.com/PratulDeshpande/QTiming/blob/main/tutorials/00-why-timing/sources.md).
# Vendor figures are **claims, not certified bounds**.
#
# - **IBM Heron:** the [IBM Quantum blog (19 Nov 2025)](https://www.ibm.com/quantum/blog/utility-scale-dynamic-circuits)
#   puts feed-forward latency "around ~600ns" and says Qiskit cannot reliably model the execution time of
#   the classical operations involved, which is why `stretch` lets users state timing intent.
# - **Qblox Q1:** the [trigger network](https://docs.qblox.com/en/main/products/architecture/sequencers/trigger_handling.html)
#   delivers a trigger to all sequencers after a documented latency (212 to 239 ns on the page's figure); only
#   one trigger can be on the backplane at a time, and a skipped conditional instruction stalls the real-time
#   pipeline for a set wait.
# - **ARTIQ:** events are queued and fired at timestamps; if an [event cannot be released in time](https://m-labs.hk/artiq/manual/rtio.html)
#   it is not fired and the kernel raises `RTIOUnderflow`. Slack is the gap between the timeline cursor and the wall clock.
# - **Quantum Machines QUA:** [`align()`](https://docs.quantum-machines.co/1.1.7/qm-qua-sdk/docs/Guides/timing_in_qua/) makes
#   later operations wait for earlier ones. With compile-time durations the compiler inserts exact waits; with run-time
#   durations a gap of a few cycles can form.

# %% [markdown]
# ## The contract records these as claims
# The shipped contracts keep the number, its provenance class and its source string. Here is the IBM
# feed-forward latency: the `vendor` class is the weakest, which is why the verdict is PROVED-UNDER and not PROVED.

# %%
code, out = _show.run("contract", "show", "ibm_heron", show=False)
ff = json.loads(out)["latencies"]["ff.default"]
print("ff.default =", ff)
assert code == 0 and ff[2] == "vendor"

# %% [markdown]
# Where a number is not published, the contract leaves it absent and the dependent check comes out UNKNOWN
# rather than guessed. ARTIQ's `timeline.commit_lead` is such a case:

# %%
code, out = _show.run("contract", "show", "artiq", show=False)
art = json.loads(out)
print("missing:", art["missing"])
assert "timeline.commit_lead" in art["missing"]

# %% [markdown]
# ## What just happened
# - Timing correctness depends on uncertain classical latencies, so qtiming reasons over ranges.
# - Each stack's range is a documented claim with a provenance class; absent numbers stay absent.
# - Next: [Your first verdict](01-first-verdict.md).
