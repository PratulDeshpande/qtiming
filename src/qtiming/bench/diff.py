"""`qtiming-bench diff`: the H1 differential (plan 17.2).

For every program the checker calls PROVED or PROVED-UNDER, run N random (omega, theta) executions
in the reference executor (which shares no code with the graph and solver side) and count the
runs that violate. The number must be ZERO. Two program sources, reported per personality:

* the benchmark suite, under the shipped contracts (`--suite`, `--contracts`);
* random programs (`--programs M`, from `--seed`), under small self-contained contracts of the same
  four personalities (the dicts of tests/differential/test_graph_vs_executor.py, plus gate
  durations), written as OpenQASM 3 so they go through the real front end.

Scope: the executor reports per-run violations only (RTIO underflow, Q1 stale read and RT
underflow, ARTIQ silent drops). O3, O4 and O7 compare times or two runs; they are covered by
tests/property/test_soundness.py, not here.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

from qtiming.core.errors import QtError

STMT_BUDGET = 40_000  # runs x elaborated statements per proved cell
_GATES = {"x": 16, "h": 24, "cx": 40}
CONTRACTS: dict[str, dict[str, Any]] = {
    "ibm": {"durations": {"measure": 90, "reset": 20},
            "latencies": [{"key": "ff.default", "src": "measure", "dst": "branch", "lo": 5,
                           "hi": 60}]},
    "qua": {"durations": {"measure": 90, "reset": 20}, "branch": {"allow_nested": True},
            "params": {},
            "latencies": [
                {"key": "active_reset", "src": "measure", "dst": "branch", "lo": 0, "hi": 40},
                {"key": "align.same_fem", "src": "align", "dst": "align", "tier": "same_fem",
                 "lo": 0, "hi": 12}]},
    "q1": {"durations": {"measure": 30, "reset": 10}, "issue_cost": {"nop": 1},
           "capacity": {"rt_queue_depth": 4}, "params": {"else_time_dt": 1},
           "branch": {"allow_nested": True},
           "latencies": [{"key": "trigger.network", "src": "measure", "dst": "branch", "lo": 3,
                          "hi": 20}]},
    "artiq": {"durations": {"measure": 20, "reset": 5}, "issue_cost": {"cpu_issue": 3},
              "capacity": {"lanes": 8, "coarse_mu": 8}, "commit_lead": 4,
              "branch": {"class": "exposed", "default_policy": "exp", "allow_nested": True},
              "latencies": [{"key": "in2cpu", "src": "input", "dst": "cpu", "lo": 0, "hi": 50}]},
}
_KLASS = {"ibm": "restricted", "q1": "predicated", "qua": "resync", "artiq": "exposed"}
_POLICY = {"ibm": "sync", "q1": "eq", "qua": "sync", "artiq": "exp"}
_LATE = {"ibm": "compile_error", "q1": "halt", "artiq": "mixed", "qua": "compile_error"}


def make_contract(pers: str) -> Any:
    from qtiming.contract.loader import load_contract_dict

    spec = CONTRACTS[pers]
    raw: dict[str, Any] = {
        "meta": {"name": f"bench_{pers}", "version": "0", "schema": "qtiming-contract/0.2",
                 "personality": pers},
        "timebase": {"dt_ns": "1"},
        "timeline": {"late_policy": _LATE[pers]},
        "durations": {**spec["durations"], **_GATES},
        "issue_cost": {k: {"ns": v, "prov": "cyc", "source": "bench"}
                       for k, v in spec.get("issue_cost", {}).items()},
        "capacity": spec.get("capacity", {}),
        "latency": [{"key": x["key"], "src": x["src"], "dst": x["dst"],
                     "tier": x.get("tier", "default"), "lo_ns": x["lo"], "hi_ns": x["hi"],
                     "prov": "vendor", "source": "bench"} for x in spec["latencies"]],
        "branch": {"class": _KLASS[pers], "default_policy": _POLICY[pers], "allow_nested": False,
                   **spec.get("branch", {})},
        "personality_params": {pers: spec.get("params", {})},
    }
    if spec.get("commit_lead") is not None:
        raw["timeline"]["commit_lead"] = spec["commit_lead"]
    return load_contract_dict(raw)


def random_qasm(pers: str, rng: random.Random) -> str:
    """A random valid program: gates, delays, measures, barriers and (nested-free) ifs."""
    wide = pers not in ("q1", "artiq")
    out: list[str] = []
    nbits = 0

    def simple() -> str:
        if rng.random() < 0.3:
            return f"delay[{rng.randint(1, 40)}ns] q[{rng.randrange(3)}];"
        if wide and rng.random() < 0.3:
            a, b = rng.sample(range(3), 2)
            return f"cx q[{a}], q[{b}];"
        return f"{rng.choice(['x', 'h'])} q[{rng.randrange(3)}];"

    if pers == "artiq":
        out.append(f"delay[{rng.randint(1, 80)}ns] q[0];")
    for _ in range(rng.randint(3, 10)):
        r = rng.random()
        if r < 0.22 and nbits < 4:
            out.append(f"c[{nbits}] = measure q[{rng.randrange(3)}];")
            nbits += 1
        elif r < 0.52 and nbits:
            c = f"c[{rng.randrange(nbits)}]"
            if nbits > 1 and rng.random() < 0.3:
                c = f"{c} ^ c[{rng.randrange(nbits)}]"
            if rng.random() < 0.3:
                c = f"!({c})"
            then = "\n".join("    " + simple() for _ in range(rng.randint(1, 3)))
            els = ("" if rng.random() < 0.4 else " else {\n" + "\n".join(
                "    " + simple() for _ in range(rng.randint(1, 3))) + "\n}")
            out.append(f"if ({c}) {{\n{then}\n}}{els}")
        elif r < 0.62 and wide:
            out.append("barrier q;")
        else:
            out.append(simple())
    return "OPENQASM 3.0;\nqubit[3] q;\nbit[4] c;\n" + "\n".join(out) + "\n"


def _violations(body: Any, contract: Any, runs: int, seed: int) -> tuple[int, int, set[str]]:
    """(runs that violate, runs executed, kinds seen) of `runs` random executions."""
    from qtiming.exec.engine import execute
    from qtiming.exec.oracle import Random

    bad, kinds = 0, set()
    for k in range(runs):
        res = execute(body, contract, Random(seed * 1_000_003 + k))
        ks = {v.kind for v in res.violations} | {f"drop:{d.kind}" for d in res.drops}
        bad += bool(ks)
        kinds |= ks
    return bad, runs, kinds


def diff_program(prog: Any, contract: Any, policy: str, runs: int, seed: int,
                 ) -> tuple[str, int, set[str], int] | None:
    """(verdict, violating runs, kinds, runs used) if PROVED or PROVED-UNDER, else None."""
    from qtiming.core.ast import Policy
    from qtiming.elab import elaborate
    from qtiming.verdict.run import check_program, collect_locs, with_policy

    from . import UNROLL_LIMIT

    v = check_program(prog, contract, policy=policy, unroll_limit=UNROLL_LIMIT).verdict
    if v not in ("PROVED", "PROVED-UNDER"):
        return None
    # the executor runs the program the verdict was about, fully unrolled (also a windowed loop)
    el = elaborate(with_policy(prog, Policy(policy)), contract, unroll_limit=256)  # type: ignore[arg-type]
    # long unrolled programs get fewer runs (cost ~ runs x statements); the cap is reported
    n = max(10, min(runs, STMT_BUDGET // max(1, len(collect_locs(el.body, {})))))
    bad, _, kinds = _violations(el.body, contract, n, seed)
    return v, bad, kinds, n


def _diff(a: argparse.Namespace) -> int:
    from qtiming.contract.loader import load_contract
    from qtiming.frontend import from_qasm3

    from . import INSTANCES, contracts, key, programs

    per: dict[str, dict[str, int]] = {}
    failures: list[dict[str, Any]] = []

    def skip(pers: str) -> None:
        per.setdefault(pers, {"cells": 0, "proved_cells": 0, "runs": 0, "violating_runs": 0,
                              "skipped": 0})["skipped"] += 1

    def tally(pers: str, name: str, res: tuple[str, int, set[str], int] | None) -> None:
        s = per.setdefault(pers, {"cells": 0, "proved_cells": 0, "runs": 0, "violating_runs": 0,
                                  "skipped": 0})
        s["cells"] += 1
        if res is None:
            return
        s["proved_cells"] += 1
        s["runs"] += res[3]
        s["violating_runs"] += res[1]
        if res[1]:
            failures.append({"cell": name, "verdict": res[0], "violating_runs": res[1],
                             "kinds": sorted(res[2])})

    loaded = {cn: load_contract(str(INSTANCES / f"{cn}.toml")) for cn in contracts(a.contracts)}
    for prog in programs(Path(a.suite)) if a.suite else []:
        for cn in loaded:
            for pol in a.policies.split(","):
                name = key({"family": prog.parent.name, "program": prog.stem, "contract": cn,
                            "policy": pol})
                c = loaded[cn]
                try:
                    p = from_qasm3(prog.read_text(encoding="utf-8"), filename=str(prog),
                                   contract=c)
                    tally(c.personality, name, diff_program(p.body, c, pol, a.runs, a.seed))
                except QtError:
                    skip(c.personality)
    for pers in CONTRACTS:
        c = make_contract(pers)
        for n in range(a.programs):
            seed = a.seed * 100_003 + n
            text = random_qasm(pers, random.Random(seed))
            for pol in ("eq", "sync", "exp"):
                try:
                    p = from_qasm3(text, filename=f"random/{pers}/{seed}", contract=c)
                    tally(pers, f"random/{pers}/{seed}|{pol}",
                          diff_program(p.body, c, pol, a.runs, seed))
                except QtError:
                    skip(pers)
    total = sum(s["violating_runs"] for s in per.values())
    doc = {"runs_per_cell": a.runs, "seed": a.seed, "random_programs_per_personality": a.programs,
           "per_personality": dict(sorted(per.items())), "violating_runs_total": total,
           "failures": failures}
    if a.out:
        out = Path(a.out)
        out = out if out.suffix == ".json" else out / "diff.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    for pers, s in sorted(per.items()):
        print(f"{pers}: {s['proved_cells']} proved cells of {s['cells']}, {s['runs']} runs, "
              f"{s['violating_runs']} violating, {s['skipped']} unsupported")
    for f in failures[:20]:
        print(f"VIOLATION {f}")
    print(f"H1: {total} violating runs in total ({'PASS' if total == 0 else 'FAIL'})")
    return 1 if total else 0


def add_parser(sub: Any) -> None:
    d = sub.add_parser("diff", help="H1 differential: executor violations on proved programs")
    d.add_argument("--runs", type=int, default=1000, help="random executions per proved cell")
    d.add_argument("--seed", type=int, default=1)
    d.add_argument("--programs", type=int, default=0,
                   help="random programs per personality (0: benchmark suite only)")
    d.add_argument("--suite", default="benchmarks/families", help="'' to skip the suite")
    d.add_argument("--contracts", default="all")
    d.add_argument("--policies", default="eq,sync,exp")
    d.add_argument("--out")
    d.set_defaults(fn=_diff)
