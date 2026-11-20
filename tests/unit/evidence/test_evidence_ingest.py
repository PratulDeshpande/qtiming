"""Evidence ingestion (plan 7.7 / 18.3 / P14). All fixtures are SYNTHETIC, never hardware data."""

from __future__ import annotations

import copy
import hashlib
import sys
from pathlib import Path

import pytest

from qtiming.contract.loader import load_contract_dict

try:
    import tomllib
except ModuleNotFoundError:  # py3.10
    import tomli as tomllib  # type: ignore[no-redef]

from qtiming.evidence import EvidenceError, apply_patch, ingest, load_job

sys.path.insert(0, str(Path(__file__).parents[2] / "personality"))
from _support import build  # noqa: E402

FX = Path(__file__).parents[2] / "fixtures" / "evidence"
GOOD = sorted((FX / "conclusive").glob("*.json"))
MIXED = sorted((FX / "inconclusive").glob("*.json"))


def _patch(files, **kw):
    return tomllib.loads(ingest(files, allow_synthetic=True, **kw))


def _base(hi: int = 600) -> dict:
    return {
        "meta": {"name": "t", "version": "0", "schema": "qtiming-contract/0.2",
                 "personality": "ibm"},
        "timebase": {"dt_ns": "1"}, "timeline": {"late_policy": "compile_error"},
        "durations": {"measure": 1000, "reset": 100},
        "latency": [{"key": "ff.default", "src": "measure", "dst": "branch", "lo_ns": 0,
                     "hi_ns": hi, "prov": "vendor", "source": "t"}],
        "branch": {"class": "restricted", "default_policy": "sync", "allow_nested": False},
        "personality_params": {"ibm": {"join_behavior": "pad_to_longest_block"}},
    }


def test_deterministic_bytes():
    a = ingest(GOOD, allow_synthetic=True)
    assert a == ingest(list(reversed(GOOD)), allow_synthetic=True)
    assert a.encode() == ingest(GOOD, allow_synthetic=True).encode()


def test_sha256_recorded():
    p = _patch(GOOD)
    got = {e["file"]: e["sha256"] for e in p["evidence"]}
    for f in GOOD:
        assert got[f.name] == hashlib.sha256(f.read_bytes()).hexdigest()
    assert all(e["synthetic"] is True for e in p["evidence"])


def test_latency_bounds_from_jobs():
    (lat,) = _patch(GOOD)["latency"]
    assert (lat["key"], lat["prov"], lat["n"]) == ("ff.default", "sched", 4)
    assert (lat["lo_ns"], lat["hi_ns"]) == ("450", "520")
    assert "SYNTHETIC" in lat["source"]


def test_join_conclusive_pad():
    ibm = _patch(GOOD)["personality_params"]["ibm"]
    assert ibm["join_behavior"] == "pad_to_longest_block"
    assert ibm["join_behavior_prov"]["prov"] == "sched"


def test_join_inconclusive_is_marked_not_guessed():
    ibm = _patch(MIXED)["personality_params"]["ibm"]
    assert "join_behavior" not in ibm
    assert ibm["join_behavior_prov"]["prov"] == "vendor"
    assert "inconclusive" in ibm["join_behavior_prov"]["source"]


def test_absent_evidence_leaves_fields_absent():
    only_ff = [f for f in GOOD if f.name.startswith("ff")]
    p = _patch(only_ff)
    assert "personality_params" not in p  # no unequal-arm job: join stays whatever it was


def test_refuses_synthetic_by_default_and_non_dry_run(tmp_path):
    with pytest.raises(EvidenceError, match="synthetic"):
        ingest(GOOD)
    bad = tmp_path / "j.json"
    bad.write_text(GOOD[0].read_text().replace('"dry_run": true', '"dry_run": false'))
    with pytest.raises(EvidenceError, match="dry_run"):
        load_job(str(bad))


def test_patch_applies_and_loads():
    patch = _patch(GOOD)
    base = _base()
    snapshot = copy.deepcopy(base)
    patched = apply_patch(base, patch)
    assert base == snapshot  # input untouched
    c = load_contract_dict(patched)
    ff = next(x.latency for x in c.latencies if x.latency.key == "ff.default")
    assert (ff.iv.lo, ff.iv.hi) == (450, 520)
    assert len(patched["evidence"]) == 4
    assert c.sha256 != load_contract_dict(base).sha256


def test_patched_contract_changes_graph_and_executor():
    from qtiming.dispatch import build_graph
    from qtiming.elab import elaborate
    from qtiming.exec.engine import execute

    prog, ids = build([
        {"op": "measure", "id": "m0", "q": 0, "bit": 0},
        {"op": "if", "id": "i0", "cond": "m0", "then": [{"op": "gate", "q": [1], "dur": 10}]},
    ])
    old = load_contract_dict(_base())
    new = load_contract_dict(apply_patch(_base(), _patch(GOOD)))
    g = [build_graph(elaborate(prog, c).body, c) for c in (old, new)]
    assert [(v.lo, v.hi) for v in g[0].lats] == [(0, 600)]
    assert [(v.lo, v.hi) for v in g[1].lats] == [(450, 520)]
    t = [execute(elaborate(prog, c).body, c).times[(ids["m0"], "valid")] for c in (old, new)]
    assert t[0] != t[1]
