"""Oracle behaviour: Fixed defaults, Random determinism, Extreme vertices, Exhaustive coverage."""

from __future__ import annotations

from fractions import Fraction

import pytest
from _support import cases, load_case

from qtiming.core.errors import QtError
from qtiming.core.time import Interval
from qtiming.exec.engine import execute
from qtiming.exec.explore import exhaustive
from qtiming.exec.oracle import Extreme, Fixed, Random


def test_fixed_defaults_are_recorded_and_midpoint() -> None:
    o = Fixed()
    assert o.latency("k@m1", Interval(0, 10)) == 5
    assert o.outcome("c[0]@m1") == 0
    assert o.defaulted == ["k@m1", "c[0]@m1"]


def test_fixed_rejects_theta_outside_interval() -> None:
    with pytest.raises(QtError, match="E-EXEC-THETA"):
        Fixed(theta={"k@m1": 11}).latency("k@m1", Interval(0, 10))


def test_random_is_seeded_and_inside_interval() -> None:
    a, b = Random(7), Random(7)
    xs = [a.latency("k", Interval(3, 9)) for _ in range(20)]
    assert xs == [b.latency("k", Interval(3, 9)) for _ in range(20)]
    assert all(3 <= x <= 9 and (x * 8).denominator == 1 for x in xs)


def test_extreme_picks_vertices() -> None:
    assert Extreme("hi").latency("k", Interval(3, 9)) == 9
    assert Extreme("lo").latency("k", Interval(3, 9)) == 3


def test_exhaustive_covers_both_outcomes_and_both_vertices() -> None:
    c = load_case(next(p for p in cases("ibm") if "04_if_pad" in p.name))
    runs = list(exhaustive(c.prog, c.contract))
    assert len(runs) == 4  # 2 outcomes x 2 latency vertices (0 and 600)
    assert {tuple(sorted(r[1].values())) for r in runs} == {(Fraction(0),), (Fraction(600),)}
    # EQ-style padding: the block end does not depend on the outcome for a fixed latency
    ends: dict[Fraction, set[Fraction]] = {}
    for _, theta, res in runs:
        ends.setdefault(next(iter(theta.values())), set()).add(
            next(v for (n, tag), v in res.times.items() if tag == "bend")
        )
    assert all(len(v) == 1 for v in ends.values())


def test_artiq_refuses_unspecified_commit_lead() -> None:
    c = load_case(next(p for p in cases("artiq") if "01_pulse" in p.name))
    from dataclasses import replace

    with pytest.raises(QtError, match="E-EXEC-PARAM"):
        execute(c.prog, replace(c.contract, commit_lead=None))


def test_unelaborated_loop_is_refused() -> None:
    from qtiming.core.ast import For, Seq, SourceLoc

    c = load_case(next(p for p in cases("ibm") if "01_gate" in p.name))
    loc = SourceLoc("t")
    loop = For(nid=99, loc=loc, var="i", n=2, body=Seq(nid=100, loc=loc, stmts=()))
    with pytest.raises(QtError, match="E-EXEC-UNSUPPORTED"):
        execute(loop, c.contract)
