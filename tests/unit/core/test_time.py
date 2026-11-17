from fractions import Fraction

import pytest
from hypothesis import given
from hypothesis import strategies as st

from qtiming.core.errors import QtError
from qtiming.core.provenance import Prov, ProvClass
from qtiming.core.time import Interval, Latency, dt_to_ns, ns_to_dt

DT = Fraction(4)


# Rounding by role (finding F7): the table at boundary values.
@pytest.mark.parametrize(
    ("ns", "role", "expected"),
    [
        (3001, "deadline", 750),        # floor: 751 would admit a violation
        (3003, "deadline", 750),
        (3004, "deadline", 751),
        (101, "commit_lead", 26),       # ceil: 25 would admit an underflow
        (100, "commit_lead", 25),
        (601, "latency_hi", 151),       # ceil, outward
        (599, "latency_lo", 149),       # floor, outward
        (600, "latency_lo", 150),
        (7, "gap_bound", 1),
        (7, "spread_bound", 1),
        (7, "min_separation", 2),
        (1660, "exact", 415),
    ],
)
def test_rounding_by_role(ns: int, role: str, expected: int) -> None:
    assert ns_to_dt(ns, DT, role) == expected  # type: ignore[arg-type]


def test_exact_rejects_non_multiple() -> None:
    with pytest.raises(QtError) as ei:
        ns_to_dt(1661, DT, "exact", what="measure")
    assert ei.value.code == "E-TIME-EXACT"
    assert "measure" in ei.value.message


def test_decimal_string_is_exact_not_float() -> None:
    # 0.1 ns must not pick up binary float noise
    assert ns_to_dt("0.1", Fraction(1, 10), "exact") == 1


def test_dt_to_ns_roundtrip() -> None:
    assert dt_to_ns(Fraction(3, 2), DT) == Fraction(6)


@given(st.fractions(min_value=0, max_value=10**6), st.integers(min_value=1, max_value=16))
def test_rounding_soundness_property(ns: Fraction, dt: int) -> None:
    d = Fraction(dt)
    assert ns_to_dt(ns, d, "latency_lo") * d <= ns
    assert ns_to_dt(ns, d, "latency_hi") * d >= ns
    assert ns_to_dt(ns, d, "deadline") * d <= ns
    assert ns_to_dt(ns, d, "gap_bound") * d <= ns
    assert ns_to_dt(ns, d, "spread_bound") * d <= ns
    assert ns_to_dt(ns, d, "commit_lead") * d >= ns
    assert ns_to_dt(ns, d, "min_separation") * d >= ns


def test_interval_rejects_empty() -> None:
    with pytest.raises(QtError) as ei:
        Interval(5, 3)
    assert ei.value.code == "E-INTERVAL"


def test_interval_add_hull_contains() -> None:
    a, b = Interval(1, 3), Interval(2, 10)
    assert a + b == Interval(3, 13)
    assert a.hull(b) == Interval(1, 10)
    assert a.contains(Fraction(3, 2)) and not a.contains(4)


def test_latency_pairs_interval_with_provenance() -> None:
    p = Prov(ProvClass.VENDOR, "blog")
    lat = Latency("ff.default", Interval(0, 150), p)
    assert (lat.key, lat.iv.hi, lat.prov.source) == ("ff.default", 150, "blog")
    assert lat == Latency("ff.default", Interval(0, 150), p)


def test_unbounded_interval_propagates() -> None:
    u = Interval(1, None)
    assert not u.bounded
    assert (u + Interval(1, 2)).hi is None
    assert u.hull(Interval(0, 5)) == Interval(0, None)
    assert u.contains(10**9)
