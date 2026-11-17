from fractions import Fraction

import pytest

from qtiming.core.provenance import Assumption, Prov, ProvClass, can_discharge, combine, weakest


def _a(cls: ProvClass, key: str = "ff") -> Assumption:
    kw: dict[str, object] = {}
    if cls == ProvClass.MMAX:
        kw["n"] = 100
    if cls == ProvClass.PCTL:
        kw.update(p=Fraction(99, 100), load="rho=0.8")
    if cls == ProvClass.MSIGMA:
        kw["k_sigma"] = Fraction(3)
    return Assumption(key, 0, 10, Prov(cls, "src", **kw))  # type: ignore[arg-type]


def test_hard_discharge_requires_cyc_or_cert() -> None:
    assert ProvClass.CYC.may_discharge_hard and ProvClass.CERT.may_discharge_hard
    for c in (ProvClass.VENDOR, ProvClass.MSIGMA, ProvClass.PCTL, ProvClass.MMAX, ProvClass.SCHED):
        assert not c.may_discharge_hard


def test_can_discharge() -> None:
    strong = frozenset({_a(ProvClass.CYC, "a"), _a(ProvClass.CERT, "b")})
    mixed = frozenset({_a(ProvClass.CYC, "a"), _a(ProvClass.VENDOR, "b")})
    assert can_discharge(True, strong)
    assert not can_discharge(True, mixed)
    assert can_discharge(False, mixed)       # advisory obligations are never blocked
    assert can_discharge(True, frozenset())  # nothing assumed


def test_weakest_and_empty() -> None:
    assert weakest([]) is None
    assert weakest([_a(ProvClass.CERT, "a"), _a(ProvClass.MMAX, "b")]) == ProvClass.MMAX


def test_combine_keeps_every_assumption() -> None:
    x, y = frozenset({_a(ProvClass.CYC, "a")}), frozenset({_a(ProvClass.VENDOR, "b")})
    assert len(combine(x, y)) == 2
    assert combine(x, x) == x


@pytest.mark.parametrize(
    "cls", [ProvClass.MMAX, ProvClass.PCTL, ProvClass.MSIGMA]
)
def test_missing_evidence_fields_rejected(cls: ProvClass) -> None:
    with pytest.raises(ValueError):
        Prov(cls, "src")


def test_vendor_needs_no_extras() -> None:
    assert Prov(ProvClass.VENDOR, "blog").cls == ProvClass.VENDOR
