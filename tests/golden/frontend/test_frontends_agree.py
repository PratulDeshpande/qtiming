"""P3 exit: one program, every input route (Qiskit builder, QPY, OpenQASM 3 via Qiskit, OpenQASM 3
via the `openqasm3` parser) gives the same TQ AST modulo source locations."""

import pytest

pytest.importorskip("qiskit")
pytest.importorskip("qiskit_qasm3_import")
pytest.importorskip("openqasm3")

from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister  # noqa: E402
from qiskit.circuit.classical import expr  # noqa: E402

from qtiming.contract.loader import load_contract_dict  # noqa: E402
from qtiming.frontend import from_circuit, from_qasm3, from_qpy  # noqa: E402
from qtiming.frontend.annotations import Policy, Within  # noqa: E402
from qtiming.frontend.program import normalise  # noqa: E402
from qtiming.frontend.serialise import qasm3_dumps, qasm3_loads, qpy_dumps  # noqa: E402

CONTRACT = load_contract_dict({
    "meta": {"name": "t", "version": "1", "schema": "qtiming-contract/0.2", "personality": "q1"},
    "timebase": {"dt_ns": "4"},
    "timeline": {"late_policy": "halt", "commit_lead": 0},
    "durations": {"h": 32, "x": 32, "z": 32, "cx": 200},
    "latency": [{"key": "ff", "src": "measure", "dst": "branch", "hi_ns": 600,
                 "prov": "vendor", "source": "t"}],
    "branch": {"class": "predicated", "default_policy": "eq"},
})

HEAD = 'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[3] q;\nbit[2] c;\n'

# Section 6.4 / Appendix A teleportation, in the documented text form.
TELEPORT = HEAD + """
h q[1]; cx q[1], q[2];
cx q[0], q[1]; h q[0];
c[0] = measure q[0];
c[1] = measure q[1];
@timing.policy eq
@timing.within 3000ns c[1]
box {
  if (c[1]) { x q[2]; }
  if (c[0]) { z q[2]; }
}
"""


def teleport_circuit() -> QuantumCircuit:
    q, c = QuantumRegister(3, "q"), ClassicalRegister(2, "c")
    qc = QuantumCircuit(q, c)
    qc.h(1)
    qc.cx(1, 2)
    qc.cx(0, 1)
    qc.h(0)
    qc.measure(0, c[0])
    qc.measure(1, c[1])
    with qc.box(annotations=[Policy("eq"), Within(3000, unit="ns", anchor="c[1]")]):
        with qc.if_test((c[1], 1)):
            qc.x(2)
        with qc.if_test((c[0], 1)):
            qc.z(2)
    return qc


def norm(p):
    return (normalise(p.body), p.qubits, p.bits, p.vars)


def test_teleport_same_ast_from_every_route(tmp_path) -> None:
    qc = teleport_circuit()
    want = norm(from_circuit(qc, contract=CONTRACT))
    path = tmp_path / "teleport.qpy"
    path.write_bytes(qpy_dumps(qc))
    routes = {
        "qpy": from_qpy(str(path), contract=CONTRACT),
        "qasm3 via qiskit (documented text)": from_circuit(qasm3_loads(TELEPORT),
                                                           contract=CONTRACT),
        "qasm3 parser (documented text)": from_qasm3(TELEPORT, contract=CONTRACT),
        "qasm3 parser (qiskit's dump)": from_qasm3(qasm3_dumps(qc), contract=CONTRACT),
    }
    for name, prog in routes.items():
        assert norm(prog) == want, name


SHARED = {
    "else_and_elseif": """
c[0] = measure q[0]; c[1] = measure q[1];
if (c[0]) { x q[1]; } else { if (c[1]) { z q[1]; } else { x q[2]; } }
""",
    "comparison_and_not": """
c[0] = measure q[0]; c[1] = measure q[1];
if (c == 2) { z q[2]; }
if (!c[1]) { x q[0]; }
""",
    "for_delay_barrier_reset": """
for int i in [0:3] { x q[0]; }
delay[40ns] q[1];
delay[12dt] q[0], q[2];
barrier q[0], q[1];
reset q[2];
""",
    "capped_while": """
c[0] = measure q[0];
@timing.cap 4
box {
  while (!c[0]) { x q[0]; c[0] = measure q[0]; }
}
""",
    "sync_policy_box": """
c[0] = measure q[0];
@timing.policy sync(delta=8ns,gap=4dt)
box { if (c[0]) { x q[1]; } else { z q[1]; } }
""",
}


@pytest.mark.parametrize("name", sorted(SHARED))
def test_parser_and_qiskit_agree_on_shared_fragment(name: str) -> None:
    text = HEAD + SHARED[name]
    via_qiskit = from_circuit(qasm3_loads(text), contract=CONTRACT)
    via_parser = from_qasm3(text, contract=CONTRACT)
    assert norm(via_parser) == norm(via_qiskit)


def _measured() -> tuple[QuantumCircuit, ClassicalRegister]:
    c = ClassicalRegister(2, "c")
    qc = QuantumCircuit(QuantumRegister(3, "q"), c)
    qc.measure(0, c[0])
    qc.measure(1, c[1])
    return qc, c


def test_parity_and_boolean_qiskit_importer_cannot_read() -> None:
    qc, c = _measured()
    with qc.if_test(expr.bit_xor(c[0], c[1])):
        qc.x(2)
    with qc.if_test(expr.logic_and(c[0], expr.logic_not(c[1]))):
        qc.x(0)
    with qc.if_test(expr.logic_or(expr.logic_not(c[0]), c[1])):
        qc.x(1)
    text = HEAD + """c[0] = measure q[0]; c[1] = measure q[1];
if (c[0] ^ c[1]) { x q[2]; }
if (c[0] && !c[1]) { x q[0]; }
if (!c[0] || c[1]) { x q[1]; }
"""
    assert norm(from_qasm3(text, contract=CONTRACT)) == norm(from_circuit(qc, contract=CONTRACT))


def test_switch_qiskit_importer_cannot_read() -> None:
    qc, c = _measured()
    with qc.switch(c) as case:
        with case(0):
            qc.x(0)
        with case(1, 2):
            qc.z(0)
        with case(case.DEFAULT):
            qc.h(0)
    text = HEAD + ("c[0] = measure q[0]; c[1] = measure q[1];\n"
                   "switch (c) { case 0 { x q[0]; } case 1, 2 { z q[0]; } default { h q[0]; } }\n")
    assert norm(from_qasm3(text, contract=CONTRACT)) == norm(from_circuit(qc, contract=CONTRACT))
