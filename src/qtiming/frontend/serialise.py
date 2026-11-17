"""OpenQASM 3 and QPY (de)serialisation of `timing.*` annotations (requires qiskit).

Verified against Qiskit 2.6.2: handlers are `OpenQASM3Serializer` subclasses keyed by namespace
PREFIX for qasm3 (`annotation_handlers`) and via `.as_qpy()` for QPY (`annotation_factories`).
"""

from __future__ import annotations

import io
from collections.abc import Mapping

from qiskit import QuantumCircuit, qasm3, qpy
from qiskit.circuit.annotation import OpenQASM3Serializer

from qtiming.core.errors import QtError

from .annotations import CLASSES, TimingAnnotation


class TimingQasm3Serializer(OpenQASM3Serializer):  # type: ignore[misc]
    def dump(self, annotation: object) -> str:
        if not isinstance(annotation, TimingAnnotation):
            return NotImplemented  # type: ignore[no-any-return]
        return annotation.payload

    def load(self, namespace: str, payload: str) -> TimingAnnotation:
        kind = namespace.partition(".")[2]
        cls = CLASSES.get(kind)
        if cls is None:
            raise QtError("E-FE-ANNOT-PAYLOAD", f"unknown timing annotation {namespace!r}")
        return cls(payload)


def _handlers(extra: Mapping[str, OpenQASM3Serializer] | None) -> dict[str, OpenQASM3Serializer]:
    return {"timing": TimingQasm3Serializer(), **(extra or {})}


def qasm3_dumps(qc: QuantumCircuit, extra: Mapping[str, OpenQASM3Serializer] | None = None) -> str:
    return str(qasm3.dumps(qc, annotation_handlers=_handlers(extra)))


def qasm3_loads(
    text: str, extra: Mapping[str, OpenQASM3Serializer] | None = None
) -> QuantumCircuit:
    return qasm3.loads(text, annotation_handlers=_handlers(extra))


def _factories(extra: Mapping[str, OpenQASM3Serializer] | None) -> dict[str, object]:
    return {ns: h.as_qpy() for ns, h in _handlers(extra).items()}


def qpy_dumps(qc: QuantumCircuit, extra: Mapping[str, OpenQASM3Serializer] | None = None) -> bytes:
    buf = io.BytesIO()
    qpy.dump(qc, buf, annotation_factories=_factories(extra))  # type: ignore[arg-type]
    return buf.getvalue()


def qpy_loads(
    data: bytes, extra: Mapping[str, OpenQASM3Serializer] | None = None
) -> QuantumCircuit:
    factories = _factories(extra)
    out = qpy.load(io.BytesIO(data), annotation_factories=factories)  # type: ignore[arg-type]
    return out[0]
