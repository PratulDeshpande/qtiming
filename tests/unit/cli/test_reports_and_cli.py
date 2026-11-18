"""P9: SARIF validated against the official 2.1.0 schema, HTML and JSON reports, and the
explain / lint / replay / contract commands, end to end on the teleportation family."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("openqasm3")
pytest.importorskip("z3")
from qtiming.cli.main import main  # noqa: E402

ROOT = Path(__file__).parents[3]
FAM = ROOT / "benchmarks" / "families" / "teleportation"
TP = str(FAM / "tp_basic")
SYNC = str(FAM / "tp_sync")
SCHEMA = ROOT / "tests" / "fixtures" / "sarif-schema-2.1.0.json"
GATES = ["--assume", "durations.h=32", "--assume", "durations.cx=80", "--assume",
         "durations.x=32", "--assume", "durations.measure=1000", "--assume", "durations.reset=100"]


def run(args: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    rc = main(args)
    return rc, capsys.readouterr().out


def validate_sarif(doc: dict[str, Any]) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.validate(doc, json.loads(SCHEMA.read_text(encoding="utf-8")))


@pytest.mark.parametrize("prog", [TP, SYNC])
def test_sarif_validates_against_the_official_schema(
    prog: str, capsys: pytest.CaptureFixture[str]
) -> None:
    rc, out = run(["check", prog, "--contract", "ibm_heron", "--format", "sarif"], capsys)
    doc = json.loads(out)
    validate_sarif(doc)
    assert doc["version"] == "2.1.0"
    run0 = doc["runs"][0]
    levels = {r["level"] for r in run0["results"]}
    assert "note" in levels  # the assumption
    if prog == SYNC:
        assert rc == 1 and "error" in levels
        bad = next(r for r in run0["results"] if r["ruleId"] == "V-O4")
        assert bad["locations"][0]["physicalLocation"]["region"]["startLine"] >= 1
        assert "\\" not in bad["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
        assert bad["partialFingerprints"]["qtiming/v1"]
        assert bad["properties"]["counterexample"]["omega"]  # the witness travels with the finding
    else:
        assert rc == 0


def test_sarif_fingerprints_are_stable_across_runs(capsys: pytest.CaptureFixture[str]) -> None:
    a = json.loads(run(["check", SYNC, "--contract", "ibm_heron", "--format", "sarif"], capsys)[1])
    b = json.loads(run(["check", SYNC, "--contract", "ibm_heron", "--format", "sarif"], capsys)[1])
    fa = [r["partialFingerprints"] for r in a["runs"][0]["results"] if "partialFingerprints" in r]
    fb = [r["partialFingerprints"] for r in b["runs"][0]["results"] if "partialFingerprints" in r]
    assert fa == fb and fa


def test_lint_sarif_validates(capsys: pytest.CaptureFixture[str]) -> None:
    rc, out = run(["lint", TP, "--contract", "ibm_heron", "--format", "sarif"], capsys)
    validate_sarif(json.loads(out))
    assert rc in (0, 2)


def test_html_report_has_an_inline_timeline(capsys: pytest.CaptureFixture[str]) -> None:
    rc, out = run(["check", SYNC, "--contract", "ibm_heron", "--format", "html"], capsys)
    assert rc == 1
    assert out.lstrip().startswith("<!doctype html>") and "<svg" in out and "REFUTED" in out
    assert "<title>" in out and "O4" in out
    assert "<script" not in out  # static page


def test_json_report_carries_counterexamples(capsys: pytest.CaptureFixture[str]) -> None:
    rc, out = run(["check", SYNC, "--contract", "ibm_heron", "--format", "json"], capsys)
    rep = json.loads(out)
    assert rc == 1 and rep["verdict"] == "REFUTED"
    cx = rep["counterexamples"]
    assert cx and cx[0]["obligation"]["code"] == "O4" and cx[0]["second"] is not None


def test_replay_reproduces_a_counterexample_from_a_saved_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rep = tmp_path / "rep.json"
    assert main(["check", SYNC, "--contract", "ibm_heron", "--format", "json",
                 "--out", str(rep)]) == 1
    capsys.readouterr()
    rc, out = run(["replay", str(rep), SYNC, "--contract", "ibm_heron", "--trace"], capsys)
    assert rc == 0 and out.startswith("REPRODUCED: O4")
    bad = json.loads(rep.read_text(encoding="utf-8"))
    bad["counterexamples"][0]["obligation"]["nid"] = 9999
    rep.write_text(json.dumps(bad), encoding="utf-8")
    assert main(["replay", str(rep), SYNC, "--contract", "ibm_heron"]) == 2


def test_text_report_shows_the_location_and_a_timeline(capsys: pytest.CaptureFixture[str]) -> None:
    rc, out = run(["check", SYNC, "--contract", "ibm_heron"], capsys)
    assert rc == 1
    assert "O4 failed at" in out and "tp_sync.qasm:17" in out.replace("\\", "/")
    assert "timeline (counterexample)" in out and "q2" in out


def test_explain_commands(capsys: pytest.CaptureFixture[str]) -> None:
    rc, out = run(["explain", TP, "--contract", "ibm_heron", "--policy", "eq", "--elaborated"],
                  capsys)
    assert rc == 0 and "Barrier" in out and "synth(from" in out and "If" in out
    rc, out = run(["explain", TP, "--contract", "ibm_heron", "--graph", "dot"], capsys)
    assert out.startswith("digraph lteg") and "ff.default" in out
    rc, out = run(["explain", TP, "--contract", "ibm_heron", "--obligations"], capsys)
    assert "O3 n" in out and "O2b n" in out
    rc, out = run(["explain", TP, "--contract", "ibm_heron"], capsys)
    assert "obligations" in out and "latency variables" in out


def test_contract_show_and_diff(capsys: pytest.CaptureFixture[str]) -> None:
    rc, out = run(["contract", "show", "ibm_heron"], capsys)
    assert rc == 0 and json.loads(out)["personality"] == "ibm"
    assert main(["contract", "diff", "ibm_heron", "ibm_heron"]) == 0
    rc, out = run(["contract", "diff", "ibm_heron", "q1"], capsys)
    assert rc == 1 and "personality" in out


# the teleportation family end to end on all four shipped contracts (plan P9 gate)
ARTIQ_X = ["--assume", "timeline.commit_lead=50", "--assume", "in2cpu=0:300", "--assume",
           "durations.measure=100"]
FAMILY = [
    ("ibm_heron", "tp_basic", [], "PROVED-UNDER"),
    ("ibm_heron", "tp_sync", [], "REFUTED"),
    ("q1", "tp_q1", GATES, "PROVED-UNDER"),
    ("qua", "tp_sync", GATES, "REFUTED"),
    ("artiq", "tp_exp", GATES + ARTIQ_X, "UNKNOWN"),
]


@pytest.mark.parametrize("contract,prog,extra,want", FAMILY,
                         ids=[f"{c}-{p}" for c, p, _, _ in FAMILY])
def test_teleportation_family_on_every_contract(
    contract: str, prog: str, extra: list[str], want: str, capsys: pytest.CaptureFixture[str]
) -> None:
    rc, out = run(["check", str(FAM / prog), "--contract", contract, *extra], capsys)
    assert out.startswith(want), out[:200]
    assert rc == {"PROVED-UNDER": 0, "REFUTED": 1, "UNKNOWN": 3}[want]
