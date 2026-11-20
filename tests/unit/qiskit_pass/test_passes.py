import pytest

pytest.importorskip("qiskit")

from qiskit import QuantumCircuit  # noqa: E402
from qiskit.circuit import IfElseOp  # noqa: E402
from qiskit.transpiler import PassManager  # noqa: E402
from qiskit.transpiler.exceptions import TranspilerError  # noqa: E402

from qtiming.frontend import from_circuit  # noqa: E402
from qtiming.frontend.annotations import Policy, Within  # noqa: E402
from qtiming.qiskit_pass import EqualizeBranches, StripTimingAnnotations, TimingCheck  # noqa: E402
from qtiming.qiskit_pass._common import as_contract  # noqa: E402
from qtiming.verdict.run import check_program  # noqa: E402


def teleport(deadline: str = "3000ns c[1]") -> QuantumCircuit:
    qc = QuantumCircuit(3, 2)
    qc.h(1)
    qc.cx(1, 2)
    qc.cx(0, 1)
    qc.h(0)
    qc.measure(0, 0)
    qc.measure(1, 1)
    with qc.box(annotations=[Policy("eq"), Within(deadline)]):
        with qc.if_test((qc.clbits[1], 1)):
            qc.x(2)
    return qc


def walk(qc: QuantumCircuit):
    for i in qc.data:
        yield i.operation
        for b in getattr(i.operation, "blocks", ()):
            yield from walk(b)


def test_timing_check_stores_verdict_and_leaves_circuit_alone() -> None:
    qc = teleport()
    pm = PassManager([TimingCheck("ibm_heron", fail_on="never")])
    assert pm.run(qc) == qc
    assert pm.property_set["qtiming_verdict"].verdict in ("PROVED", "PROVED-UNDER")


def test_timing_check_fail_on_refuted_raises() -> None:
    with pytest.raises(TranspilerError, match="REFUTED"):
        PassManager([TimingCheck("ibm_heron")]).run(teleport("1ns c[1]"))


def test_timing_check_rejects_bad_fail_on() -> None:
    with pytest.raises(ValueError):
        TimingCheck("ibm_heron", fail_on="sometimes")


def test_equalize_pads_arms_and_reverifies() -> None:
    c = as_contract("ibm_heron")
    out = PassManager([EqualizeBranches(c)]).run(teleport())
    ops = list(walk(out))
    (op,) = [o for o in ops if isinstance(o, IfElseOp)]
    assert len(op.blocks) == 2  # the missing else arm now carries padding
    assert any(i.operation.name == "delay" for i in op.blocks[1].data)
    assert any(o.name == "barrier" for o in ops)
    v = check_program(from_circuit(out, contract=c).body, c, policy="eq")
    assert v.verdict in ("PROVED", "PROVED-UNDER")


def test_equalize_keeps_original_instructions() -> None:
    out = PassManager([EqualizeBranches("ibm_heron")]).run(teleport())
    names = [i.operation.name for i in PassManager([StripTimingAnnotations()]).run(out).data]
    assert names[:6] == ["h", "cx", "cx", "h", "measure", "measure"]


def test_equalize_refuses_loops() -> None:
    qc = QuantumCircuit(2, 1)
    qc.measure(0, 0)
    with qc.for_loop(range(3)):
        with qc.if_test((qc.clbits[0], 1)):
            qc.x(1)
    with pytest.raises(TranspilerError):
        PassManager([EqualizeBranches("ibm_heron")]).run(qc)


def test_plugin_checks_then_strips(monkeypatch: pytest.MonkeyPatch) -> None:
    from qtiming.qiskit_pass.plugin import QtimingSchedulingPlugin

    monkeypatch.setenv("QTIMING_CONTRACT", "ibm_heron")
    pm = QtimingSchedulingPlugin().pass_manager(None)
    out = pm.run(teleport())
    assert pm.property_set["qtiming_verdict"].verdict in ("PROVED", "PROVED-UNDER")
    assert not any(getattr(o, "annotations", None) for o in walk(out))
    monkeypatch.delenv("QTIMING_CONTRACT")
    with pytest.raises(ValueError):
        QtimingSchedulingPlugin().pass_manager(None)
