"""First differential run (plan P6): on random programs, the graph's dispatch evaluation must
equal the executor's event times exactly, for every personality."""

from __future__ import annotations

import os
import random
import sys
from dataclasses import fields, is_dataclass, replace
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "personality"))
from _support import KLASS, build, make_contract  # noqa: E402

from qtiming.contract.compat import compat  # noqa: E402
from qtiming.core.ast import If, Policy  # noqa: E402
from qtiming.core.errors import QtError  # noqa: E402
from qtiming.dispatch import build_graph  # noqa: E402
from qtiming.elab import elaborate  # noqa: E402
from qtiming.exec.engine import execute  # noqa: E402
from qtiming.exec.oracle import Random as RandomOracle  # noqa: E402
from qtiming.graph.invariants import bit_props, check_invariants  # noqa: E402
from qtiming.graph.lteg import evaluate_graph  # noqa: E402

N = int(os.environ.get("QTIMING_DIFF_N", "1000"))

CONTRACTS: dict[str, dict[str, Any]] = {
    "ibm": {"durations": {"measure": 90, "measure_2": 90, "reset": 20},
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


def gen(pers: str, rng: random.Random) -> list[dict[str, Any]]:
    """A random valid program: gates/delays/measures/barriers and (per personality) ifs."""
    ops: list[dict[str, Any]] = []
    measured: list[str] = []
    n = 0

    def nm(prefix: str) -> str:
        nonlocal n
        n += 1
        return f"{prefix}{n}"

    def simple(qs: int = 3) -> dict[str, Any]:
        k = rng.random()
        wide = pers not in ("q1", "artiq")
        q = rng.sample(range(qs), rng.choice([1, 1, 2]) if wide else 1)
        dur = rng.randint(1, 40)
        if k < 0.7:
            return {"op": "gate", "id": nm("g"), "q": q, "dur": dur}
        return {"op": "delay", "id": nm("d"), "q": q, "dur": dur}

    if pers == "artiq":
        ops.append({"op": "delay", "id": nm("d"), "q": [0], "dur": rng.randint(0, 80)})
    for _ in range(rng.randint(3, 10)):
        r = rng.random()
        if r < 0.22 and len(measured) < 4:
            mid = nm("m")
            ops.append({"op": "measure", "id": mid, "q": rng.randrange(3), "bit": len(measured)})
            measured.append(mid)
        elif r < 0.52 and measured:
            c = rng.choice(measured)
            if len(measured) > 1 and rng.random() < 0.3:
                c = c + "^" + rng.choice([x for x in measured if x != c])
            if rng.random() < 0.3:
                c = "!" + c
            then = [simple() for _ in range(rng.randint(1, 3))]
            els = [simple() for _ in range(rng.randint(1, 3))] if rng.random() < 0.6 else None
            ops.append({"op": "if", "id": nm("i"), "cond": c, "then": then,
                        **({} if els is None else {"else": els})})
        elif r < 0.62 and pers in ("ibm", "qua"):
            ops.append({"op": "barrier", "id": nm("b"),
                        "q": rng.sample(range(3), rng.choice([2, 3]))})
        else:
            ops.append(simple())
    return ops


class Recording:
    """Seeded Random oracle that records every choice, so the graph can replay it."""

    def __init__(self, seed: int) -> None:
        self.inner = RandomOracle(seed)
        self.omega: dict[str, int] = {}
        self.theta: dict[str, Fraction] = {}

    def outcome(self, prop: str) -> int:
        self.omega[prop] = self.inner.outcome(prop)
        return self.omega[prop]

    def latency(self, occurrence: str, iv: Any) -> Fraction:
        self.theta[occurrence] = self.inner.latency(occurrence, iv)
        return self.theta[occurrence]


def with_policy(s: Any, pol: Policy) -> Any:
    """Copy of the program with every unannotated If given policy `pol`."""
    if isinstance(s, tuple):
        return tuple(with_policy(x, pol) for x in s)
    if not is_dataclass(s):
        return s
    ch = {f.name: with_policy(getattr(s, f.name), pol) for f in fields(s)
          if f.name in ("stmts", "body", "then_", "else_", "default", "exhaust")}
    if isinstance(s, If) and s.policy is None:
        ch["policy"] = pol
    return replace(s, **ch)  # type: ignore[type-var]


ACCEPTED = [(p, pol) for p in KLASS for pol in (None, "eq", "sync", "exp")
            if pol is None or compat(pol, KLASS[p]).accepted]


@pytest.mark.parametrize("pers,policy", ACCEPTED)
def test_graph_equals_executor_on_random_programs(pers: str, policy: str | None) -> None:
    contract = make_contract(pers, CONTRACTS[pers])
    ran = 0
    for seed in range(N):
        prog, _ = build(gen(pers, random.Random(seed)))
        if policy:
            prog = with_policy(prog, Policy(policy))  # type: ignore[arg-type]
        try:
            el = elaborate(prog, contract)
        except QtError as e:
            if e.code.startswith("E-ELAB-"):  # EQ arms not equalisable, policy rejected, ...
                continue
            raise
        try:
            g = build_graph(el.body, contract)
        except QtError as e:
            if e.code == "E-GRAPH-UNSUPPORTED":  # personality restriction (e.g. IBM nesting)
                continue
            raise
        check_invariants(g)
        oracle = Recording(seed)
        res = execute(el.body, contract, oracle)
        # bits the graph needs but the executor never drew (untaken paths) default to 0
        omega = dict.fromkeys(bit_props(g), 0)
        omega.update(oracle.omega)
        theta = {v.occurrence: Fraction(v.lo) for v in g.lats}
        theta.update(oracle.theta)
        times = evaluate_graph(g, omega, theta)
        for key, want in res.times.items():
            if key[1] == "emit":
                continue
            assert times.get(key) == want, (
                f"{pers}/{policy} seed {seed}: {key}: graph {times.get(key)} != exec {want}"
            )
        ran += 1
    assert ran >= N // 3, f"only {ran}/{N} programs were comparable"


@pytest.mark.parametrize("pers", list(KLASS))
def test_rejected_policies_are_refused(pers: str) -> None:
    contract = make_contract(pers, CONTRACTS[pers])
    bad = [p for p in ("eq", "sync", "exp") if not compat(p, KLASS[pers]).accepted]
    for pol in bad:
        for seed in range(50):
            ops = gen(pers, random.Random(seed))
            if not any(o["op"] == "if" for o in ops):
                continue
            prog, _ = build(ops)
            with pytest.raises(QtError, match="E-ELAB-POLICY-REJECTED"):
                elaborate(with_policy(prog, Policy(pol)), contract)  # type: ignore[arg-type]
            break
