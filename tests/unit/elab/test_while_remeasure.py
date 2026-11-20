"""A `while` whose body re-measures the bit it tests: iteration j+1 must read the NEW measurement.

Regression for a bare AssertionError in graph.builder.arm: the unrolled iterations all tested the
pre-loop proposition, so a nested else-arm contradicted its enclosing then-arm.
"""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import pytest

pytest.importorskip("openqasm3")

from qtiming.contract.loader import load_contract  # noqa: E402
from qtiming.core.ast import (
    If,  # noqa: E402
    Policy,  # noqa: E402
)
from qtiming.core.time import Interval  # noqa: E402
from qtiming.dispatch import build_graph  # noqa: E402
from qtiming.elab import elaborate  # noqa: E402
from qtiming.exec.engine import execute  # noqa: E402
from qtiming.exec.oracle import Random as RandomOracle  # noqa: E402
from qtiming.frontend import from_qasm3  # noqa: E402
from qtiming.graph.invariants import bit_props, check_invariants  # noqa: E402
from qtiming.graph.lteg import evaluate_graph  # noqa: E402
from qtiming.verdict.run import check_program, with_policy  # noqa: E402

INST = Path(__file__).parents[3] / "src" / "qtiming" / "contract" / "instances"
SRC = """OPENQASM 3.0;
qubit[2] q;
bit[1] c;
c[0] = measure q[0];
@timing.cap 3
box {
    while (c[0]) {
        x q[1];
        h q[0];
        c[0] = measure q[0];
    }
}
"""
DUR = ("durations.h=20", "durations.x=20", "durations.measure=1000", "durations.reset=100")


def _conds(s: object, out: list[str]) -> list[str]:
    if isinstance(s, If):
        out.append(repr(s.cond))
    for name in ("stmts", "body", "then_", "else_", "exhaust"):
        v = getattr(s, name, None)
        for c in (v if isinstance(v, tuple) else (v,)):
            if c is not None:
                _conds(c, out)
    return out


@pytest.mark.parametrize("inst", ["qua", "artiq"])
def test_unrolled_iterations_test_distinct_measurements(inst: str) -> None:
    c = load_contract(str(INST / f"{inst}.toml"), assume=DUR)
    p = from_qasm3(SRC, filename="w", contract=c)
    conds = _conds(elaborate(p.body, c).body, [])
    assert len(conds) >= 3 and len(set(conds)) == len(conds), conds


@pytest.mark.parametrize("inst", ["qua", "artiq"])
def test_check_does_not_crash_on_a_remeasuring_while(inst: str) -> None:
    c = load_contract(str(INST / f"{inst}.toml"), assume=DUR)
    p = from_qasm3(SRC, filename="w", contract=c)
    assert check_program(p.body, c).verdict in {"PROVED", "PROVED-UNDER", "REFUTED", "UNKNOWN"}


class _Rec:
    """Random oracle that records its draws so the graph can replay them."""

    def __init__(self, seed: int) -> None:
        self.inner, self.omega, self.theta = RandomOracle(seed), {}, {}

    def outcome(self, prop: str) -> int:
        self.omega[prop] = self.inner.outcome(prop)
        return self.omega[prop]

    def latency(self, occurrence: str, iv: object) -> Fraction:
        if iv.hi is None:  # contract leaves it unbounded: sample a finite window above lo
            iv = Interval(iv.lo, iv.lo + 50)  # type: ignore[attr-defined]
        self.theta[occurrence] = self.inner.latency(occurrence, iv)  # type: ignore[arg-type]
        return self.theta[occurrence]


@pytest.mark.parametrize("policy", ["eq", "sync"])
@pytest.mark.parametrize("cap", [1, 2, 3])
@pytest.mark.parametrize("inst", ["qua"])
def test_graph_matches_executor_on_a_remeasuring_while(inst: str, cap: int, policy: str) -> None:
    c = load_contract(str(INST / f"{inst}.toml"), assume=DUR)
    p = from_qasm3(SRC.replace("cap 3", f"cap {cap}"), filename="w", contract=c)
    el = elaborate(with_policy(p.body, Policy(policy)), c)  # type: ignore[arg-type]
    g = build_graph(el.body, c)
    check_invariants(g)
    for seed in range(12):
        o = _Rec(seed)
        res = execute(el.body, c, o)
        omega = dict.fromkeys(bit_props(g), 0)
        omega.update(o.omega)
        theta = {v.occurrence: Fraction(v.lo) for v in g.lats}
        theta.update(o.theta)
        times = evaluate_graph(g, omega, theta)
        for key, want in res.times.items():
            if key[1] != "emit":
                assert times.get(key) == want, (seed, key, times.get(key), want)
