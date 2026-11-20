"""T4 differential (plan 16.5): windowed and whole-program verdicts agree wherever both run.

The loop is windowed with `unroll_limit=1` and fully unrolled with `unroll_limit=64`, over loop
bodies that prove, refute and go UNKNOWN, on both windowing-capable personalities and three
policies. Plus the H3 smoke: a 20-round repetition code checked through one iteration window.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "personality"))
from _support import build, make_contract  # noqa: E402

from qtiming.verdict.model import PROVED, PROVED_UNDER  # noqa: E402
from qtiming.verdict.run import check_program  # noqa: E402

IBM = {"durations": {"measure": 1000, "reset": 100},
       "latencies": [{"key": "ff.default", "src": "measure", "dst": "branch", "lo": 0, "hi": 600}]}
IBM_NO_HI = {**IBM, "latencies": [{"key": "ff.default", "src": "measure", "dst": "branch",
                                   "lo": 0}]}
QUA_LATS = [
    {"key": "align.same_fem", "src": "align", "dst": "align", "tier": "same_fem", "lo": 0,
     "hi": 12},
    {"key": "align.cross_fem", "src": "align", "dst": "align", "tier": "cross_fem", "lo": 0,
     "hi": 24},
]
B = {"op": "barrier", "q": [0, 1]}
M = {"op": "measure", "id": "m", "q": 0}
G = {"op": "gate", "q": [1], "dur": 8}
BODIES = {
    "equal arms": [B, M, {"op": "if", "cond": "m", "then": [G], "else": [G]}, B],
    "one arm": [B, M, {"op": "if", "cond": "m", "then": [G]}, B],
    "no branch": [B, M, G, B],
    "long gate": [B, {"op": "gate", "q": [0], "dur": 5000}, M, {"op": "if", "cond": "m",
                                                               "then": [G], "else": [G]}, B],
}


@pytest.mark.parametrize("policy", ["eq", "sync", "exp"])
@pytest.mark.parametrize("name", sorted(BODIES))
@pytest.mark.parametrize("spec", [IBM, IBM_NO_HI], ids=["bounded", "unbounded"])
def test_windowed_equals_whole(policy: str, name: str, spec: dict[str, Any]) -> None:
    c = make_contract("ibm", spec)
    prog, _ = build([{"op": "for", "n": 4, "body": BODIES[name]}])
    whole = check_program(prog, c, policy=policy, unroll_limit=64)
    win = check_program(prog, c, policy=policy, unroll_limit=1)
    assert whole.verdict == win.verdict, (whole.reasons, win.reasons)


def test_qua_cut_is_refused_because_align_latency_crosses_it() -> None:
    """Whole-program QUA/eq is REFUTED (O4 gap between joins); a window would miss that."""
    c = make_contract("qua", {**IBM, "latencies": IBM["latencies"] + QUA_LATS,
                              "branch": {"allow_nested": True}})
    prog, _ = build([{"op": "for", "n": 4, "body": BODIES["equal arms"]}])
    assert check_program(prog, c, policy="eq", unroll_limit=64).verdict == "REFUTED"
    v = check_program(prog, c, policy="eq", unroll_limit=1)
    assert v.verdict == "UNKNOWN" and any("rule 4" in r for r in v.reasons)


def test_h3_smoke_20_round_repetition_code() -> None:
    """Syndrome round: join, measure, correct on the outcome, join. 20 rounds."""
    rnd = [B, M, {"op": "if", "cond": "m", "then": [G], "else": [G]}, B]
    prog, _ = build([{"op": "for", "n": 20, "body": rnd}])
    v = check_program(prog, make_contract("ibm", IBM), policy="eq", unroll_limit=4)
    assert v.verdict in (PROVED, PROVED_UNDER) and any("20 iterations" in n for n in v.notes)
