from fractions import Fraction

import pytest

from qtiming.core.ast import BitRef
from qtiming.core.errors import QtError
from qtiming.frontend.payload import (
    Dur,
    parse_call,
    parse_cap,
    parse_duration,
    parse_pmin,
    parse_policy,
    parse_within,
    to_dt,
)

DT = Fraction(4)


@pytest.mark.parametrize(
    ("text", "value", "unit"),
    [("3000ns", 3000, "ns"), ("750dt", 750, "dt"), ("3us", 3, "us"),
     ("1.5us", Fraction(3, 2), "us"), ("2 ms", 2, "ms"), ("1s", 1, "s")],
)
def test_parse_duration(text: str, value: object, unit: str) -> None:
    assert parse_duration(text) == Dur(Fraction(value), unit)  # type: ignore[arg-type]


@pytest.mark.parametrize("text", ["", "ns", "12", "3 parsecs", "-5ns"])
def test_bad_duration(text: str) -> None:
    with pytest.raises(QtError) as ei:
        parse_duration(text)
    assert ei.value.code == "E-FE-ANNOT-PAYLOAD"


def test_to_dt_uses_role_rounding_and_dt_passthrough() -> None:
    assert to_dt(parse_duration("3001ns"), DT, "deadline") == 750  # floor
    assert to_dt(parse_duration("101ns"), DT, "commit_lead") == 26  # ceil
    assert to_dt(parse_duration("3us"), DT, "deadline") == 750
    assert to_dt(parse_duration("750dt"), DT, "deadline") == 750
    with pytest.raises(QtError):
        to_dt(parse_duration("7.5dt"), DT, "deadline")  # dt must be whole


def test_policy_forms() -> None:
    assert parse_policy("eq").kind == "eq"
    assert parse_policy("exp").kind == "exp"
    s = parse_policy("sync(delta=10ns,gap=4ns)")
    assert s.kind == "sync"
    assert s.delta == Dur(Fraction(10), "ns") and s.gap == Dur(Fraction(4), "ns")
    assert parse_policy("sync").delta is None
    for bad in ("fast", "sync(delta=)", "sync(wat=1ns)", "eq(1)"):
        with pytest.raises(QtError):
            parse_policy(bad)


def test_within_and_bit_names() -> None:
    d, bit = parse_within("3000ns c[1]")
    assert d == Dur(Fraction(3000), "ns") and bit == BitRef("c", 1)
    with pytest.raises(QtError) as ei:
        parse_within("3000ns c1")
    assert ei.value.code == "E-FE-ANNOT-BIT"
    with pytest.raises(QtError):
        parse_within("3000ns")


def test_cap() -> None:
    assert parse_cap("4 exhaust=fail") == (4, "fail")
    assert parse_cap("8") == (8, None)
    for bad in ("0", "x", "-1", "4 exhaust="):
        with pytest.raises(QtError):
            parse_cap(bad)


def test_call_and_pmin() -> None:
    assert parse_call("decode latency=dec.rtt") == ("decode", "dec.rtt")
    with pytest.raises(QtError):
        parse_call("decode")
    assert parse_pmin("1/2") == Fraction(1, 2) and parse_pmin("0.25") == Fraction(1, 4)
    for bad in ("0", "1.5", "abc"):
        with pytest.raises(QtError):
            parse_pmin(bad)
