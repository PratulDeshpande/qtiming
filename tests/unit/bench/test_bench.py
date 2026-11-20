"""qtiming-bench: matrix run, unsupported cells are reported, golden compare and update."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("openqasm3")
from qtiming.bench import main  # noqa: E402

SUITE = str(Path(__file__).parents[3] / "benchmarks" / "families")


def test_run_check_roundtrip(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    res, gold = tmp_path / "r.jsonl", tmp_path / "g.json"
    assert main(["run", "--suite", SUITE, "--contracts", "ibm_heron,artiq", "--policies", "eq",
                 "--out", str(res)]) == 0
    rows = [json.loads(x) for x in res.read_text(encoding="utf-8").splitlines()]
    by = {(r["program"], r["contract"]): r["status"] for r in rows}
    assert by[("tp_basic", "ibm_heron")] == "PROVED-UNDER"
    assert by[("tp_basic", "artiq")] == "unsupported"  # no gate durations: reported, not skipped
    assert main(["check", str(res), "--golden", str(gold), "--update"]) == 0
    assert main(["check", str(res), "--golden", str(gold)]) == 0
    g = json.loads(gold.read_text(encoding="utf-8"))
    g["teleportation/tp_basic|ibm_heron|eq"] = "REFUTED"
    gold.write_text(json.dumps(g), encoding="utf-8")
    assert main(["check", str(res), "--golden", str(gold)]) == 1
    assert "MISMATCH teleportation/tp_basic|ibm_heron|eq" in capsys.readouterr().out
