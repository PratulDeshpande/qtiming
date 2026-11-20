"""`qtiming repair` (plan 12.8): the ARTIQ underflow of Appendix A is fixed and RE-VERIFIED."""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("openqasm3")
sys.path.insert(0, str(Path(__file__).parents[2] / "personality"))
from _support import cases, load_case  # noqa: E402

from qtiming.core.ast import Delay  # noqa: E402
from qtiming.repair.suggest import _find, _max_nid, _wrap, repair  # noqa: E402
from qtiming.verdict.model import REFUTED  # noqa: E402
from qtiming.verdict.run import check_program  # noqa: E402


def _artiq(name: str) -> Any:
    return load_case(next(p for p in cases("artiq") if name in p.name))


def test_artiq_underflow_is_repaired_with_the_exact_shortfall() -> None:
    c = _artiq("02_underflow")  # short 20 dt, +5 dt issue cost of the delay
    r = repair(c.prog, c.contract)
    assert r.before.verdict == REFUTED
    assert r.status == "fixed" and r.after.verdict != REFUTED
    assert [(h.code, h.dur) for h in r.hunks] == [("O1", 25)] and r.idle_dt == 25


def test_the_patch_is_minimal_one_dt_less_still_fails() -> None:
    c = _artiq("02_underflow")
    r = repair(c.prog, c.contract)
    d = _find(r.program, _max_nid(c.prog) + 1)
    assert isinstance(d, Delay) and d.dur == 25
    shorter = _wrap(c.prog, r.hunks[0].nid, replace(d, dur=24))
    assert check_program(shorter, c.contract).verdict == REFUTED


def test_a_clean_program_is_left_alone() -> None:
    c = _artiq("01_pulse")
    r = repair(c.prog, c.contract)
    assert r.status == "ok" and not r.hunks and r.program is c.prog


def test_cli_repair_suggests_a_delay_and_never_claims_a_proof_it_lacks(
        capsys: pytest.CaptureFixture[str]) -> None:
    from qtiming.cli.main import main

    tp = Path(__file__).parents[3] / "benchmarks" / "families" / "teleportation" / "tp_basic"
    a = [f"{k}={v}" for k, v in {
        "durations.h": 20, "durations.cx": 100, "durations.x": 20, "durations.z": 20,
        "durations.s": 20, "durations.measure": 1000, "durations.reset": 100,
        "timeline.commit_lead": 5000}.items()]
    argv = ["repair", str(tp), "--contract", "artiq"] + [x for s in a for x in ("--assume", s)]
    rc = main(argv)
    out = capsys.readouterr().out
    assert "before: REFUTED" in out and "insert before line" in out and "delay[" in out
    assert rc == 3  # O1 is patched, but the unbounded in2cpu / O5 keep the program UNKNOWN
