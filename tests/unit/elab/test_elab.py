"""Elaboration: EQ structure, idempotence, loop unrolling with fresh propositions, limits."""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "personality"))
from _support import build, make_contract  # noqa: E402

from qtiming.core.ast import (  # noqa: E402
    Barrier,
    Delay,
    For,
    If,
    Measure,
    Policy,
    Seq,
    SourceLoc,
    While,
)
from qtiming.core.errors import QtError  # noqa: E402
from qtiming.core.ids import bit_prop  # noqa: E402
from qtiming.core.labels import EBit  # noqa: E402
from qtiming.elab import elaborate  # noqa: E402

IBM = {"durations": {"measure": 1000, "reset": 100},
       "latencies": [{"key": "ff.default", "src": "measure", "dst": "branch", "lo": 0, "hi": 600}]}
G = {"op": "gate", "name": "x", "q": [1]}


def flat(s: Any) -> list[Any]:
    if isinstance(s, Seq):
        return [y for x in s.stmts for y in flat(x)]
    if isinstance(s, If):
        return [s, *flat(s.then_), *(flat(s.else_) if s.else_ else [])]
    return [s]


def force(prog: Any, kind: str) -> Any:
    stmts = tuple(replace(s, policy=Policy(kind)) if isinstance(s, If) else s for s in prog.stmts)
    return replace(prog, stmts=stmts)


def test_eq_inserts_barrier_wait_and_pads_arms() -> None:
    ops = [{"op": "measure", "id": "m", "q": 0},
           {"op": "if", "id": "i", "cond": "m",
            "then": [{**G, "dur": 160}], "else": [{"op": "delay", "q": [1], "dur": 40}]}]
    prog, _ = build(ops)
    el = elaborate(force(prog, "eq"), make_contract("ibm", IBM))
    kinds = [type(x).__name__ for x in flat(el.body)]
    assert kinds[:4] == ["Measure", "Barrier", "Delay", "If"]
    wait = next(x for x in flat(el.body) if isinstance(x, Delay) and x.dur == 600)
    assert wait.declared and wait.origin_nid is not None  # synthesised, exempt from O4a
    iff = next(x for x in flat(el.body) if isinstance(x, If))
    pad = [x for x in flat(iff.else_) if isinstance(x, Delay) and x.origin_nid is not None]
    assert [d.dur for d in pad] == [120]  # else arm padded from 40 to 160
    assert el.policy_map[iff.nid].kind == "eq"


def test_elaboration_is_idempotent() -> None:
    ops = [{"op": "measure", "id": "m", "q": 0},
           {"op": "if", "id": "i", "cond": "m", "then": [{**G, "dur": 160}]}]
    prog, _ = build(ops)
    c = make_contract("ibm", IBM)
    for kind in ("sync", "eq"):
        once = elaborate(force(prog, kind), c).body
        assert elaborate(once, c).body == once


def test_unbounded_latency_is_recorded_not_guessed() -> None:
    spec = {**IBM, "latencies": [{"key": "ff.default", "src": "measure", "dst": "branch",
                                  "lo": 7}]}
    ops = [{"op": "measure", "id": "m", "q": 0},
           {"op": "if", "id": "i", "cond": "m", "then": [{**G, "dur": 10}]}]
    prog, _ = build(ops)
    el = elaborate(force(prog, "eq"), make_contract("ibm", spec))
    assert el.missing == {"ff.default"}
    assert any(isinstance(x, Delay) and x.dur == 7 for x in flat(el.body))  # placeholder = lo


def test_for_unrolls_with_fresh_propositions() -> None:
    loc = SourceLoc("t")
    prog, _ = build([{"op": "measure", "id": "m", "q": 0}])
    loop = For(nid=51, loc=loc, var="i", n=3, body=Seq(nid=50, loc=loc, stmts=(prog.stmts[0],)))
    out = elaborate(Seq(nid=52, loc=loc, stmts=(loop,)), make_contract("ibm", IBM))
    ms = [x for x in flat(out.body) if isinstance(x, Measure)]
    assert len(ms) == 3 and len({m.nid for m in ms}) == 3  # distinct nids => distinct props
    assert all(m.origin_nid is not None for m in ms)


def test_if_inside_an_unrolled_loop_is_elaborated_like_one_outside() -> None:
    """Regression: clones used to carry origin_nid, which elab_if reads as 'already elaborated'."""
    ops = [{"op": "measure", "id": "m", "q": 0},
           {"op": "if", "id": "i", "cond": "m",
            "then": [{**G, "dur": 160}], "else": [{"op": "delay", "q": [1], "dur": 40}]}]
    c = make_contract("ibm", IBM)
    outside, _ = build(ops)
    inside, _ = build([{"op": "for", "n": 2, "body": ops}])
    def waits(p: Any) -> int:  # the EQ wait of 600 dt (the feedforward bound) before each branch
        return sum(isinstance(x, Delay) and x.dur == 600 for x in flat(p))

    one = waits(elaborate(force(outside, "eq"), c).body)
    assert one == 1 and waits(elaborate(force_deep(inside), c).body) == 2  # one per unrolled copy


def force_deep(prog: Any) -> Any:
    loop = prog.stmts[0]
    return replace(prog, stmts=(replace(loop, body=force(loop.body, "eq")),))


def test_for_over_limit_is_refused() -> None:
    loc = SourceLoc("t")
    loop = For(nid=1, loc=loc, var="i", n=100, body=Seq(nid=2, loc=loc, stmts=()))
    with pytest.raises(QtError, match="E-ELAB-LOOP-LIMIT"):
        elaborate(loop, make_contract("ibm", IBM))


def test_while_unrolls_to_nested_ifs_with_exhaust_handler() -> None:
    loc = SourceLoc("t")
    prog, _ = build([{"op": "measure", "id": "m", "q": 0}])
    m = prog.stmts[0]
    exhaust = Delay(nid=60, loc=loc, qubits=(1,), dur=5)
    body = Seq(nid=62, loc=loc, stmts=(Delay(nid=63, loc=loc, qubits=(0,), dur=3),))
    w = While(nid=61, loc=loc, cond=EBit(bit_prop("c", 0, m.nid)), body=body, cap=2,
              exhaust=exhaust, policy=Policy("sync"))
    c = make_contract("ibm", {**IBM, "branch": {"allow_nested": True}})
    out = elaborate(Seq(nid=64, loc=loc, stmts=(m, w)), c)
    assert sum(isinstance(x, If) for x in flat(out.body)) == 3  # iterations 0, 1 and the cap check
    assert any(isinstance(x, Delay) and x.dur == 5 for x in flat(out.body))  # exhaust survives


def test_q1_eq_refuses_when_arm_totals_differ() -> None:
    q1 = {"durations": {"measure": 30, "reset": 10}, "issue_cost": {"nop": 1},
          "params": {"else_time_dt": 1}, "branch": {"allow_nested": True},
          "latencies": [{"key": "trigger.network", "src": "measure", "dst": "branch", "lo": 3,
                         "hi": 20}]}
    ops = [{"op": "measure", "id": "m", "q": 0},
           {"op": "if", "id": "i", "cond": "m", "then": [{**G, "q": [0], "dur": 100}],
            "else": [{**G, "q": [0], "dur": 40}, {**G, "q": [0], "dur": 40}]}]
    prog, _ = build(ops)
    with pytest.raises(QtError, match="E-ELAB-Q1-NOT-EQUALISABLE"):
        elaborate(prog, make_contract("q1", q1))


def test_qua_sync_adds_join_barrier() -> None:
    qua = {"durations": {"measure": 90, "reset": 20}, "branch": {"allow_nested": True},
           "latencies": [{"key": "active_reset", "src": "measure", "dst": "branch", "lo": 0,
                          "hi": 40}]}
    ops = [{"op": "measure", "id": "m", "q": 0},
           {"op": "if", "id": "i", "cond": "m", "then": [{**G, "dur": 10}]}]
    prog, _ = build(ops)
    out = elaborate(prog, make_contract("qua", qua))
    assert isinstance(flat(out.body)[-1], Barrier)
