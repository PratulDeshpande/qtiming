"""IBM adapter pieces that need no network: timing-table parsing, .env loading, version guard."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3] / "experiments" / "ibm_dryrun"
spec = importlib.util.spec_from_file_location("ibm_collect2", ROOT / "collect.py")
collect = importlib.util.module_from_spec(spec)
sys.modules["ibm_collect2"] = collect
spec.loader.exec_module(collect)

# Verbatim from IBM's "Visualize circuit timing" page (then-branch only, one conditional block).
TIMING = (
    "main,rz_0,Qubit 0,875,0,shift_phase\nmain,sx_0,Qubit 0,875,6,play\n"
    "main,measure_0,Qubit 0,882,180,play\nmain,measure_0,AWGR0_0,1003,205,capture\n"
    "main,broadcast,Hub,1003,406,broadcast\nmain,receive,Receive,1409,7,receive\n"
    "then,x_0,Qubit 0,1424,6,play\n"
    "main,measure_0,Qubit 0,1437,180,play\nmain,measure_0,AWGR0_0,1558,205,capture\n"
)


def test_parse_pairs_measure_play_with_capture() -> None:
    ins = collect.parse_timing(TIMING)
    meas = [i for i in ins if i["name"].startswith("measure")]
    assert [(m["start_dt"], m["stop_dt"], m["block_id"]) for m in meas] == [
        (882, 1208, None), (1437, 1763, None)]
    assert meas[0]["qubits"] == [0]


def test_parse_marks_conditional_block_and_drops_main_noise() -> None:
    ins = collect.parse_timing(TIMING)
    assert [i for i in ins if i["block_id"] is not None] == [
        {"name": "x_0", "qubits": [0], "start_dt": 1424, "stop_dt": 1430, "block_id": "b1"}]
    assert all(i["name"] != "broadcast" for i in ins)


def test_parse_accepts_list_of_lines_and_rejects_garbage() -> None:
    assert collect.parse_timing(TIMING.splitlines()) == collect.parse_timing(TIMING)
    with pytest.raises(ValueError, match="scheduler_timing"):
        collect.parse_timing("not,a,row")


def test_branches_seen() -> None:
    assert collect.branches_seen(TIMING) == {"then"}


def test_dotenv_fills_only_unset_and_skips_blank(tmp_path: Path) -> None:
    f = tmp_path / ".env"
    f.write_text("# c\nQISKIT_IBM_TOKEN=abc\nQISKIT_IBM_INSTANCE=\nKEEP='new'\n", encoding="utf-8")
    env = {"KEEP": "old"}
    collect.load_dotenv(f, env)
    assert env == {"KEEP": "old", "QISKIT_IBM_TOKEN": "abc"}
    collect.load_dotenv(tmp_path / "missing", env)  # absent file is fine


def test_runtime_version_guard() -> None:
    collect.require_runtime("0.51.0")
    collect.require_runtime("0.52.1")
    with pytest.raises(SystemExit, match="0.51"):
        collect.require_runtime("0.50.2")
