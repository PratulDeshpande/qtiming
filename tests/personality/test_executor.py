"""The reference executor must reproduce every hand-computed golden trace exactly."""

from __future__ import annotations

from fractions import Fraction

import pytest
from _support import cases, expected_times, load_case

from qtiming.exec.engine import execute
from qtiming.exec.oracle import Fixed

PERSONALITIES = ["ibm", "q1", "artiq", "qua"]
ALL = [(p, c) for p in PERSONALITIES for c in cases(p)]


def test_at_least_six_goldens_per_personality() -> None:
    for p in PERSONALITIES:
        assert len(cases(p)) >= 6, p


@pytest.mark.parametrize("pers,path", ALL, ids=[f"{p}/{c.stem}" for p, c in ALL])
def test_executor_reproduces_golden(pers: str, path) -> None:  # type: ignore[no-untyped-def]
    c = load_case(path)
    res = execute(c.prog, c.contract, Fixed(c.omega, c.theta))
    for key, want in expected_times(c).items():
        assert res.times.get(key) == want, f"{c.name}: {key} = {res.times.get(key)}, want {want}"
    for who_tag in c.expect.get("absent", []):
        who, _, tag = who_tag.partition(".")
        assert (c.ids[who], tag) not in res.times, f"{c.name}: {who_tag} should not exist"
    if "violations" in c.expect:
        got = sorted((v.kind, v.nid, v.shortfall) for v in res.violations)
        want = sorted(
            (v["kind"], c.ids[v["id"]], Fraction(v["shortfall"])) for v in c.expect["violations"]
        )
        assert got == want
    if "drops" in c.expect:
        got_d = sorted((d.kind, d.nid, d.t) for d in res.drops)
        want_d = sorted((d["kind"], c.ids[d["id"]], Fraction(d["t"])) for d in c.expect["drops"])
        assert got_d == want_d
    assert res.halted == c.expect.get("halted", False)
