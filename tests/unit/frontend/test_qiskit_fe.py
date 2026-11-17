import pytest

pytest.importorskip("qiskit")
pytest.importorskip("qiskit_qasm3_import")

from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister  # noqa: E402
from qiskit.circuit import Instruction  # noqa: E402
from qiskit.circuit.classical import expr  # noqa: E402

from qtiming.contract.loader import load_contract_dict  # noqa: E402
from qtiming.core.ast import (  # noqa: E402
    Barrier,
    BitRef,
    Box,
    Delay,
    For,
    Gate,
    If,
    Measure,
    Policy,
    Reset,
    Seq,
    Switch,
    While,
)
from qtiming.core.errors import QtError  # noqa: E402
from qtiming.core.ids import bit_prop  # noqa: E402
from qtiming.core.labels import EBit, EUn, evaluate  # noqa: E402
from qtiming.frontend import from_circuit  # noqa: E402
from qtiming.frontend.annotations import Cap, Within  # noqa: E402
from qtiming.frontend.annotations import Policy as PolicyAnn
from qtiming.frontend.qiskit_fe import UNRESOLVED_DUR  # noqa: E402

CONTRACT = load_contract_dict({
    "meta": {"name": "t", "version": "1", "schema": "qtiming-contract/0.2", "personality": "q1"},
    "timebase": {"dt_ns": "4"},
    "timeline": {"late_policy": "halt", "commit_lead": 0},
    "durations": {"h": 32, "x": 32, "z": 32, "cx": 200},
    "latency": [{"key": "ff", "src": "measure", "dst": "branch", "hi_ns": 600,
                 "prov": "vendor", "source": "t"}],
    "branch": {"class": "predicated", "default_policy": "eq"},
})


def walk(s):
    """All nodes, depth first."""
    yield s
    for f in ("stmts",):
        for c in getattr(s, f, ()):
            yield from walk(c)
    for f in ("then_", "else_", "body", "exhaust", "default"):
        c = getattr(s, f, None)
        if c is not None and hasattr(c, "nid"):
            yield from walk(c)
    for _, c in getattr(s, "cases", ()):
        yield from walk(c)


def of(prog, typ):
    return [n for n in walk(prog.body) if isinstance(n, typ)]


def circ(n=3, c=3):
    return QuantumCircuit(QuantumRegister(n, "q"), ClassicalRegister(c, "c"))


def test_gates_measure_and_ids() -> None:
    qc = circ()
    qc.h(0)
    qc.cx(0, 1)
    qc.measure(0, 0)
    p = from_circuit(qc, contract=CONTRACT)
    h, cx, m = p.body.stmts
    assert (type(h), type(cx), type(m)) == (Gate, Gate, Measure)
    assert (h.name, h.qubits, h.dur) == ("h", (0,), 8)
    assert (cx.qubits, cx.dur) == ((0, 1), 50)
    assert (m.qubit, m.cbit, m.variant) == (0, BitRef("c", 0), "std")
    ids = [n.nid for n in walk(p.body)]
    assert len(ids) == len(set(ids))
    assert p.qubits == (0, 1, 2) and BitRef("c", 2) in p.bits


def test_unresolved_duration_without_contract_is_flagged() -> None:
    qc = circ()
    qc.h(0)
    p = from_circuit(qc)
    assert p.body.stmts[0].dur == UNRESOLVED_DUR
    assert any(n.code == "N-FE-DUR-UNRESOLVED" for n in p.notes)


def test_gate_missing_from_contract_is_an_error() -> None:
    qc = circ()
    qc.y(0)
    with pytest.raises(QtError) as ei:
        from_circuit(qc, contract=CONTRACT)
    assert ei.value.code == "E-CT-MISSING"


def test_delay_barrier_reset() -> None:
    qc = circ()
    qc.delay(100, 0, unit="dt")
    qc.delay(40, 1, unit="ns")
    qc.barrier(0, 1)
    qc.reset(2)
    p = from_circuit(qc, contract=CONTRACT)
    d1, d2, b, r = p.body.stmts
    assert (type(d1), d1.dur, d1.declared) == (Delay, 100, True)
    assert d2.dur == 10 and d2.qubits == (1,)
    assert (type(b), b.qubits, type(r), r.qubit) == (Barrier, (0, 1), Reset, 2)


def test_non_dt_delay_needs_a_contract() -> None:
    qc = circ()
    qc.delay(40, 0, unit="ns")
    with pytest.raises(QtError) as ei:
        from_circuit(qc)
    assert ei.value.code == "E-FE-NO-DT"


def test_bit_condition_and_else() -> None:
    qc = circ()
    qc.measure(0, 0)
    with qc.if_test((qc.clbits[0], 1)) as els:
        qc.x(2)
    with els:
        qc.z(2)
    p = from_circuit(qc, contract=CONTRACT)
    m = of(p, Measure)[0]
    i = of(p, If)[0]
    assert i.cond == EBit(bit_prop("c", 0, m.nid))
    assert i.else_ is not None and of(p, Gate)[-1].name == "z"


def test_negative_bit_condition() -> None:
    qc = circ()
    qc.measure(0, 0)
    with qc.if_test((qc.clbits[0], 0)):
        qc.x(2)
    i = of(from_circuit(qc, contract=CONTRACT), If)[0]
    assert isinstance(i.cond, EUn) and i.cond.op == "not"


def test_register_condition_value() -> None:
    qc = circ()
    for k in range(3):
        qc.measure(k, k)
    with qc.if_test((qc.cregs[0], 5)):
        qc.x(2)
    p = from_circuit(qc, contract=CONTRACT)
    i = of(p, If)[0]
    ms = [m.nid for m in of(p, Measure)]
    def env(v):
        return {bit_prop("c", k, ms[k]): (v >> k) & 1 for k in range(3)}
    assert evaluate(i.cond, env(5)) == 1 and evaluate(i.cond, env(4)) == 0


def test_expr_conditions() -> None:
    qc = circ()
    for k in range(3):
        qc.measure(k, k)
    c = qc.cregs[0]
    with qc.if_test(expr.bit_xor(c[0], c[1])):
        qc.x(2)
    with qc.if_test(expr.logic_and(c[0], expr.logic_not(c[2]))):
        qc.x(2)
    with qc.if_test(expr.greater(c, 2)):
        qc.x(2)
    p = from_circuit(qc, contract=CONTRACT)
    ifs = of(p, If)
    ms = [m.nid for m in of(p, Measure)]
    def env(v):
        return {bit_prop("c", k, ms[k]): (v >> k) & 1 for k in range(3)}
    assert [evaluate(ifs[0].cond, env(v)) for v in (0, 1, 3)] == [0, 1, 0]
    assert [evaluate(ifs[1].cond, env(v)) for v in (1, 5)] == [1, 0]
    assert [evaluate(ifs[2].cond, env(v)) for v in (2, 3, 7)] == [0, 1, 1]


def test_unsupported_expr_operator() -> None:
    qc = circ()
    for k in range(3):
        qc.measure(k, k)
    with qc.if_test(expr.equal(expr.shift_left(qc.cregs[0], 1), 2)):
        qc.x(2)
    with pytest.raises(QtError) as ei:
        from_circuit(qc, contract=CONTRACT)
    assert ei.value.code == "E-FE-EXPR-UNSUPPORTED"


def test_reading_an_unwritten_bit() -> None:
    qc = circ()
    with qc.if_test((qc.clbits[0], 1)):
        qc.x(2)
    with pytest.raises(QtError) as ei:
        from_circuit(qc, contract=CONTRACT)
    assert ei.value.code == "E-FE-BIT-UNWRITTEN"


def test_two_measurements_into_one_bit_are_different_propositions() -> None:
    qc = circ()
    qc.measure(0, 0)
    with qc.if_test((qc.clbits[0], 1)):
        qc.x(2)
    qc.measure(1, 0)
    with qc.if_test((qc.clbits[0], 1)):
        qc.z(2)
    p = from_circuit(qc, contract=CONTRACT)
    i1, i2 = of(p, If)
    assert i1.cond != i2.cond


def test_nested_block_maps_to_outer_qubits() -> None:
    qc = circ()
    qc.measure(0, 0)
    with qc.if_test((qc.clbits[0], 1)):
        qc.x(2)
    assert of(from_circuit(qc, contract=CONTRACT), Gate)[0].qubits == (2,)


def test_branch_writer_merge_is_refused_not_guessed() -> None:
    qc = circ()
    qc.measure(0, 0)
    with qc.if_test((qc.clbits[0], 1)) as els:
        qc.measure(1, 1)
    with els:
        pass
    with qc.if_test((qc.clbits[1], 1)):
        qc.x(2)
    with pytest.raises(QtError) as ei:
        from_circuit(qc, contract=CONTRACT)
    assert ei.value.code == "E-FE-UNSUPPORTED"


def test_for_loop_and_switch() -> None:
    qc = circ()
    for k in range(3):
        qc.measure(k, k)
    with qc.for_loop(range(3)):
        qc.h(0)
    with qc.switch(qc.cregs[0]) as case:
        with case(0, 1):
            qc.x(0)
        with case(case.DEFAULT):
            qc.z(0)
    p = from_circuit(qc, contract=CONTRACT)
    assert of(p, For)[0].n == 3
    sw = of(p, Switch)[0]
    assert [v for v, _ in sw.cases] == [0, 1] and sw.default is not None


def test_while_needs_a_cap() -> None:
    qc = circ()
    qc.measure(0, 0)
    with qc.while_loop((qc.clbits[0], 1)):
        qc.h(0)
    with pytest.raises(QtError) as ei:
        from_circuit(qc, contract=CONTRACT)
    assert ei.value.code == "E-FE-UNBOUNDED-WHILE" and "timing.cap" in (ei.value.hint or "")


def test_while_with_cap_from_enclosing_box() -> None:
    qc = circ()
    qc.measure(0, 0)
    with qc.box(annotations=[Cap("4")]):
        with qc.while_loop((qc.clbits[0], 1)):
            qc.h(0)
    w = of(from_circuit(qc, contract=CONTRACT), While)[0]
    assert w.cap == 4 and isinstance(w.exhaust, Seq) and w.exhaust.stmts == ()


def test_cap_exhaust_label_is_refused_until_implemented() -> None:
    qc = circ()
    qc.measure(0, 0)
    with qc.box(annotations=[Cap("4 exhaust=fail")]):
        with qc.while_loop((qc.clbits[0], 1)):
            qc.h(0)
    with pytest.raises(QtError) as ei:
        from_circuit(qc, contract=CONTRACT)
    assert ei.value.code == "E-FE-UNSUPPORTED"


def test_box_annotations_and_policy_propagation() -> None:
    qc = circ()
    qc.measure(0, 0)
    qc.measure(1, 1)
    with qc.box(annotations=[PolicyAnn("sync(delta=10ns,gap=4ns)"), Within("3000ns c[1]")]):
        with qc.if_test((qc.clbits[1], 1)):
            qc.x(2)
    p = from_circuit(qc, contract=CONTRACT)
    b = of(p, Box)[0]
    assert b.annotations == (("policy", "sync(delta=10ns,gap=4ns)"), ("within", "3000ns c[1]"))
    assert of(p, If)[0].policy == Policy("sync", delta=2, gap=1)


def test_eq_policy_needs_no_dt() -> None:
    qc = circ()
    qc.measure(0, 0)
    with qc.box(annotations=[PolicyAnn("eq")]):
        with qc.if_test((qc.clbits[0], 1)):
            qc.x(2)
    assert of(from_circuit(qc), If)[0].policy == Policy("eq")


def test_bad_annotation_anchor_and_payload() -> None:
    qc = circ()
    qc.measure(0, 0)
    with qc.box(annotations=[Within("3000ns c[9]")]):
        qc.x(1)
    with pytest.raises(QtError) as ei:
        from_circuit(qc, contract=CONTRACT)
    assert ei.value.code == "E-FE-ANNOT-BIT"
    qc2 = circ()
    with qc2.box(annotations=[PolicyAnn("fast")]):
        qc2.x(1)
    with pytest.raises(QtError) as ei2:
        from_circuit(qc2, contract=CONTRACT)
    assert ei2.value.code == "E-FE-ANNOT-PAYLOAD"


def test_measure_2_is_the_mid_variant() -> None:
    qc = circ()
    qc.append(Instruction("measure_2", 1, 1, []), [0], [0])
    assert of(from_circuit(qc, contract=CONTRACT), Measure)[0].variant == "mid"


def test_unknown_instruction_is_an_error() -> None:
    qc = circ()
    qc.append(Instruction("weird", 1, 0, []), [0], [])
    with pytest.raises(QtError) as ei:
        from_circuit(qc, contract=CONTRACT)
    assert ei.value.code == "E-FE-UNKNOWN-OP"


def test_front_end_does_not_mutate_the_circuit() -> None:
    qc = circ()
    qc.measure(0, 0)
    with qc.box(annotations=[PolicyAnn("eq")]):
        with qc.if_test((qc.clbits[0], 1)):
            qc.x(2)
    before = qc.copy()
    from_circuit(qc, contract=CONTRACT)
    assert qc == before


def test_qasm3_round_trip_yields_the_same_ast() -> None:
    from qtiming.frontend.program import normalise
    from qtiming.frontend.serialise import qasm3_dumps, qasm3_loads

    qc = circ()
    qc.measure(0, 0)
    qc.measure(1, 1)
    with qc.box(annotations=[PolicyAnn("eq"), Within("3000ns c[1]")]):
        with qc.if_test((qc.clbits[1], 1)):
            qc.x(2)
        with qc.if_test((qc.clbits[0], 1)):
            qc.z(2)
    a = from_circuit(qc, contract=CONTRACT)
    b = from_circuit(qasm3_loads(qasm3_dumps(qc)), contract=CONTRACT)
    assert normalise(a.body) == normalise(b.body)
