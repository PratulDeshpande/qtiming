"""Appendix A.1 to A.6 of the implementation plan, reproduced exactly (IBM-like contract)."""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parents[2] / "personality"))
from _support import build, make_contract  # noqa: E402

from qtiming.core.ast import BitRef, If, Policy, Seq, SourceLoc, Within  # noqa: E402
from qtiming.dispatch import build_graph  # noqa: E402
from qtiming.elab import elaborate  # noqa: E402
from qtiming.graph.invariants import check_invariants  # noqa: E402
from qtiming.oblig.generate import generate  # noqa: E402
from qtiming.solve.dispatcher import verify  # noqa: E402
from qtiming.verdict.model import PROVED_UNDER, REFUTED, UNKNOWN  # noqa: E402
from qtiming.verdict.run import check_program, max_safe, with_latency_hi  # noqa: E402

# dt = 4 ns: measure 415 dt, ff.default [0, 150] dt (0 to 600 ns), x gate 8 dt.
IBM = {"durations": {"measure": 415, "reset": 25},
       "latencies": [{"key": "ff.default", "src": "measure", "dst": "branch", "lo": 0,
                      "hi": 150}]}


def teleport_correction(deadline: int = 750) -> Seq:
    prog, _ = build([
        {"op": "measure", "id": "m", "q": 1, "bit": 1},
        {"op": "if", "id": "i", "cond": "m",
         "then": [{"op": "gate", "name": "x", "q": [2], "dur": 8}]},
    ])
    m, iff = prog.stmts
    assert isinstance(iff, If)
    loc = SourceLoc("a1")
    iff = replace(iff, policy=Policy("eq"))
    body = Seq(nid=90, loc=loc, stmts=(iff,))
    w = Within(nid=91, loc=loc, deadline=deadline, anchor=BitRef("c", 1), body=body)
    return Seq(nid=92, loc=loc, stmts=(m, w))


def of(v: Any, code: str) -> list[Any]:
    return [r for r in v.results if r.obl.code == code]


def test_a4_a5_proved_under_with_margin_2400_ns() -> None:
    v = check_program(teleport_correction(), make_contract("ibm", IBM))
    assert v.verdict == PROVED_UNDER
    assert {a.key for a in v.assumptions} == {"ff.default"}
    assert v.weakest_class == "vendor"
    o2b, o3, o4, o7 = (of(v, k) for k in ("O2b", "O3", "O4", "O7"))
    assert o2b and all(r.res.kind == "proved" and r.res.tier == 1 for r in o2b)
    # O3: Tier 1, margin 750 - 150 = 600 dt = 2400 ns at dt = 4 ns
    assert o3 and all(r.res.tier == 1 for r in o3)
    assert min(r.res.margin for r in o3) == 600
    assert min(r.res.margin for r in o3) * 4 == 2400
    assert o4 and all(r.res.kind == "proved" for r in o4)
    # O7: Variation(bend, barrier, 0). Ruling: plan A.4 files this under Tier 0, but the block
    # start is max(ready, valid) so theta IS in the cone; Tier 1 proves it with spread 0.
    assert o7 and all(r.res.kind == "proved" and r.res.margin == 0 for r in o7)
    assert not any(r.res.kind in ("refuted", "unknown") for r in v.results)


def test_a5_max_safe_ff_upper_bound_is_750_dt_3000_ns() -> None:
    h = max_safe(teleport_correction(), make_contract("ibm", IBM), "ff.default")
    assert h == 750 and h * 4 == 3000


def test_a6_optimistic_hi_is_never_proved() -> None:
    """The program is elaborated against hi = 100 dt but the true latency reaches 150: O2b needs
    100 - theta >= 0. Tier 1 must not prove it (Tier 2 will later REFUTE it with theta = 150)."""
    c = make_contract("ibm", IBM)
    el = elaborate(teleport_correction(), with_latency_hi(c, "ff.default", 100))
    g = build_graph(el.body, c)
    check_invariants(g)
    res = {o.code: verify(g, o) for o in generate(g, el, c) if o.code in ("O2b", "O4")}
    assert res["O2b"].kind != "proved"
    assert res["O4"].kind != "proved"


def test_deadline_too_tight_is_not_proved() -> None:
    v = check_program(teleport_correction(deadline=100), make_contract("ibm", IBM))  # needs 150
    assert v.verdict in (UNKNOWN, REFUTED)
    assert of(v, "O3") and all(r.res.kind != "proved" for r in of(v, "O3"))
