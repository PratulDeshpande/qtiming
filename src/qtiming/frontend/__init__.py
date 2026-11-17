"""Front ends. `qtiming.frontend.program` and `.payload` are pure; Qiskit loads only on demand."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .program import ContractView, Program

if TYPE_CHECKING:
    from qiskit import QuantumCircuit

__all__ = ["ContractView", "Program", "from_circuit", "from_qpy"]


def from_circuit(qc: QuantumCircuit, *, contract: ContractView | None = None) -> Program:
    from .qiskit_fe import from_circuit as _from_circuit

    return _from_circuit(qc, contract=contract)


def from_qpy(path: str, *, contract: ContractView | None = None) -> Program:
    from .qiskit_fe import from_circuit as _from_circuit
    from .serialise import qpy_loads

    with open(path, "rb") as fh:
        return _from_circuit(qpy_loads(fh.read()), contract=contract)
