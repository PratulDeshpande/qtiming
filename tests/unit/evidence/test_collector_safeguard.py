"""The IBM dry-run collector must never submit unless asked, and never without dry_run."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3] / "experiments" / "ibm_dryrun"
spec = importlib.util.spec_from_file_location("ibm_collect", ROOT / "collect.py")
collect = importlib.util.module_from_spec(spec)
sys.modules["ibm_collect"] = collect
spec.loader.exec_module(collect)


class FakeRuntime:
    def __init__(self, honour: bool = True) -> None:
        self.calls: list[tuple[dict, bool]] = []
        self.honour = honour

    def submit(self, job_spec: dict, *, dry_run: bool) -> dict:
        self.calls.append((job_spec, dry_run))
        return {"job_id": "fake", "backend": "fake_backend", "runtime_version": "0",
                "qiskit_version": "0", "dry_run": dry_run and self.honour,
                "scheduler_timing": {"instructions": []}}


TOKEN = {"QISKIT_IBM_TOKEN": "x"}


def test_default_is_dry_run_and_never_submits(tmp_path):
    rt = FakeRuntime()
    assert collect.main(["--out", str(tmp_path)], runtime=rt, env={"QISKIT_IBM_TOKEN": "x"}) == 0
    assert rt.calls == []
    files = sorted(tmp_path.glob("*.json"))
    assert files and all(json.loads(f.read_text())["dry_run"] is True for f in files)


def test_submit_without_credentials_refuses(tmp_path):
    rt = FakeRuntime()
    with pytest.raises(SystemExit):
        collect.main(["--submit", "--out", str(tmp_path)], runtime=rt, env={})
    assert rt.calls == [] and not list(tmp_path.glob("*.json"))


def test_submit_always_passes_dry_run_true(tmp_path):
    rt = FakeRuntime()
    collect.main(["--submit", "--out", str(tmp_path)], runtime=rt, env={"QISKIT_IBM_TOKEN": "x"})
    assert rt.calls and all(dr is True for _, dr in rt.calls)


def test_aborts_if_dry_run_not_honoured(tmp_path):
    rt = FakeRuntime(honour=False)
    with pytest.raises(SystemExit):
        collect.main(["--submit", "--out", str(tmp_path)], runtime=rt, env=TOKEN)
    assert len(rt.calls) == 1 and not list(tmp_path.glob("*.json"))


def test_import_does_not_load_ibm_runtime():
    assert "qiskit_ibm_runtime" not in sys.modules
