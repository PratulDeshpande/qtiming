import pytest

pytest.importorskip("qiskit")

from qiskit import QuantumCircuit  # noqa: E402
from qiskit.circuit.annotation import Annotation  # noqa: E402

from qtiming.frontend.annotations import Cap, Policy, Within  # noqa: E402
from qtiming.qiskit_pass import StripTimingAnnotations  # noqa: E402


class Other(Annotation):
    namespace = "samplomatic.twirl"

    def __eq__(self, o: object) -> bool:
        return type(o) is Other

    def __hash__(self) -> int:
        return 0


def anns(qc: QuantumCircuit) -> list:
    out = []
    for inst in qc.data:
        out.extend(getattr(inst.operation, "annotations", ()))
        for b in getattr(inst.operation, "blocks", ()):
            out.extend(anns(b))
    return out


def annotated() -> QuantumCircuit:
    qc = QuantumCircuit(3, 2)
    qc.measure(0, 0)
    qc.measure(1, 1)
    with qc.box(annotations=[Policy("eq"), Within("3000ns c[1]")]):  # unwrapped
        with qc.if_test((qc.clbits[1], 1)):
            with qc.box(annotations=[Cap("2")]):  # nested: unwrapped
                qc.x(2)
    with qc.box(annotations=[Policy("exp"), Other()]):  # kept, Other only
        qc.z(2)
    with qc.box():  # the user's own plain box: kept
        qc.h(0)
    with qc.box(duration=100, unit="dt", annotations=[Policy("eq")]):  # has a duration: kept
        qc.x(0)
    return qc


def expected() -> QuantumCircuit:
    qc = QuantumCircuit(3, 2)
    qc.measure(0, 0)
    qc.measure(1, 1)
    with qc.if_test((qc.clbits[1], 1)):
        qc.x(2)
    with qc.box(annotations=[Other()]):
        qc.z(2)
    with qc.box():
        qc.h(0)
    with qc.box(duration=100, unit="dt"):
        qc.x(0)
    return qc


def test_strip_removes_timing_keeps_content_and_other_boxes() -> None:
    qc = annotated()
    before = anns(qc)
    out = StripTimingAnnotations()(qc)
    assert all(not a.namespace.startswith("timing") for a in anns(out))
    assert out == expected()  # DAG equality: same content and dependencies
    assert anns(qc) == before  # the input circuit is not mutated


def test_strip_is_idempotent() -> None:
    once = StripTimingAnnotations()(annotated())
    assert StripTimingAnnotations()(once) == once
