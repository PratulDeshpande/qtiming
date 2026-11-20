"""`TimingCheck`: an analysis pass that stores the checker's verdict in the property set."""

from __future__ import annotations

from pathlib import Path

from qiskit.converters import dag_to_circuit
from qiskit.dagcircuit import DAGCircuit
from qiskit.transpiler.basepasses import AnalysisPass
from qiskit.transpiler.exceptions import TranspilerError

from qtiming.contract.model import Contract
from qtiming.frontend import from_circuit
from qtiming.verdict.model import REFUTED, UNKNOWN
from qtiming.verdict.run import check_program

from ._common import as_contract

_FAIL = {"never": (), "refuted": (REFUTED,), "unknown": (REFUTED, UNKNOWN)}


class TimingCheck(AnalysisPass):  # type: ignore[misc]
    """Run `qtiming check` on the circuit. The `Verdict` goes to `property_set["qtiming_verdict"]`.
    `fail_on` is "never", "refuted" (default) or "unknown" (refuted or unknown); a failure
    raises `TranspilerError` naming the verdict. The circuit is never changed."""

    def __init__(self, contract: Contract | str | Path, *, policy: str | None = None,
                 fail_on: str = "refuted") -> None:
        super().__init__()
        if fail_on not in _FAIL:
            raise ValueError(f"fail_on must be one of {sorted(_FAIL)}, not {fail_on!r}")
        self.contract, self.policy, self.fail_on = as_contract(contract), policy, fail_on

    def run(self, dag: DAGCircuit) -> None:
        prog = from_circuit(dag_to_circuit(dag), contract=self.contract)
        v = check_program(prog.body, self.contract, policy=self.policy)
        self.property_set["qtiming_verdict"] = v
        if v.verdict in _FAIL[self.fail_on]:
            why = "; ".join(v.reasons) or "see the verdict in the property set"
            raise TranspilerError(f"qtiming: {v.verdict} under {self.contract.name}: {why}")
