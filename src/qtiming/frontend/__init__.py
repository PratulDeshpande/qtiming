"""Front ends. `qtiming.frontend.program` and `.payload` are pure; Qiskit loads only on demand."""

from __future__ import annotations

from typing import TYPE_CHECKING

from qtiming.core.errors import QtError

from .program import ContractView, Program

if TYPE_CHECKING:
    from qiskit import QuantumCircuit

__all__ = ["ContractView", "Program", "from_circuit", "from_qasm3", "from_qpy"]


def from_qasm3(text: str, *, filename: str = "<string>",
               contract: ContractView | None = None) -> Program:
    """OpenQASM 3 text through the `openqasm3` parser (no Qiskit needed)."""
    try:
        from .qasm3_fe import from_qasm3 as _from_qasm3
    except ImportError as e:  # the OpenQASM 3 parser ships with the `qiskit` extra
        raise QtError("E-FE-MISSING-EXTRA", "reading OpenQASM 3 needs the openqasm3 parser",
                      hint="pip install 'qtiming[qiskit]'") from e

    return _from_qasm3(text, filename=filename, contract=contract)


def from_circuit(qc: QuantumCircuit, *, contract: ContractView | None = None) -> Program:
    from .qiskit_fe import from_circuit as _from_circuit

    return _from_circuit(qc, contract=contract)


def from_qpy(path: str, *, contract: ContractView | None = None) -> Program:
    from .qiskit_fe import from_circuit as _from_circuit
    from .serialise import qpy_loads

    with open(path, "rb") as fh:
        return _from_circuit(qpy_loads(fh.read()), contract=contract)
