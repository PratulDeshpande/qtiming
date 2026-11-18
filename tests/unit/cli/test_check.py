"""`qtiming check`: the plan's gate example end to end, exit codes, and REFUTED from Tier 0."""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

pytest.importorskip("openqasm3")
sys.path.insert(0, str(Path(__file__).parents[2] / "personality"))
from _support import build, cases, load_case  # noqa: E402

from qtiming.cli.main import main  # noqa: E402
from qtiming.verdict.model import REFUTED  # noqa: E402
from qtiming.verdict.run import check_program  # noqa: E402

TP = str(Path(__file__).parents[3] / "benchmarks" / "families" / "teleportation" / "tp_basic")


def test_gate_example_proved_under_2400_ns_and_3000_ns(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["check", TP, "--contract", "ibm_heron", "--policy", "eq", "--max-safe",
               "ff.default"])
    out = capsys.readouterr().out
    assert rc == 0
    assert out.startswith("PROVED-UNDER")
    assert "O3: 2 obligation(s): proved (tier 1, margin 2400 ns)" in out
    assert "max safe ff.default.hi: 750 dt = 3000 ns" in out


def test_json_report_has_the_documented_fields(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["check", TP, "--contract", "ibm_heron", "--policy", "eq", "--format", "json"])
    rep = json.loads(capsys.readouterr().out)
    assert rc == 0 and rep["verdict"] == "PROVED-UNDER"
    assert rep["assumptions"][0]["latency"] == "ff.default"
    assert rep["assumptions"][0]["prov"] == "vendor"
    o3 = [o for o in rep["obligations"] if o["code"] == "O3"]
    assert o3 and all(o["margin_ns"] == "2400" for o in o3)
    assert any("O6" in x for x in rep["not_checked"])  # a PROVED never silently covers O6/O8/O9


def test_strict_proved_turns_proved_under_into_failure() -> None:
    assert main(["check", TP, "--contract", "ibm_heron", "--policy", "eq", "--strict-proved"]) == 1


def test_cli_policy_does_not_override_an_annotation(capsys: pytest.CaptureFixture[str]) -> None:
    """`--policy` is only for branches that carry no timing.policy annotation."""
    rc = main(["check", TP, "--contract", "ibm_heron", "--policy", "exp"])
    assert rc == 0 and capsys.readouterr().out.startswith("PROVED-UNDER")


def test_policy_incompatible_request_is_refuted() -> None:
    prog, _ = build([{"op": "measure", "id": "m", "q": 0},
                     {"op": "if", "id": "i", "cond": "m",
                      "then": [{"op": "gate", "name": "x", "q": [1], "dur": 8}]}])
    c = load_case(next(p for p in cases("ibm") if "01_gate" in p.name)).contract
    v = check_program(prog, c, policy="exp")  # no exposed timeline on a restricted backend
    assert v.verdict == REFUTED and v.exit_code == 1
    assert any("policy-incompatible" in r for r in v.reasons)


def test_usage_errors_exit_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check", TP, "--contract", "no_such_backend"]) == 2
    assert main(["check", "no_such_program", "--contract", "ibm_heron"]) == 2
    assert "error:" in capsys.readouterr().err


def test_missing_gate_duration_is_a_usage_error_not_a_guess(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main(["check", TP, "--contract", "q1", "--policy", "eq"])
    assert rc == 2 and "duration" in capsys.readouterr().err


def test_artiq_underflow_is_refuted_by_tier0() -> None:
    c = load_case(next(p for p in cases("artiq") if "02_underflow" in p.name))
    v = check_program(c.prog, c.contract)
    assert v.verdict == REFUTED and v.exit_code == 1
    o1 = [r for r in v.results if r.obl.code == "O1" and r.res.kind == "refuted"]
    assert o1 and o1[0].res.tier == 0 and o1[0].res.shortfall == 20


def test_unknown_when_a_required_contract_number_is_missing() -> None:
    c = load_case(next(p for p in cases("artiq") if "01_pulse" in p.name))
    v = check_program(c.prog, replace(c.contract, commit_lead=None))
    assert v.verdict == "UNKNOWN" and v.exit_code == 3
    assert any("commit_lead" in r for r in v.reasons)


def test_clean_program_with_no_assumptions_is_proved() -> None:
    prog, _ = build([{"op": "gate", "name": "x", "q": [0], "dur": 10},
                     {"op": "gate", "name": "x", "q": [0], "dur": 10}])
    c = load_case(next(p for p in cases("ibm") if "01_gate" in p.name)).contract
    v = check_program(prog, c)
    assert v.verdict == "PROVED" and not v.assumptions
