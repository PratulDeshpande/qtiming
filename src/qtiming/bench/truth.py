"""`qtiming-bench truth`: exhaustive ground truth for small programs (plan 16.4, hypothesis H2).

For each (program, contract, policy) cell whose elaborated program is small enough, enumerate every
outcome assignment times every vertex of the latency box in the reference executor
(`qtiming.exec.explore.exhaustive`) and record whether ANY execution violates.

Scope, stated so the numbers are not over-read: the executor reports per-run violations only
(RTIO underflow, Q1 stale read / RT underflow, ARTIQ silent drops). Obligations that compare two
runs (O4 idle-gap variation, O7) or a deadline (O3) are not visible to it, so `violated: false`
means "no per-run violation reachable", not "the program is safe". Vertices of the latency box are
exact only for snap-free programs (theorem T10).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from qtiming.core.errors import QtError


def truth_cell(prog: Path, contract: str, policy: str, *, max_bits: int, max_lats: int,
               max_runs: int, assume: tuple[str, ...] = ()) -> dict[str, Any]:
    from qtiming.core.ast import Policy
    from qtiming.elab import elaborate
    from qtiming.exec.explore import exhaustive
    from qtiming.verdict.run import with_policy

    from . import load_cell

    c, p = load_cell(prog, contract, assume)
    body = with_policy(p.body, Policy(policy))  # type: ignore[arg-type]
    el = elaborate(body, c)
    kinds: set[str] = set()
    runs = 0
    for _omega, _theta, res in exhaustive(el.body, c, k_max=max_bits, K_max=max_lats):
        runs += 1
        kinds |= {v.kind for v in res.violations} | {f"drop:{d.kind}" for d in res.drops}
        if runs >= max_runs:
            raise QtError("E-EXEC-EXHAUSTIVE", f"more than {max_runs} executions")
    return {"executions": runs, "violated": bool(kinds), "kinds": sorted(kinds)}


def _truth(a: argparse.Namespace) -> int:
    from . import contracts, key, programs

    truth: dict[str, Any] = {}
    skipped: dict[str, str] = {}
    for prog in programs(Path(a.suite)):
        for c in contracts(a.contracts):
            for pol in a.policies.split(","):
                k = key({"family": prog.parent.name, "program": prog.stem, "contract": c,
                         "policy": pol})
                try:
                    truth[k] = truth_cell(prog, c, pol, max_bits=a.max_bits, max_lats=a.max_lats,
                                          max_runs=a.max_runs, assume=tuple(a.assume or ()))
                except QtError as e:  # too big, unbounded latency, unsupported, ...
                    skipped[k] = e.code
    out = Path(a.out)
    out = out if out.suffix == ".json" else out / "ground_truth.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = {"limits": {"max_bits": a.max_bits, "max_latencies": a.max_lats,
                      "max_executions": a.max_runs},
           "scope": "per-run executor violations only; see qtiming.bench.truth",
           "truth": dict(sorted(truth.items())), "skipped": dict(sorted(skipped.items()))}
    out.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    reasons: dict[str, int] = {}
    for v in skipped.values():
        reasons[v] = reasons.get(v, 0) + 1
    print(f"{len(truth)} cells with ground truth, {len(skipped)} skipped "
          + (f"({', '.join(f'{k}={v}' for k, v in sorted(reasons.items()))})" if reasons else "")
          + f" -> {out}")
    return 0


def add_parser(sub: Any) -> None:
    t = sub.add_parser("truth", help="exhaustive ground truth for small programs (H2)")
    t.add_argument("--suite", default="benchmarks/families")
    t.add_argument("--contracts", default="all")
    t.add_argument("--policies", default="eq,sync,exp")
    t.add_argument("--max-bits", type=int, default=8, help="skip programs with more outcome bits")
    t.add_argument("--max-lats", type=int, default=6, help="skip programs with more latencies")
    t.add_argument("--max-runs", type=int, default=2048, help="skip programs needing more runs")
    t.add_argument("--assume", action="append", metavar="KEY=VALUE")
    t.add_argument("--out", default="benchmarks/families/")
    t.set_defaults(fn=_truth)
