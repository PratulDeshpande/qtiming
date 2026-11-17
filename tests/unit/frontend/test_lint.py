from qtiming.core.ast import (
    BitRef,
    Box,
    For,
    Gate,
    If,
    Measure,
    Reset,
    Seq,
    SourceLoc,
    Switch,
    While,
)
from qtiming.core.labels import EBin, EBit, EConst
from qtiming.frontend.lint import lint

LOC = SourceLoc("t", 1, 1)
_n = iter(range(1000))


def nid() -> int:
    return next(_n)


def gate() -> Gate:
    return Gate(nid=nid(), loc=LOC, name="x", qubits=(0,), dur=8)


def seq(*s) -> Seq:
    return Seq(nid=nid(), loc=LOC, stmts=tuple(s))


def cond(op="and", extra=None):
    a, b = EBit("c[0]@m1"), EBit("c[1]@m2")
    return EBin(op, a, b) if extra is None else extra


def if_(then, else_=None, c=None) -> If:
    return If(nid=nid(), loc=LOC, cond=c or EBit("c[0]@m1"), then_=then, else_=else_)


def codes(body, who="ibm") -> set[str]:
    return {e.code for e in lint(body, who)}


def test_clean_single_if_else_passes() -> None:
    assert codes(seq(if_(seq(gate()), seq(gate())))) == set()


def test_only_ibm_has_rules_here() -> None:
    nested = seq(if_(seq(if_(seq(gate())))))
    assert codes(nested, "q1") == set() and codes(nested, "artiq") == set()


def test_nested_if() -> None:
    assert codes(seq(if_(seq(if_(seq(gate())))))) == {"E-LINT-IBM-NESTED-IF"}


def test_else_if_chain_is_its_own_rule() -> None:
    chain = if_(seq(gate()), else_=if_(seq(gate())))
    assert codes(seq(chain)) == {"E-LINT-IBM-ELSEIF"}


def test_loops_and_switch() -> None:
    body = seq(gate())
    f = For(nid=nid(), loc=LOC, var="i", n=2, body=body)
    w = While(nid=nid(), loc=LOC, cond=EBit("c[0]@m1"), body=body, cap=3, exhaust=body)
    s = Switch(nid=nid(), loc=LOC, target=EBit("c[0]@m1"), cases=((0, body),))
    assert codes(seq(f)) == {"E-LINT-IBM-LOOP"}
    assert codes(seq(w)) == {"E-LINT-IBM-LOOP"}
    assert codes(seq(s)) == {"E-LINT-IBM-LOOP"}


def test_measure_or_reset_in_conditional() -> None:
    m = Measure(nid=nid(), loc=LOC, qubit=0, cbit=BitRef("c", 0))
    r = Reset(nid=nid(), loc=LOC, qubit=0)
    assert codes(seq(if_(seq(m)))) == {"E-LINT-IBM-MEAS-IN-IF"}
    assert codes(seq(if_(seq(r)))) == {"E-LINT-IBM-MEAS-IN-IF"}
    assert codes(seq(m, r)) == set()  # fine outside a conditional


def test_arithmetic_in_condition() -> None:
    arith = EBin("gt", EBin("add", EBit("c[0]@m1"), EBit("c[1]@m2")), EConst(1, 2))
    assert codes(seq(if_(seq(gate()), c=arith))) == {"E-LINT-IBM-ARITH-COND"}
    parity = EBin("xor", EBit("c[0]@m1"), EBit("c[1]@m2"))
    assert codes(seq(if_(seq(gate()), c=parity))) == set()


def test_operand_width_over_32_bits() -> None:
    wide = EConst(0, 1)
    for i in range(33):
        wide = EBin("and", wide, EBit(f"c[{i}]@m{i}"))
    assert codes(seq(if_(seq(gate()), c=wide))) == {"E-LINT-IBM-OPERAND-WIDTH"}


def test_box_is_flagged_as_warning_only() -> None:
    b = Box(nid=nid(), loc=LOC, dur=None, body=seq(gate()), annotations=(("timing.policy", "eq"),))
    errs = lint(seq(b), "ibm")
    assert [e.code for e in errs] == ["E-LINT-IBM-BOX"] and errs[0].severity == "warning"


def test_findings_point_at_the_offending_node() -> None:
    inner = if_(seq(gate()))
    errs = lint(seq(if_(seq(inner))), "ibm")
    assert errs[0].loc == LOC and errs[0].hint
