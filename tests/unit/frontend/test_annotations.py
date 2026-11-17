import pytest

pytest.importorskip("qiskit")
pytest.importorskip("qiskit_qasm3_import")

from qiskit import QuantumCircuit  # noqa: E402
from qiskit.circuit.annotation import Annotation, OpenQASM3Serializer  # noqa: E402

from qtiming.frontend.annotations import (  # noqa: E402
    Call,
    Cap,
    Cut,
    DeclaredIdle,
    Hard,
    PMin,
    Policy,
    Within,
    timing_annotations,
)
from qtiming.frontend.serialise import (  # noqa: E402
    qasm3_dumps,
    qasm3_loads,
    qpy_dumps,
    qpy_loads,
)


class Other(Annotation):
    """A second namespace, standing in for IBM's Samplomatic."""

    namespace = "samplomatic.twirl"

    def __init__(self, payload: str = "") -> None:
        self.payload = payload

    def __eq__(self, o: object) -> bool:
        return isinstance(o, Other) and o.payload == self.payload

    def __hash__(self) -> int:
        return hash(self.payload)


class OtherSer(OpenQASM3Serializer):
    def dump(self, annotation):
        return annotation.payload if isinstance(annotation, Other) else NotImplemented

    def load(self, namespace, payload):
        return Other(payload)


def circuit(*anns) -> QuantumCircuit:
    qc = QuantumCircuit(3, 2)
    qc.measure(0, 0)
    qc.measure(1, 1)
    with qc.box(annotations=list(anns)):
        with qc.if_test((qc.clbits[1], 1)):
            qc.x(2)
        with qc.if_test((qc.clbits[0], 1)):
            qc.z(2)
    return qc


ALL = [Policy("sync(delta=10ns,gap=4ns)"), Within("3000ns c[1]"), Cap("4 exhaust=fail"),
       PMin("1/2"), DeclaredIdle(), Call("decode latency=dec"), Hard(), Cut()]


def test_namespaces_and_equality() -> None:
    assert Policy("eq").namespace == "timing.policy" and Hard().namespace == "timing.hard"
    assert Policy("eq") == Policy("eq") and Policy("eq") != Policy("exp")
    assert Policy("eq") != Within("eq")
    assert len({Policy("eq"), Policy("eq")}) == 1


def test_within_convenience_constructor() -> None:
    assert Within(3000, unit="ns", anchor="c[1]") == Within("3000ns c[1]")


def test_qasm3_text_matches_the_documented_form() -> None:
    text = qasm3_dumps(circuit(Policy("eq"), Within("3000ns c[1]")))
    assert "@timing.policy eq" in text and "@timing.within 3000ns c[1]" in text


def test_qasm3_round_trip_every_annotation() -> None:
    qc = circuit(*ALL)
    assert qasm3_loads(qasm3_dumps(qc)) == qc


def test_qpy_round_trip_every_annotation() -> None:
    qc = circuit(*ALL)
    assert qpy_loads(qpy_dumps(qc)) == qc


def test_second_namespace_survives_round_trip() -> None:
    qc = circuit(Policy("eq"), Other("seed=3"))
    handlers = {"samplomatic": OtherSer()}
    assert qasm3_loads(qasm3_dumps(qc, handlers), handlers) == qc
    assert qpy_loads(qpy_dumps(qc, handlers), handlers) == qc


def test_timing_annotations_extracts_only_our_namespace_in_a_stable_order() -> None:
    qc = circuit(Other("x"), Within("3000ns c[1]"), Policy("eq"))
    box = qc.data[-1].operation
    assert timing_annotations(box.annotations) == (
        ("within", "3000ns c[1]"), ("policy", "eq"))
