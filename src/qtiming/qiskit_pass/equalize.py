"""`EqualizeBranches`: re-emit each `if` with the barrier, wait and arm padding that EQ elaboration
inserts (plan 8.4), as plain `barrier` and `delay` instructions, so later passes see fixed windows.

The elaborated program carries no gate parameters, so the circuit is rebuilt from the original
and only the synthesised statements are added; every original instruction is kept as is. Each
elaborated `if` is matched to its `IfElseOp` by source order. A program whose elaboration
duplicates an `if` (loops are unrolled) does not match and is refused.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from qiskit import QuantumCircuit
from qiskit.circuit import IfElseOp, Qubit
from qiskit.converters import circuit_to_dag, dag_to_circuit
from qiskit.dagcircuit import DAGCircuit
from qiskit.transpiler.basepasses import TransformationPass
from qiskit.transpiler.exceptions import TranspilerError

from qtiming.contract.model import Contract
from qtiming.core.ast import Barrier, Delay, If, Policy, Seq
from qtiming.elab import elaborate
from qtiming.frontend import from_circuit
from qtiming.verdict.run import with_policy

from ._common import as_contract

_KIDS = ("stmts", "body", "then_", "else_", "default", "exhaust")
_EQ = Policy("eq")


def _kids(s: Any) -> list[Any]:
    out: list[Any] = []
    for f in _KIDS:
        v = getattr(s, f, None)
        out += [x for x in (v if isinstance(v, tuple) else (v,)) if hasattr(x, "nid")]
    return out


def _synth(body: Any) -> list[tuple[list[Any], If]]:
    """(statements synthesised before the `if`, the `if`) per source `if`, in source order."""
    out: list[tuple[list[Any], If]] = []

    def walk(s: Any) -> None:
        if (isinstance(s, Seq) and s.origin_nid is not None and s.stmts
                and isinstance(s.stmts[-1], If) and s.stmts[-1].origin_nid == s.origin_nid):
            out.append((list(s.stmts[:-1]), s.stmts[-1]))
            for c in _kids(s.stmts[-1]):
                walk(c)
            return
        for c in _kids(s):
            walk(c)

    walk(body)
    return out


def _pads(arm: Any) -> list[Any]:
    """The arm's statements in order, with None standing for the original arm content."""
    if arm is None:
        return []
    if isinstance(arm, Seq) and arm.origin_nid is not None:
        return [None if (isinstance(x, Seq) and x.origin_nid is None) else x for x in arm.stmts]
    return [None]


def _emit(tgt: QuantumCircuit, stmts: list[Any], qof: Callable[[int], Any]) -> None:
    for s in stmts:
        if isinstance(s, Delay):
            for q in s.qubits:
                tgt.delay(s.dur, qof(q), unit="dt")
        elif isinstance(s, Barrier):
            tgt.barrier(*[qof(q) for q in s.qubits])
        else:
            raise TranspilerError(f"EqualizeBranches: cannot emit synthesised {type(s).__name__}")


def _count_ifs(qc: QuantumCircuit) -> int:
    n = 0
    for inst in qc.data:
        n += isinstance(inst.operation, IfElseOp)
        for b in getattr(inst.operation, "blocks", ()):
            n += _count_ifs(b)
    return n


class EqualizeBranches(TransformationPass):  # type: ignore[misc]
    def __init__(self, contract: Contract | str | Path) -> None:
        super().__init__()
        self.contract = as_contract(contract)

    def run(self, dag: DAGCircuit) -> DAGCircuit:
        qc = dag_to_circuit(dag)
        body = with_policy(from_circuit(qc, contract=self.contract).body, _EQ)
        found = _synth(elaborate(body, self.contract).body)
        if len(found) != _count_ifs(qc):
            raise TranspilerError("EqualizeBranches: elaboration changed the number of branches "
                                  "(loops are not supported); see `qtiming explain --elaborated`")
        qmap = {i: q for i, q in enumerate(qc.qubits)}
        return circuit_to_dag(self._rewrite(qc, iter(found), qmap)[0])

    def _rewrite(self, qc: QuantumCircuit, it: Any,
                 qmap: dict[int, Any]) -> tuple[QuantumCircuit, list[int]]:
        """Rebuild `qc`; `qmap` maps program qubit index -> this block's qubit. A box that needs
        a qubit it lacks is widened (what elaboration assumed); returns the indices it added."""
        new = qc.copy_empty_like()
        added: list[int] = []
        inv = {q: g for g, q in qmap.items()}

        def need(g: int) -> Any:
            if g not in qmap:
                q = Qubit()
                new.add_bits([q])
                qmap[g] = q
                added.append(g)
            return qmap[g]

        for inst in qc.data:
            op = inst.operation
            if isinstance(op, IfElseOp):
                prefix, elab = next(it)
                _emit(new, prefix, need)
                arms = [(op.blocks[0], _pads(elab.then_)),
                        (op.blocks[1] if len(op.blocks) == 2 else op.blocks[0].copy_empty_like(),
                         _pads(elab.else_))]
                blocks = [self._arm(b, inst, inv, p, it) for b, p in arms]
                if len(op.blocks) == 1 and blocks[1].size() == 0:
                    blocks = blocks[:1]
                new.append(op.replace_blocks(blocks), inst.qubits, inst.clbits)
            elif getattr(op, "blocks", ()):
                blocks, extra = [], []
                for b in op.blocks:
                    cm = {inv[q]: bq for q, bq in zip(inst.qubits, b.qubits, strict=True)}
                    nb, ex = self._rewrite(b, it, cm)
                    blocks.append(nb)
                    extra += ex
                if extra and len(blocks) != 1:
                    raise TranspilerError("EqualizeBranches: padding needs a qubit the control "
                                          "flow does not touch; add it to the block first")
                new.append(op.replace_blocks(blocks),
                           [*inst.qubits, *[need(g) for g in extra]], inst.clbits)
            else:
                new.append(inst)
        return new, added

    def _arm(self, blk: QuantumCircuit, inst: Any, inv: dict[Any, int], pads: list[Any],
             it: Any) -> QuantumCircuit:
        """`blk` with the synthesised padding added; its qubits line up with `inst.qubits`."""
        cm = {inv[q]: blk.qubits[j] for j, q in enumerate(inst.qubits)}

        def qof(g: int) -> Any:
            if g not in cm:
                raise TranspilerError("EqualizeBranches: padding needs a qubit the `if` does "
                                      "not touch; add it to the branch first")
            return cm[g]

        new = blk.copy_empty_like()
        for s in pads:
            if s is None:
                inner, ex = self._rewrite(blk, it, dict(cm))
                if ex:
                    raise TranspilerError("EqualizeBranches: a nested block needs a qubit the "
                                          "`if` does not touch")
                for i2 in inner.data:
                    new.append(i2)
            else:
                _emit(new, [s], qof)
        return new
