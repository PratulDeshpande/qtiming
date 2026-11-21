"""Precompute Docs/tutorials/compare-data.json from real `qtiming check` runs (no qtiming in the browser)."""
from __future__ import annotations

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Docs" / "tutorials" / "compare-data.json"
FAM = "benchmarks/families/"
PROGRAMS = {
    "tp_basic": "teleportation/tp_basic.qasm",
    "tp_q1": "teleportation/tp_q1.qasm",
    "rep_d3_r3": "qec/rep_d3_r3.qasm",
    "msi_hard_3000": "magic_state/msi_hard_3000.qasm",
}
# Durations are assumed by the user (not in the contracts); the page says so.
DUR = ["durations.x=32", "durations.sx=32", "durations.h=32", "durations.cx=100",
       "durations.measure=1000", "durations.reset=1000"]
STACKS = {  # contract -> (swept key, format, values in ns, fixed assumes, label)
    "ibm_heron": ("ff.default", "0:{}", [0, 600, 3000, 3001, 5000], [], "ff.default upper bound (ns)"),
    "qua": ("active_reset", "0:{}", [0, 224, 1000, 3000, 10000], DUR, "active_reset upper bound (ns)"),
    "q1": ("trigger.network", "212:{}", [212, 240, 1000, 3000, 10000], DUR, "trigger.network upper bound (ns)"),
    "artiq": ("timeline.commit_lead", "{}", [0, 100, 1000, 3000, 10000],
              DUR + ["latency.in2cpu.hi=0"], "timeline.commit_lead (ns)"),
}

INTRO = """# Same circuit, four stacks: interactive comparison

Pick a program and drag each stack's slider. Every result below was produced by a real
`qtiming check` run (`tutorials/compare.py`); no qtiming code runs in your browser. Gate durations on
QUA, Q1 and ARTIQ are **illustrative assumptions of this page**, not vendor numbers: see
[what the numbers assume](#what-the-numbers-assume) before reading anything into them.
"""

NOTES = """
## What the numbers assume

- The slider moves the one latency that matters most on that stack, through `--assume`.
  IBM: `ff.default` upper bound. QUA: `active_reset`. Q1: `trigger.network` (lower bound fixed at 212 ns).
  ARTIQ: `timeline.commit_lead`.
- Gate durations on QUA, Q1 and ARTIQ (x, sx, h = 32 ns, cx = 100 ns, measure and reset = 1000 ns) are
  **illustrative assumptions of this page**, not vendor numbers; the contracts leave them absent. On ARTIQ
  `latency.in2cpu.hi` is assumed 0 so the sweep can reach a verdict. IBM takes its durations from the Target.
- Errors such as `E-ELAB-Q1-NOT-EQUALISABLE` are shown as cells, not hidden. PROVED-UNDER is conditional
  on the vendor-claimed latencies, which are claims, not certified bounds.

For the walk-through see [Same circuit, four stacks](06-four-stacks.md).
"""


def run(prog: str, contract: str, assume: list[str], fmt: str) -> str:
    a = [x for s in assume for x in ("--assume", s)]
    p = subprocess.run([sys.executable, "-m", "qtiming.cli.main", "check", FAM + prog,
                        "--contract", contract, "--format", fmt, *a],
                       capture_output=True, text=True, cwd=ROOT)
    return p.stdout + (p.stderr if not p.stdout else "")


def cell(job: tuple[str, str, int]) -> tuple[tuple[str, str, int], dict]:
    pname, contract, i = job
    key, fmt, vals, fixed, _ = STACKS[contract]
    assume = fixed + [f"{key}={fmt.format(vals[i])}"]
    js = run(PROGRAMS[pname], contract, assume, "json")
    try:
        j = json.loads(js)
    except json.JSONDecodeError:  # an error such as E-CT-MISSING is a cell, not a hole
        return (pname, contract, i), {"verdict": "ERROR", "error": js.strip().splitlines()[0]}
    obl = {}
    for o in j.get("obligations", []):
        by = obl.setdefault(o["code"], {})
        by[o["result"]] = by.get(o["result"], 0) + 1
    margins = [int(float(o["margin_ns"])) for o in j.get("obligations", [])
               if o.get("margin_ns") not in (None, "")]
    html = run(PROGRAMS[pname], contract, assume, "html")
    s, e = html.find("<svg"), html.rfind("</svg>")
    return (pname, contract, i), {
        "verdict": j["verdict"], "obligations": obl,
        "min_margin_ns": min(margins) if margins else None,
        "svg": html[s : e + 6] if s >= 0 < e else "",
    }


def main() -> None:
    jobs = [(p, c, i) for p in PROGRAMS for c in STACKS for i in range(len(STACKS[c][2]))]
    with ThreadPoolExecutor(8) as ex:
        res = dict(ex.map(cell, jobs))
    data = {"stacks": {c: {"key": s[0], "label": s[4], "values": s[2]} for c, s in STACKS.items()},
            "programs": {}}
    for p in PROGRAMS:
        data["programs"][p] = {
            "source": (ROOT / (FAM + PROGRAMS[p])).read_text(encoding="utf-8"),
            "cells": {c: [res[(p, c, i)] for i in range(len(STACKS[c][2]))] for c in STACKS},
        }
    OUT.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    page = (Path(__file__).parent / "compare_page.html").read_text(encoding="utf-8")
    blob = json.dumps(data, sort_keys=True, separators=(",", ":")).replace("</", "<\\/")
    (OUT.parent / "compare.md").write_text(INTRO + "\n" + page.replace("__DATA__", blob) + NOTES,
                                           encoding="utf-8")


if __name__ == "__main__":
    main()
