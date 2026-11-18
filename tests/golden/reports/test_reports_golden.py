"""Snapshot tests for the report formats (plan P9 gate). Regenerate deliberately with
`QTIMING_UPDATE_GOLDEN=1 pytest tests/golden/reports` and review the diff."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytest.importorskip("openqasm3")
pytest.importorskip("z3")
from qtiming.cli.main import main  # noqa: E402

ROOT = Path(__file__).parents[3]
SNAP = Path(__file__).parent / "snapshots"
CASES = [
    ("tp_basic_ibm", "benchmarks/families/teleportation/tp_basic"),
    ("tp_sync_ibm", "benchmarks/families/teleportation/tp_sync"),
]


@pytest.mark.parametrize("fmt,ext", [("text", "txt"), ("json", "json"), ("sarif", "sarif")])
@pytest.mark.parametrize("name,prog", CASES, ids=[c[0] for c in CASES])
def test_report_matches_snapshot(
    name: str, prog: str, fmt: str, ext: str,
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.chdir(ROOT)  # relative paths keep the snapshots machine independent
    out = tmp_path / f"out.{ext}"
    main(["check", prog, "--contract", "ibm_heron", "--format", fmt, "--out", str(out)])
    got = out.read_text(encoding="utf-8").replace("\r\n", "\n")
    snap = SNAP / f"{name}.{ext}"
    if os.environ.get("QTIMING_UPDATE_GOLDEN") == "1" or not snap.exists():
        SNAP.mkdir(parents=True, exist_ok=True)
        snap.write_text(got, encoding="utf-8", newline="\n")
        pytest.skip(f"snapshot {snap.name} written")
    assert got == snap.read_text(encoding="utf-8").replace("\r\n", "\n")
