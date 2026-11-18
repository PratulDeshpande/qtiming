"""Tier 2 (Z3): refutation with exact rational witnesses, replay, A.6/A.7, unbounded latencies."""

from __future__ import annotations

import sys
from fractions import Fraction
from pathlib import Path

import pytest

pytest.importorskip("z3")
sys.path.insert(0, str(Path(__file__).parents[2] / "personality"))
sys.path.insert(0, str(Path(__file__).parents[2] / "fixtures"))
from _support import build, cases, load_case, make_contract  # noqa: E402
from free_stn_false_proof import artiq_free_stn  # noqa: E402
from test_appendix_a import IBM, teleport_correction  # noqa: E402

from qtiming.core.ast import Policy  # noqa: E402
from qtiming.dispatch import build_graph  # noqa: E402
from qtiming.elab import elaborate  # noqa: E402
from qtiming.exec.engine import execute  # noqa: E402
from qtiming.exec.oracle import Fixed  # noqa: E402
from qtiming.graph.invariants import check_invariants  # noqa: E402
from qtiming.oblig.generate import generate  # noqa: E402
from qtiming.solve.dispatcher import SolveCfg, verify  # noqa: E402
from qtiming.verdict.model import PROVED_UNDER, REFUTED, UNKNOWN  # noqa: E402
from qtiming.verdict.replay import replay  # noqa: E402
from qtiming.verdict.run import check_program, with_latency_hi, with_policy  # noqa: E402

NO_T1 = SolveCfg(use_tier1=False)


def test_a6_optimistic_hi_is_refuted_by_tier2_beyond_100_and_replays() -> None:
    c = make_contract("ibm", IBM)
    el = elaborate(teleport_correction(), with_latency_hi(c, "ff.default", 100))
    g = build_graph(el.body, c)  # the TRUE latency interval is [0, 150]
    check_invariants(g)
    o2b = next(o for o in generate(g, el, c) if o.code == "O2b")
    r = verify(g, o2b)
    assert r.kind == "refuted" and r.tier == 2
    (theta,) = r.theta.values()
    assert isinstance(theta, Fraction) and theta > 100  # the wait of 100 dt no longer covers it
    assert replay(g, o2b, r, el.body, c)  # the independent executor reproduces the stall


def test_tier2_agrees_with_tier1_whenever_tier1_proves() -> None:
    c = make_contract("ibm", IBM)
    el = elaborate(teleport_correction(), c)
    g = build_graph(el.body, c)
    for o in generate(g, el, c):
        if o.deps:
            assert verify(g, o, NO_T1).kind == "proved", o.code  # Tier 1 proved => UNSAT


def test_a7_artiq_underflow_refuted_and_free_stn_gives_a_false_proof() -> None:
    base = load_case(next(p for p in cases("artiq") if "04_delay_restores" in p.name))
    wide = with_latency_hi(base.contract, "in2cpu", 800)
    v = check_program(base.prog, wide)
    assert v.verdict == REFUTED
    o1 = [r for r in v.results if r.obl.code == "O1" and r.res.kind == "refuted"]
    assert o1 and o1[0].res.tier == 2
    (theta,) = o1[0].res.theta.values()
    assert 540 < theta <= 800  # slack = 590 - theta must stay >= 50
    res = execute(base.prog, wide, Fixed(o1[0].res.omega, o1[0].res.theta))
    assert any(x.kind == "underflow" and x.nid == o1[0].obl.nid for x in res.violations)
    assert artiq_free_stn(1700, 0, 800, 50) is True  # the free-time STN calls it consistent
    ok = check_program(base.prog, with_latency_hi(base.contract, "in2cpu", 500))
    assert not any(r.res.kind == "refuted" for r in ok.results if r.obl.code == "O1")


def test_unbounded_latency_is_never_a_tier2_refutation() -> None:
    base = load_case(next(p for p in cases("artiq") if "04_delay_restores" in p.name))
    v = check_program(base.prog, base.contract)  # in2cpu has no hi: the missing number decides
    o1 = [r for r in v.results if r.obl.code == "O1"]
    assert o1 and all(r.res.tier != 2 or r.res.kind != "refuted" for r in o1)
    assert any("in2cpu" in r.res.reason for r in o1 if r.res.kind == "unknown")
    assert v.verdict == UNKNOWN


def test_variation_witness_is_two_replayable_executions() -> None:
    """SYNC leaves a varying gap: O4 is refuted with two executions; EQ repairs it."""
    prog, _ = build([{"op": "measure", "id": "m", "q": 0},
                     {"op": "if", "id": "i", "cond": "m",
                      "then": [{"op": "gate", "name": "x", "q": [1], "dur": 8}]}])
    c = make_contract("ibm", IBM)
    el = elaborate(with_policy(prog, Policy("sync")), c)
    g = build_graph(el.body, c)
    bad = [(o, r) for o in generate(g, el, c) if o.code == "O4"
           for r in [verify(g, o)] if r.kind == "refuted"]
    assert bad and all(r.second is not None for _, r in bad)
    assert all(replay(g, o, r, el.body, c) for o, r in bad)
    assert check_program(prog, c, policy="sync").verdict == REFUTED
    assert check_program(prog, c, policy="eq").verdict == PROVED_UNDER
