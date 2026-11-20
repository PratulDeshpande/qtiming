"""Write the benchmark programs of plan 17.1 to `benchmarks/families/<family>/<name>.qasm`.

    python benchmarks/gen_families.py            # (re)write the files and each <family>/meta.json
    python benchmarks/gen_families.py --check    # exit 1 if the files on disk differ

Deterministic: no randomness, no clock, so two runs give identical bytes. The four teleportation
programs written in P7 (tp_basic, tp_exp, tp_q1, tp_sync) are not generated: they are kept as they
are and only listed in the family's meta.json.

Every program is written by the qtiming authors (Apache-2.0). None is external code. Programs
use only gates the shipped IBM snapshot has a duration for (x, sx, h, z, cx, cz, measure, reset),
because the other three shipped contracts publish no gate durations (cells there come out
`unsupported`; see benchmarks/README.md).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent / "families"
LICENCE = "Apache-2.0"
PROVENANCE = "written by qtiming authors"
Prog = dict[str, Any]
FAMILIES: dict[str, dict[str, Prog]] = {}


def add(family: str, name: str, why: str, obligations: list[str], body: str, *, header: str = "",
        notes: str = "", nq: int = 3, nc: int = 2, windowed: bool = False) -> None:
    text = (f"OPENQASM 3.0;\n// {name}: {why}\n"
            + (f"// {header}\n" if header else "")
            + f"qubit[{nq}] q;\nbit[{nc}] c;\n\n{body.strip()}\n")
    FAMILIES.setdefault(family, {})[name] = {
        "family": family, "why": why, "main_obligations": obligations,
        "provenance": PROVENANCE, "licence": LICENCE, "notes": notes,
        "needs_windowing": windowed, "text": text}


def rep(n: int, body: str) -> str:
    """A `for` loop of n rounds whose body is delimited by full barriers (a legal window)."""
    return f"for int i in [0:{n - 1}] {{\nbarrier q;\n{body.strip()}\nbarrier q;\n}}"


# ------------------------------------------------------------ teleportation (2 new of 6)
_BELL = ("h q[1];\ncx q[1], q[2];\ncx q[0], q[1];\nh q[0];\nc[0] = measure q[0];\n"
         "c[1] = measure q[1];")
add("teleportation", "tp_gate_xz",
    "gate teleportation: both Pauli corrections (X on c[1], Z on c[0]) as two conditionals",
    ["O2a", "O3", "O4"],
    _BELL + "\nif (c[1]) {\n    x q[2];\n}\nif (c[0]) {\n    z q[2];\n}",
    notes="Unannotated: the policy comes from `--policies`; EQ pads each arm, SYNC leaves an "
          "outcome-dependent gap.")
add("teleportation", "tp_gate_parity",
    "gate teleportation with a parity-controlled correction (c[0] xor c[1]) inside a within box",
    ["O2a", "O3", "O4"],
    _BELL + "\n@timing.within 3000ns c[1]\nbox {\n    if (c[0] ^ c[1]) {\n        z q[2];\n"
            "    }\n}",
    notes="Derived condition (xor) exercises the label algebra; the 3000 ns deadline is generous.")

# ------------------------------------------------------------ active reset (4)
add("active_reset", "reset_basic", "simplest conditional: measure, flip if 1",
    ["O2a", "O4"], "c[0] = measure q[0];\nif (c[0]) {\n    x q[0];\n}", nq=1, nc=1)
add("active_reset", "reset_parallel", "two qubits reset in parallel from independent results",
    ["O2a", "O4"],
    "c[0] = measure q[0];\nc[1] = measure q[1];\nif (c[0]) {\n    x q[0];\n}\nif (c[1]) {\n"
    "    x q[1];\n}", nq=2)
add("active_reset", "reset_twice",
    "two rounds of active reset on one qubit (the second result reads a fresh bit)",
    ["O2a", "O4"],
    "c[0] = measure q[0];\nif (c[0]) {\n    x q[0];\n}\nc[1] = measure q[0];\nif (c[1]) {\n"
    "    x q[0];\n}", nq=1)
add("active_reset", "reset_within_tight",
    "reset with a 300 ns deadline: tighter than the vendor 600 ns feedforward claim",
    ["O3", "O2a"],
    "c[0] = measure q[0];\n@timing.within 300ns c[0]\nbox {\n    if (c[0]) {\n        x q[0];\n"
    "    }\n}", nq=1, nc=1,
    notes="Intended UNSAFE on IBM: the vendor upper bound (600 ns) exceeds the deadline.")


# ------------------------------------------------------------ long-range CNOT / GHZ (8)
def lrcnot(hops: int) -> str:
    """Bell pairs on (q1,q2), (q3,q4), ... entangled in a chain, all inner qubits measured; the
    corrections are parities of the measured bits (a wide join, plan 17.1). A toy: it has the
    timing shape of the protocol, not a verified circuit."""
    n = 2 * hops + 2
    lines = ["h q[1];", "cx q[1], q[2];"]
    for a in range(3, n - 1, 2):
        lines += [f"h q[{a}];", f"cx q[{a}], q[{a + 1}];"]
    lines += ["cx q[0], q[1];"]
    lines += [f"cx q[{a}], q[{a + 1}];" for a in range(2, n - 1, 2)]
    lines += [f"c[{a - 1}] = measure q[{a}];" for a in range(1, n - 1)]
    px = " ^ ".join(f"c[{a}]" for a in range(0, n - 2, 2))
    pz = " ^ ".join(f"c[{a}]" for a in range(1, n - 2, 2))
    lines += [f"if ({px}) {{\n    x q[{n - 1}];\n}}", f"if ({pz}) {{\n    z q[0];\n}}"]
    return "\n".join(lines)


for hops in (1, 2, 3, 4):
    n = 2 * hops + 2
    add("long_range_cnot", f"lrcnot_h{hops}",
        f"long-range CNOT over {hops} Bell-pair hop(s): parity corrections over {n - 2} bits",
        ["O4", "O7"], lrcnot(hops), nq=n, nc=n - 2,
        notes="Wide join: each correction depends on the xor of several outcomes. Toy circuit.")


def ghz(n: int, fan: bool) -> str:
    lines = ["h q[0];"] + [f"cx q[0], q[{i}];" for i in range(1, n)]
    meas = [f"c[{i // 2}] = measure q[{i}];" for i in range(1, n, 2)]
    ks = range(len(meas))
    if fan:  # many parallel single-bit conditionals on distinct qubits
        cond = [f"if (c[{k}]) {{\n    z q[{2 * k + 2}];\n}}" for k in ks if 2 * k + 2 < n]
    else:  # one parity conditional over every bit
        cond = [f"if ({' ^ '.join(f'c[{k}]' for k in ks)}) {{\n    z q[0];\n}}"]
    return "\n".join(lines + meas + cond)


for n, fan, name in ((4, False, "ghz_parity_4"), (6, False, "ghz_parity_6"),
                     (5, True, "ghz_fan_5"), (7, True, "ghz_fan_7")):
    add("long_range_cnot", name,
        f"{n}-qubit GHZ built with CNOTs, odd qubits measured, "
        + ("many parallel conditionals" if fan else "one wide parity conditional"),
        ["O4", "O7"], ghz(n, fan), nq=n, nc=n // 2,
        notes="Measurement-based GHZ clean-up, simplified: not a validated physical protocol; "
              "it exists to produce wide joins and many parallel branches.")

# ------------------------------------------------------------ repeat-until-success (8)
RUS_NOTE = ("`while` needs a timing.cap box. The IBM contract has allow_loops = false, so the "
            "`while` forms come out `unsupported` there (E-GRAPH-UNSUPPORTED); exhaust handlers "
            "(`timing.cap` labels) are not implemented in the front end, so the exhaust is empty.")


def rus_while(cap: int, ann: str = "") -> str:
    return (f"c[0] = measure q[0];\n@timing.cap {cap}\n{ann}box {{\n"
            "    while (c[0]) {\n        x q[1];\n        h q[0];\n"
            "        c[0] = measure q[0];\n    }\n}")


for cap in (2, 4, 8, 16):
    add("rus", f"rus_while_cap{cap}", f"repeat-until-success loop, capped at {cap} attempts",
        ["O9", "O3"], rus_while(cap), nq=2, nc=1, notes=RUS_NOTE)
add("rus", "rus_while_policy_sync", "RUS loop with an explicit SYNC policy on the loop",
    ["O9", "O4"], rus_while(4, "@timing.policy sync\n"), nq=2, nc=1, notes=RUS_NOTE)
add("rus", "rus_while_policy_eq", "RUS loop with an explicit EQ policy on the loop",
    ["O9", "O4"], rus_while(4, "@timing.policy eq\n"), nq=2, nc=1, notes=RUS_NOTE)
for k in (3, 5):
    add("rus", f"rus_unrolled_{k}",
        f"IBM-expressible approximation: {k} fixed attempts as a `for` loop with a conditional "
        "retry (no `while`)", ["O2a", "O4"],
        rep(k, "c[0] = measure q[0];\nif (c[0]) {\n    x q[1];\n    h q[0];\n}"), nq=2, nc=1,
        notes="LIMITATION: not a true RUS loop. The retry gate runs once per attempt whether or "
              "not an earlier attempt succeeded, so the success path is over-approximated. "
              "Recorded because IBM forbids loops with a data-dependent exit.")


# ------------------------------------------------------------ QEC (12)
def repetition_round(d: int) -> str:
    """Z-type syndromes of a distance-d repetition code (d-1 ancillas) and a toy lookup decoder
    (single or two-bit rules, not a full majority vote)."""
    lines = []
    for a in range(d - 1):
        lines += [f"cx q[{a}], q[{d + a}];", f"cx q[{a + 1}], q[{d + a}];"]
    lines += [f"c[{a}] = measure q[{d + a}];" for a in range(d - 1)]
    lines += ["if (c[0] && !c[1]) {\n    x q[0];\n}"]
    lines += [f"if (c[{a - 1}] && c[{a}]) {{\n    x q[{a}];\n}}" for a in range(1, d - 1)]
    lines += [f"if (!c[{d - 3}] && c[{d - 2}]) {{\n    x q[{d - 1}];\n}}"]
    lines += [f"reset q[{d + a}];" for a in range(d - 1)]
    return "\n".join(lines)


for d in (3, 5):
    for r in (1, 3, 20, 100):
        add("qec", f"rep_d{d}_r{r}",
            f"distance-{d} repetition code, {r} syndrome round(s), toy lookup decoder",
            ["O2", "O3", "O5"], repetition_round(d) if r == 1 else rep(r, repetition_round(d)),
            nq=2 * d - 1, nc=d - 1, windowed=(r == 100),
            notes=("100 rounds exceeds the default unroll limit (64): the checker windows the "
                   "loop (one iteration summarised, plan 9.7); only IBM qualifies. "
                   if r == 100 else "Within the unroll limit: unrolled in full. ")
                  + "Simplified decoder: not a full majority vote.")


def surface_round() -> str:
    """Distance-3 rotated surface code, Z-type stabilisers only (4 ancillas, 9 data qubits)."""
    stab = [(0, 1, 3, 4), (1, 2), (4, 5, 7, 8), (6, 7)]  # data qubits of the four Z checks
    lines = []
    for a, ds in enumerate(stab):
        lines += [f"cx q[{x}], q[{9 + a}];" for x in ds]
    lines += [f"c[{a}] = measure q[{9 + a}];" for a in range(4)]
    lines += ["if (c[0]) {\n    x q[4];\n}", "if (c[1] ^ c[2]) {\n    x q[5];\n}",
              "if (c[3]) {\n    x q[7];\n}"]
    lines += [f"reset q[{9 + a}];" for a in range(4)]
    return "\n".join(lines)


for r in (1, 3, 20, 100):
    add("qec", f"surf_d3_r{r}",
        f"distance-3 surface-code patch (Z checks only), {r} round(s), toy corrections",
        ["O2", "O3", "O5"], surface_round() if r == 1 else rep(r, surface_round()),
        nq=13, nc=4, windowed=(r == 100),
        notes="Z stabilisers only and a toy lookup decoder: the shape of a surface-code round, "
              "not a decoder-validated one.")

# ------------------------------------------------------------ magic-state injection (6)
INJ = "h q[0];\ncx q[0], q[1];\nc[0] = measure q[1];\n"
S_NOTE = "The IBM snapshot has no S duration; sx (same cost) stands in for the S correction."


def inj(anns: str) -> str:
    return INJ + f"{anns}box {{\n    if (c[0]) {{\n        sx q[0];\n    }}\n}}"


add("magic_state", "msi_hard_3000",
    "injection with a conditional S-like fix-up inside a hard 3000 ns reaction deadline",
    ["O3"], inj("@timing.within 3000ns c[0]\n@timing.hard\n"), nq=2, nc=1, notes=S_NOTE)
add("magic_state", "msi_hard_1000",
    "same, with a 1000 ns hard deadline (above the 600 ns vendor claim)",
    ["O3"], inj("@timing.within 1000ns c[0]\n@timing.hard\n"), nq=2, nc=1, notes=S_NOTE)
add("magic_state", "msi_hard_tight",
    "same, with a 200 ns hard deadline (below the 600 ns vendor claim)",
    ["O3"], inj("@timing.within 200ns c[0]\n@timing.hard\n"), nq=2, nc=1,
    notes="Intended UNSAFE on IBM (hi = 600 ns > 200 ns). " + S_NOTE)
add("magic_state", "msi_soft_within", "same fix-up with a soft (non-hard) deadline of 3000 ns",
    ["O3"], inj("@timing.within 3000ns c[0]\n"), nq=2, nc=1,
    notes="Non-hard within. " + S_NOTE)
add("magic_state", "msi_two_stage",
    "two-stage injection: S fix-up then a Z fix-up from a second result, both under hard deadlines",
    ["O3", "O2a"],
    "h q[0];\ncx q[0], q[1];\ncx q[0], q[2];\nc[0] = measure q[1];\nc[1] = measure q[2];\n"
    "@timing.within 3000ns c[0]\n@timing.hard\nbox {\n    if (c[0]) {\n        sx q[0];\n"
    "    }\n}\n@timing.within 3000ns c[1]\n@timing.hard\nbox {\n    if (c[1]) {\n"
    "        z q[0];\n    }\n}", nq=3, notes=S_NOTE)
add("magic_state", "msi_eq_hard", "injection under an explicit EQ policy and a hard deadline",
    ["O3", "O4"], inj("@timing.policy eq\n@timing.within 3000ns c[0]\n@timing.hard\n"),
    nq=2, nc=1, notes=S_NOTE)

# ------------------------------------------------------------ lattice surgery (6)
MERGE = "h q[0];\nh q[3];\ncx q[0], q[2];\ncx q[3], q[2];\nc[0] = measure q[2];\n"
FIX = "    z q[0];\n    z q[3];\n"
LS_NOTE = "Patches reduced to one data qubit each: the timing shape only."
add("lattice_surgery", "ls_merge_basic",
    "merge two patches by a joint-parity measurement; correct both patches on the outcome",
    ["O7", "O4"], MERGE + "if (c[0]) {\n" + FIX + "}", nq=4, nc=1, notes=LS_NOTE)
add("lattice_surgery", "ls_merge_sync_delta", "merge with an explicit sync(delta=100ns) policy",
    ["O7", "O4"], MERGE + "@timing.policy sync(delta=100ns)\nbox {\n    if (c[0]) {\n" + FIX
    + "    }\n}", nq=4, nc=1, notes=LS_NOTE)
add("lattice_surgery", "ls_merge_eq", "merge with an explicit EQ policy (arms padded equal)",
    ["O7", "O4"], MERGE + "@timing.policy eq\nbox {\n    if (c[0]) {\n" + FIX + "    }\n}",
    nq=4, nc=1, notes=LS_NOTE)
add("lattice_surgery", "ls_merge_slack",
    "patch B is busy longer than patch A before the merge; a barrier restores the join "
    "(patch-sync slack)", ["O7"],
    "delay[400ns] q[3];\nbarrier q;\n" + MERGE + "if (c[0]) {\n" + FIX + "}", nq=4, nc=1,
    notes="The slack (400 ns) is paid by the barrier before the parity measurement. " + LS_NOTE)
add("lattice_surgery", "ls_split_correction",
    "split after a merge: two results, one correction per patch", ["O7", "O2a"],
    MERGE + "c[1] = measure q[0];\nif (c[0] ^ c[1]) {\n    x q[3];\n}\nif (c[1]) {\n"
            "    z q[3];\n}", nq=4,
    notes="Reads c[1] right after its measurement: stale-read risk (O2a). " + LS_NOTE)
add("lattice_surgery", "ls_merge_split_seq", "merge, then split, in sequence under one policy",
    ["O7", "O4"],
    MERGE + "if (c[0]) {\n" + FIX + "}\nbarrier q;\nc[1] = measure q[0];\nif (c[1]) {\n"
            "    x q[3];\n}", nq=4, notes=LS_NOTE)

# ------------------------------------------------------------ ARTIQ-style kernels (6)
ARTIQ_HDR = ("synthetic ARTIQ-style kernel written by the qtiming authors, NOT external code "
             "(not from the ARTIQ project); exposed-timeline (EXP) form")
ARTIQ_NOTE = ("Synthetic, written by the qtiming authors, NOT external code. The shipped ARTIQ "
              "contract publishes no gate or measure durations and no commit lead, so ARTIQ cells "
              "are `unsupported` until durations are assumed; on IBM the `exp` policy is "
              "rejected (policy-incompatible).")
EXP_IF = "@timing.policy exp\nbox {\n    if (c[0]) {\n        x q[0];\n    }\n}"
for name, why, body, nq in (
    ("artiq_reset_fb", "measure, wait out the result latency, conditionally flip",
     "c[0] = measure q[0];\ndelay[800ns] q[0];\n" + EXP_IF, 1),
    ("artiq_ramsey_fb", "Ramsey sequence with a feedback correction after a free-evolution delay",
     "h q[0];\ndelay[2000ns] q[0];\nh q[0];\nc[0] = measure q[0];\ndelay[800ns] q[0];\n"
     + EXP_IF, 1),
    ("artiq_slack_neg", "feedback issued with NO slack after the measurement: negative slack, "
     "the result is not ready (RTIO underflow candidate)",
     "c[0] = measure q[0];\n" + EXP_IF, 1),
    ("artiq_two_ions", "two channels measured and corrected independently with explicit slack",
     "c[0] = measure q[0];\nc[1] = measure q[1];\ndelay[800ns] q[0];\ndelay[800ns] q[1];\n"
     "@timing.policy exp\nbox {\n    if (c[0]) {\n        x q[0];\n    }\n    if (c[1]) {\n"
     "        x q[1];\n    }\n}", 2),
    ("artiq_burst", "back-to-back gates on one channel before a measurement "
     "(sequence-error / collision candidate)",
     "x q[0];\nx q[0];\nx q[0];\nx q[0];\nc[0] = measure q[0];\ndelay[800ns] q[0];\n" + EXP_IF,
     1),
    ("artiq_wide_lanes", "ten channels pulsed together, then one measured and fed back (more "
     "events than the 8 SED lanes)",
     "".join(f"x q[{i}];\n" for i in range(10))
     + "c[0] = measure q[0];\ndelay[800ns] q[1];\n@timing.policy exp\nbox {\n    if (c[0]) {\n"
       "        x q[1];\n    }\n}", 10),
):
    add("artiq", name, why, ["O1", "O5"], body, header=ARTIQ_HDR, notes=ARTIQ_NOTE, nq=nq,
        nc=max(1, min(nq, 2)))

# ------------------------------------------------------------ kept and external
KEPT_TELEPORTATION = {
    "tp_basic": "teleportation with one correction in a within box (plan A.1)",
    "tp_exp": "teleportation for an exposed-timeline backend (plan A.7)",
    "tp_q1": "teleportation for a predicated backend (plan 8.5)",
    "tp_sync": "teleportation under SYNC with no padding (expected REFUTED on O4)",
}
DYNAMARQ_README = """# Dynamarq: intentionally empty

The plan (17.1) lists about 10 Dynamarq programs as an external family "where available". They
are third-party programs and were not available offline when this suite was generated, and this
repository does not invent substitutes for them. Look-alike programs would defeat the point of
the family (reducing benchmark bias with code the qtiming authors did not write).

When the real programs are obtained, add each as `<name>.qasm` here and record its source URL,
commit, licence and retrieval date in `meta.json`, then rerun `qtiming-bench run` and
`qtiming-bench check --update`.
"""


def render() -> dict[Path, str]:
    out: dict[Path, str] = {}
    for fam, progs in FAMILIES.items():
        meta: dict[str, Any] = {}
        for name, p in progs.items():
            out[ROOT / fam / f"{name}.qasm"] = p["text"]
            meta[name] = {k: v for k, v in p.items() if k != "text"}
        if fam == "teleportation":
            for name, why in KEPT_TELEPORTATION.items():
                meta[name] = {"family": fam, "why": why, "main_obligations": ["O2a", "O3", "O4"],
                              "provenance": PROVENANCE, "licence": LICENCE,
                              "notes": "written in phase P7; not regenerated",
                              "needs_windowing": False}
        out[ROOT / fam / "meta.json"] = json.dumps(dict(sorted(meta.items())), indent=1) + "\n"
    out[ROOT / "dynamarq" / "README.md"] = DYNAMARQ_README
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    files = render()
    if a.check:
        bad = [p for p, t in files.items() if not p.exists() or p.read_text(encoding="utf-8") != t]
        for p in bad:
            print(f"differs: {p}")
        return 1 if bad else 0
    for p, t in files.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(t)
    print(f"wrote {len(files)} files under {ROOT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
