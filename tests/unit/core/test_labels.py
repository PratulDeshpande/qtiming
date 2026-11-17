import pytest

from qtiming.core.errors import QtError
from qtiming.core.labels import (
    TOP,
    EBin,
    EBit,
    EConst,
    EUn,
    EVar,
    Lit,
    conj,
    consistent,
    evaluate,
    implies,
)

A, NA, B = Lit("a"), Lit("a", False), Lit("b")


def test_consistent_and_conj() -> None:
    assert consistent(frozenset({A}), frozenset({B}))
    assert not consistent(frozenset({A}), frozenset({NA}))
    assert conj(frozenset({A}), frozenset({B})) == frozenset({A, B})
    assert conj(frozenset({A}), frozenset({NA})) is None
    assert conj(TOP, TOP) == TOP


def test_implies() -> None:
    assert implies(frozenset({A, B}), frozenset({A}))
    assert implies(frozenset({A}), TOP)
    assert not implies(TOP, frozenset({A}))


def test_evaluate_bits_and_logic() -> None:
    env = {"p": 1, "q": 0}
    assert evaluate(EBit("p"), env) == 1
    assert evaluate(EUn("not", EBit("p")), env) == 0
    assert evaluate(EBin("and", EBit("p"), EBit("q")), env) == 0
    assert evaluate(EBin("or", EBit("p"), EBit("q")), env) == 1
    assert evaluate(EBin("xor", EBit("p"), EBit("q")), env) == 1  # parity


def test_evaluate_register_comparison_without_disjuncts() -> None:
    # c > 2 over 3 bits is ONE derived expression (no label duplication)
    bits = [EBit("c0"), EBit("c1"), EBit("c2")]
    value = EBin("add", EBin("add", bits[0], EBin("mul", EConst(2), bits[1])),
                 EBin("mul", EConst(4), bits[2]))
    gt2 = EBin("gt", value, EConst(2, 3))
    assert evaluate(gt2, {"c0": 1, "c1": 0, "c2": 1}) == 1   # 5 > 2
    assert evaluate(gt2, {"c0": 0, "c1": 1, "c2": 0}) == 0   # 2 > 2


def test_evaluate_var_and_missing() -> None:
    assert evaluate(EVar("x", 4), {"x": 9}) == 9
    with pytest.raises(QtError) as ei:
        evaluate(EBit("nope"), {})
    assert ei.value.code == "E-LABEL-UNBOUND"


def test_unknown_operator_rejected() -> None:
    with pytest.raises(QtError):
        evaluate(EBin("frobnicate", EConst(1), EConst(2)), {})
