"""`StripTimingAnnotations`: turn a circuit annotated for the checker into a submittable one."""

from __future__ import annotations

from typing import Any

from qiskit import QuantumCircuit
from qiskit.circuit import BoxOp
from qiskit.converters import circuit_to_dag, dag_to_circuit
from qiskit.dagcircuit import DAGCircuit
from qiskit.transpiler.basepasses import TransformationPass


def _is_timing(a: Any) -> bool:
    ns = str(getattr(a, "namespace", ""))
    return ns == "timing" or ns.startswith("timing.")


class StripTimingAnnotations(TransformationPass):  # type: ignore[misc]
    """Remove timing.* annotations, at any nesting depth. Unwrap a BoxOp that carried timing
    annotations, has no other annotations and no explicit duration (it existed only to carry
    timing intent). Keep boxes with a duration, with other namespaces, or written plain by the
    user. Builds new ops; the input circuit is never mutated."""

    def run(self, dag: DAGCircuit) -> DAGCircuit:
        for node in dag.control_flow_op_nodes():
            op = node.op
            blocks = [self._strip(b) for b in op.blocks]
            if isinstance(op, BoxOp):
                kept = [a for a in op.annotations if not _is_timing(a)]
                if len(kept) != len(op.annotations) and not kept and op.duration is None:
                    dag.substitute_node_with_dag(node, circuit_to_dag(blocks[0]))
                    continue
                new = op.replace_blocks(blocks)
                new.annotations = kept
            else:
                new = op.replace_blocks(blocks)
            dag.substitute_node(node, new)
        return dag

    def _strip(self, block: QuantumCircuit) -> QuantumCircuit:
        return dag_to_circuit(self.run(circuit_to_dag(block)), copy_operations=False)
