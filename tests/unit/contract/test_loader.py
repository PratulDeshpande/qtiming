import copy
import json
from fractions import Fraction
from types import SimpleNamespace

import pytest

from qtiming.contract.loader import ContractLoadError, load_contract, load_contract_dict
from qtiming.contract.target_import import snapshot_from_target
from qtiming.core.errors import QtError
from qtiming.core.provenance import ProvClass

BASE = {
    "meta": {"name": "t", "version": "0.1.0", "schema": "qtiming-contract/0.2",
             "personality": "q1"},
    "timebase": {"dt_ns": "4"},
    "timeline": {"late_policy": "halt", "commit_lead": 0},
    "latency": [{"key": "ff", "src": "measure", "dst": "branch", "lo_ns": 0, "hi_ns": 600,
                 "prov": "vendor", "source": "unit test"}],
    "branch": {"class": "predicated", "default_policy": "eq"},
}


def raw(**over):
    r = copy.deepcopy(BASE)
    r.update(copy.deepcopy(over))
    return r


def lat(**kw):
    d = {"key": "x", "src": "a", "dst": "b", "lo_ns": 0, "hi_ns": 8, "prov": "vendor",
         "source": "s"}
    d.update(kw)
    return d


def errors_of(r, **kw):
    with pytest.raises(ContractLoadError) as ei:
        load_contract_dict(r, **kw)
    return ei.value


def test_minimal_contract_loads() -> None:
    c = load_contract_dict(raw())
    assert c.dt_ns == Fraction(4) and c.personality == "q1"
    assert c.latency("ff").latency.iv.hi == 150 and c.commit_lead == 0


def test_toml_floats_in_time_fields_are_rejected() -> None:
    r = raw()
    r["latency"][0]["hi_ns"] = 0.1
    e = errors_of(r)
    assert any(x.code == "E-CT-SCHEMA" and "latency.0.hi_ns" in x.message for x in e.errors)


def test_float_in_duration_is_rejected() -> None:
    e = errors_of(raw(durations={"cz": 68.5}))
    assert any("durations.cz" in x.message for x in e.errors)


def test_msigma_without_explicit_hi_is_rejected() -> None:
    e = errors_of(raw(latency=[lat(prov="msigma", k_sigma="3", hi_ns=None)]))
    assert any("hi" in x.message for x in e.errors)


def test_pctl_requires_p_load_and_hi() -> None:
    errors_of(raw(latency=[lat(prov="pctl", hi_ns=None)]))
    ok = load_contract_dict(raw(latency=[lat(prov="pctl", p="0.99", load="rho=0.8")]))
    assert ok.latency("x").latency.prov.cls == ProvClass.PCTL


def test_mmax_requires_n() -> None:
    errors_of(raw(latency=[lat(prov="mmax")]))
    c = load_contract_dict(raw(latency=[lat(prov="mmax", n=50)]))
    assert c.latency("x").latency.prov.n == 50


def test_all_errors_are_collected_not_just_first() -> None:
    e = errors_of(raw(latency=[lat(prov="mmax"), lat(key="y", lo_ns=9, hi_ns=1)]))
    assert len(e.errors) >= 2


def test_missing_required_clause() -> None:
    r = raw()
    del r["branch"]
    e = errors_of(r)
    assert any("branch" in x.message for x in e.errors)


def test_duplicate_latency_keys_rejected() -> None:
    errors_of(raw(latency=[lat(key="k"), lat(key="k")]))


def test_rounding_is_outward_and_warns() -> None:
    c = load_contract_dict(raw(latency=[lat(lo_ns=599, hi_ns=601)]))
    iv = c.latency("x").latency.iv
    assert (iv.lo, iv.hi) == (149, 151)
    assert any(w.startswith("W-CT-ROUND") for w in c.warnings)
    quiet = load_contract_dict(raw(latency=[lat(lo_ns=600, hi_ns=604)]))
    assert not any(w.startswith("W-CT-ROUND") for w in quiet.warnings)


def test_latency_resolution_dt_forces_integer_endpoints() -> None:
    r = raw(latency=[lat(lo_ns=0, hi_ns=7)])
    r["timebase"]["latency_resolution"] = "dt"
    errors_of(r)


def test_exact_duration_must_be_multiple_of_dt() -> None:
    e = errors_of(raw(durations={"cz": 70}))
    assert any(x.code == "E-TIME-EXACT" for x in e.errors)
    assert load_contract_dict(raw(durations={"cz": 68})).duration("cz") == 17


def test_unknown_duration_is_missing_error() -> None:
    with pytest.raises(QtError) as ei:
        load_contract_dict(raw()).duration("nope")
    assert ei.value.code == "E-CT-MISSING"


def test_feedback_tier_must_reference_existing_latency() -> None:
    errors_of(raw(feedback_tier=[{"latency": "ghost", "pairs": "all"}]))
    load_contract_dict(raw(feedback_tier=[{"latency": "ff", "pairs": "all"}]))


def test_loop_consistency() -> None:
    errors_of(raw(loop={"while_supported": True}, branch={
        "class": "predicated", "default_policy": "eq", "allow_loops": False}))


def test_unbounded_latency_and_absent_commit_lead_are_recorded_missing() -> None:
    r = raw(latency=[lat(key="in2cpu", hi_ns=None)])
    r["meta"]["personality"] = "artiq"
    del r["timeline"]["commit_lead"]
    c = load_contract_dict(r)
    assert "latency.in2cpu.hi" in c.missing and "timeline.commit_lead" in c.missing
    assert c.commit_lead is None and c.latency("in2cpu").latency.iv.hi is None


def test_assume_fills_commit_lead_rounding_up_and_flags_latency_placeholders() -> None:
    r = raw(latency=[lat(key="in2cpu", hi_ns=None)])
    r["meta"]["personality"] = "artiq"
    del r["timeline"]["commit_lead"]
    c = load_contract_dict(r, assume=("timeline.commit_lead=101", "in2cpu=0:700"))
    assert c.commit_lead == 26
    assert "timeline.commit_lead" not in c.missing and "latency.in2cpu.hi" not in c.missing
    cl = c.latency("in2cpu")
    assert cl.placeholder and cl.latency.iv.hi == 175
    assert c.assumed == ("timeline.commit_lead=101", "in2cpu=0:700")


def test_sha256_stable_and_sensitive() -> None:
    a = load_contract_dict(raw())
    assert a.sha256 == load_contract_dict(raw()).sha256
    r = raw()
    r["latency"][0]["hi_ns"] = 604
    assert load_contract_dict(r).sha256 != a.sha256


def test_sha256_independent_of_toml_key_order(tmp_path) -> None:
    t1 = tmp_path / "a.toml"
    t2 = tmp_path / "b.toml"
    t1.write_text(
        '[meta]\nname="t"\nversion="1"\nschema="qtiming-contract/0.2"\npersonality="q1"\n'
        '[timebase]\ndt_ns="4"\n[timeline]\nlate_policy="halt"\n'
        '[branch]\nclass="predicated"\ndefault_policy="eq"\n'
        '[[latency]]\nkey="k"\nsrc="a"\ndst="b"\nhi_ns=8\nprov="vendor"\nsource="s"\n')
    t2.write_text(
        '[[latency]]\nsource="s"\nprov="vendor"\nhi_ns=8\ndst="b"\nsrc="a"\nkey="k"\n'
        '[branch]\ndefault_policy="eq"\nclass="predicated"\n'
        '[timeline]\nlate_policy="halt"\n[timebase]\ndt_ns="4"\n'
        '[meta]\npersonality="q1"\nschema="qtiming-contract/0.2"\nversion="1"\nname="t"\n')
    assert load_contract(str(t1)).sha256 == load_contract(str(t2)).sha256


def test_json_contract_loads(tmp_path) -> None:
    p = tmp_path / "c.json"
    p.write_text(json.dumps(raw()))
    assert load_contract(str(p)).name == "t"


# ---- Target handling (finding F20/F21) ----

SNAP = {"backend": "ibm_test", "unofficial": True, "dt_ns": "4",
        "alignments": {"acquire": 1, "pulse": 1, "granularity": 1},
        "durations_ns": {"measure": "2180", "measure_2": "1380"}}


def ibm_raw(**over):
    r = raw(**over)
    r["meta"]["personality"] = "ibm"
    r["timebase"] = {"dt_ns": "from_target"}
    r["target"] = {"source": "backend", "backend": "ibm_test",
                   "import": ["dt", "alignments", "durations"]}
    r["durations"] = {"import_from_target": True}
    return r


def test_from_target_requires_a_target() -> None:
    e = errors_of(ibm_raw())
    assert any(x.code == "E-CT-TARGET" for x in e.errors)


def test_target_supplies_dt_durations_and_snapshot_id() -> None:
    c = load_contract_dict(ibm_raw(), target=SNAP)
    assert c.dt_ns == 4 and c.duration("measure") == 545 and c.duration("measure_2") == 345
    assert c.target_snapshot and c.target_snapshot.startswith("ibm_test:")
    assert dict(c.grid)["acquire"] == 1


def test_contract_duration_conflicting_with_target_is_an_error_unless_overridden() -> None:
    r = ibm_raw()
    r["durations"]["measure"] = 1000
    assert any(x.code == "E-CT-TARGET-CONFLICT" for x in errors_of(r, target=SNAP).errors)
    r["durations"]["measure"] = {"ns": 1000, "override": True, "reason": "calibrated"}
    c = load_contract_dict(r, target=SNAP)
    assert c.duration("measure") == 250 and c.overrides == ("durations.measure",)
    r["durations"]["measure"] = {"ns": 1000, "override": True}
    errors_of(r, target=SNAP)  # override without a reason


def test_snapshot_file_relative_to_contract(tmp_path) -> None:
    (tmp_path / "snap.json").write_text(json.dumps(SNAP))
    r = ibm_raw()
    r["target"]["source"] = "snapshot:snap.json"
    assert load_contract_dict(r, base_dir=str(tmp_path)).dt_ns == 4


class FakeTarget:
    dt = 4e-9
    acquire_alignment = 1
    pulse_alignment = 1
    granularity = 1
    min_length = 1
    _ops = {
        "measure": {(0,): SimpleNamespace(duration=2.18e-6),
                    (1,): SimpleNamespace(duration=2.18e-6)},
        "cz": {(0, 1): SimpleNamespace(duration=68e-9), (1, 2): SimpleNamespace(duration=72e-9)},
        "barrier": {None: SimpleNamespace(duration=None)},
    }
    operation_names = list(_ops)

    def __getitem__(self, name):
        return self._ops[name]


def test_snapshot_from_duck_typed_target() -> None:
    s = snapshot_from_target(FakeTarget(), "ibm_x")
    assert s["dt_ns"] == "4" and s["durations_ns"]["measure"] == "2180"
    assert "cz" not in s["durations_ns"] and "cz" in s["ambiguous"]  # differs per qubit pair
    assert "barrier" not in s["durations_ns"]
