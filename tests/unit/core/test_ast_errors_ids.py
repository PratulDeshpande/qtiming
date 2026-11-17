import dataclasses

import pytest

from qtiming.core.ast import (
    Assign,
    Barrier,
    BitRef,
    Box,
    Call,
    Delay,
    For,
    Gate,
    If,
    Measure,
    Policy,
    Reset,
    Seq,
    SourceLoc,
    Switch,
    While,
    Within,
)
from qtiming.core.errors import QtError
from qtiming.core.ids import IdGen, bit_prop, cond_prop
from qtiming.core.labels import EBit, EConst

LOC = SourceLoc("t.qasm", 1, 1)


def test_nodes_are_frozen_and_hashable() -> None:
    g = Gate(nid=1, loc=LOC, name="h", qubits=(0,), dur=4)
    with pytest.raises(dataclasses.FrozenInstanceError):
        g.dur = 5  # type: ignore[misc]
    assert hash(g) == hash(Gate(nid=1, loc=LOC, name="h", qubits=(0,), dur=4))


def test_every_table_node_constructs() -> None:
    m = Measure(nid=2, loc=LOC, qubit=0, cbit=BitRef("c", 0))
    body = Seq(nid=3, loc=LOC, stmts=(m,))
    cond = EBit(bit_prop("c", 0, 2))
    nodes = [
        Delay(nid=4, loc=LOC, qubits=(0,), dur=10),
        Barrier(nid=5, loc=LOC, qubits=(0, 1)),
        Reset(nid=6, loc=LOC, qubit=0),
        Assign(nid=7, loc=LOC, var="x", expr=EConst(1, 4)),
        Box(nid=8, loc=LOC, dur=None, body=body),
        If(nid=9, loc=LOC, cond=cond, then_=body, policy=Policy("sync", delta=3, gap=1)),
        Switch(nid=10, loc=LOC, target=cond, cases=((0, body),), default=None),
        For(nid=11, loc=LOC, var="i", n=3, body=body),
        While(nid=12, loc=LOC, cond=cond, body=body, cap=4, exhaust=body),
        Call(nid=13, loc=LOC, fn="decode", args=(), latency_key="dec", blocking=True),
        Within(nid=14, loc=LOC, deadline=750, anchor=BitRef("c", 0), body=body),
    ]
    assert len({n.nid for n in nodes}) == len(nodes)


def test_while_requires_cap_and_exhaust() -> None:
    with pytest.raises(TypeError):
        While(nid=1, loc=LOC, cond=EBit("x"), body=Seq(nid=2, loc=LOC, stmts=()))  # type: ignore[call-arg]


def test_elaboration_origin_defaults_none() -> None:
    assert Reset(nid=1, loc=LOC, qubit=0).origin_nid is None


def test_qterror_is_raisable_with_fields() -> None:
    with pytest.raises(QtError) as ei:
        raise QtError("E-FE-UNBOUNDED-WHILE", "no cap", loc=LOC, hint="add timing.cap")
    e = ei.value
    assert (e.code, e.severity, e.hint, e.loc) == (
        "E-FE-UNBOUNDED-WHILE", "error", "add timing.cap", LOC)
    assert "E-FE-UNBOUNDED-WHILE" in str(e) and "no cap" in str(e)


def test_idgen_is_sequential_and_independent() -> None:
    a, b = IdGen(), IdGen()
    assert [a.next(), a.next(), a.next()] == [0, 1, 2]
    assert b.next() == 0


def test_proposition_keys() -> None:
    assert bit_prop("c", 0, 17) == "c[0]@m17"
    assert bit_prop("c", 0, 17, 3) == "c[0]@m17#i3"
    assert cond_prop(42, 3) == "cond@n42#i3"
    assert cond_prop(42) == "cond@n42"
    # iterations are distinct observations
    assert bit_prop("c", 0, 17, 1) != bit_prop("c", 0, 17, 2)
