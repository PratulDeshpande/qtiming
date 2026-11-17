from importlib import resources
from pathlib import Path

import pytest

from qtiming.cli.main import main
from qtiming.contract.loader import load_contract

INST = Path(str(resources.files("qtiming.contract"))) / "instances"
NAMES = ["ibm_heron", "q1", "artiq", "qua"]


@pytest.fixture(params=NAMES)
def contract(request):
    return load_contract(str(INST / f"{request.param}.toml"))


def test_all_four_instances_load(contract) -> None:
    assert contract.sha256 and contract.latencies


def test_every_number_has_a_source(contract) -> None:
    assert all(cl.latency.prov.source.strip() for cl in contract.latencies)
    assert all(ic.source.strip() for ic in contract.issue_cost)


def test_personalities_and_classes() -> None:
    got = {n: load_contract(str(INST / f"{n}.toml")) for n in NAMES}
    assert {n: c.personality for n, c in got.items()} == {
        "ibm_heron": "ibm", "q1": "q1", "artiq": "artiq", "qua": "qua"}
    assert {n: c.branch.klass for n, c in got.items()} == {
        "ibm_heron": "restricted", "q1": "predicated", "artiq": "exposed", "qua": "resync"}


def test_qua_align_entries_are_flagged_placeholders() -> None:
    c = load_contract(str(INST / "qua.toml"))
    for key in ("align.same_fem", "align.cross_fem", "align.cross_chassis"):
        assert c.latency(key).placeholder
    assert not c.latency("active_reset").placeholder


def test_artiq_unpublished_numbers_are_missing_not_defaulted() -> None:
    c = load_contract(str(INST / "artiq.toml"))
    assert c.commit_lead is None and "timeline.commit_lead" in c.missing
    assert "latency.in2cpu.hi" in c.missing


def test_ibm_uses_target_snapshot_and_vendor_ff() -> None:
    c = load_contract(str(INST / "ibm_heron.toml"))
    assert c.target_snapshot and c.dt_ns == 4
    ff = c.latency("ff.default").latency
    assert ff.iv.hi == 150 and ff.prov.cls.name == "VENDOR"
    assert c.duration("measure") > 0 and c.duration("measure_2") > 0
    assert dict(c.params)["ibm"] is not None


def test_q1_consistency_fixture_388ns() -> None:
    c = load_contract(str(INST / "q1.toml"))
    path = c.latency("path.opip.base").hi_ns + c.latency("trigger.network").hi_ns
    assert path == 388                                   # documented worked example
    dt = c.latency("path.opip.base").latency.iv.hi + c.latency("trigger.network").latency.iv.hi
    assert dt * c.dt_ns == 392                           # outward rounding is visible, not hidden
    assert any(w.startswith("W-CT-ROUND") for w in c.warnings)
    assert dict((ic.name, dict(ic.fields)) for ic in c.issue_cost)["cond_jump"] == {
        "taken_ns": 6, "not_taken_ns": 1}


def test_cli_validate(capsys) -> None:
    files = [str(INST / f"{n}.toml") for n in NAMES]
    assert main(["contract", "validate", *files]) == 0
    out = capsys.readouterr().out
    assert out.count("OK") == 4 and "placeholder" in out
    assert main(["contract", "validate", str(INST / "nope.toml")]) != 0
