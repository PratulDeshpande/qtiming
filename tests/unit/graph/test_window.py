"""P10 windowing: cut rules (plan 9.7) and summarised loops (plan 8.6)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "personality"))
from _support import build, make_contract  # noqa: E402

from qtiming.core.ast import For, Seq, SourceLoc  # noqa: E402
from qtiming.core.errors import QtError  # noqa: E402
from qtiming.graph.window import split_loops  # noqa: E402
from qtiming.verdict.model import PROVED, PROVED_UNDER, REFUTED, UNKNOWN  # noqa: E402

# the `what` argument below is only the case id shown in the test report
from qtiming.verdict.run import check_program  # noqa: E402

LOC = SourceLoc("t")
IBM = {"durations": {"measure": 1000, "reset": 100},
       "latencies": [{"key": "ff.default", "src": "measure", "dst": "branch", "lo": 0, "hi": 600}]}
ALL = [0, 1]
B = {"op": "barrier", "q": ALL}


def program(pre: list, body: list, post: list, n: int = 100) -> Seq:
    """pre ; for n { body } ; post, one builder so node ids and bit names are shared."""
    prog, _ = build([*pre, {"op": "for", "n": n, "body": body}, *post])
    assert isinstance(prog, Seq)
    return prog


def round_body(extra: list | None = None) -> list:
    return [B, {"op": "measure", "id": "m", "q": 0},
            {"op": "if", "id": "i", "cond": "m", "then": [{"op": "gate", "q": [1], "dur": 8}],
             "else": [{"op": "gate", "q": [1], "dur": 8}]},  # equal arms: no outcome-dependent gap
            *(extra or []), B]


def test_loop_over_limit_is_split_into_rest_and_one_window() -> None:
    prog = program([{"op": "gate", "q": [0], "dur": 4}, {"op": "gate", "q": [1], "dur": 4}],
                   round_body(), [{"op": "gate", "q": [0], "dur": 4}])
    w = split_loops(prog, make_contract("ibm", IBM), 64)
    assert len(w.bodies) == 1 and not any(isinstance(s, For) for s in w.rest.stmts)


def test_loop_within_limit_is_left_for_unrolling() -> None:
    prog = program([], round_body(), [], n=3)
    w = split_loops(prog, make_contract("ibm", IBM), 64)
    assert w.bodies == () and w.rest is prog


@pytest.mark.parametrize("what, body, hint", [
    ("missing join", [{"op": "gate", "q": [0], "dur": 4}, B], "join"),  # rule 1: no opening join
    ("partial join", [{"op": "barrier", "q": [0]}, {"op": "gate", "q": [1], "dur": 4},
                      {"op": "barrier", "q": [0]}], "join"),  # q1 is live but not joined
    ("cross-cut read", [B, {"op": "if", "id": "i", "cond": "m",
                            "then": [{"op": "gate", "q": [1], "dur": 8}]}, B], "cross"),  # rule 3
])
def test_cut_refusals_name_the_failed_rule(what: str, body: list, hint: str) -> None:
    pre = [{"op": "measure", "id": "m", "q": 0}]
    prog = program(pre, body, [])
    with pytest.raises(QtError, match="E-GRAPH-CUT") as e:
        split_loops(prog, make_contract("ibm", IBM), 64)
    assert hint in e.value.message


def test_noncanonical_personality_state_refuses_the_cut() -> None:  # rule 4
    prog = program([], round_body(), [])
    c = make_contract("artiq", {"durations": {"measure": 1000}, "latencies": IBM["latencies"]})
    with pytest.raises(QtError, match="E-GRAPH-CUT") as e:
        split_loops(prog, c, 64)
    assert "artiq" in e.value.message


def test_post_loop_read_of_a_loop_measurement_is_cross_cut() -> None:
    prog = program([], round_body(), [{"op": "if", "cond": "m", "then": []}])
    with pytest.raises(QtError, match="cross-cut"):
        split_loops(prog, make_contract("ibm", IBM), 64)


def test_windowed_check_agrees_with_whole_program_unrolled() -> None:
    """T4 on a small instance: n = 5 checked windowed (limit 2) and fully unrolled (limit 64)."""
    c = make_contract("ibm", IBM)
    prog = program([], round_body(), [], n=5)
    whole = check_program(prog, c, policy="eq")
    windowed = check_program(prog, c, policy="eq", unroll_limit=2)
    assert whole.verdict == windowed.verdict
    assert windowed.verdict in (PROVED, PROVED_UNDER)
    assert any("window" in n for n in windowed.notes)


def test_windowed_refutation_is_found_in_the_iteration_window() -> None:
    c = make_contract("ibm", IBM)
    one_armed = [B, {"op": "measure", "id": "m", "q": 0},
                 {"op": "if", "cond": "m", "then": [{"op": "gate", "q": [1], "dur": 8}]}, B]
    bad = program([], one_armed, [], n=100)
    windowed = check_program(bad, c)  # n = 100 > 64: one iteration window
    whole = check_program(bad, c, unroll_limit=200)  # all 100 iterations unrolled
    assert windowed.verdict == whole.verdict == REFUTED
    assert any("window" in n for n in windowed.notes)


def test_refused_cut_gives_unknown_naming_the_rule() -> None:
    prog = program([], [{"op": "gate", "q": [0], "dur": 4}], [])
    v = check_program(prog, make_contract("ibm", IBM))
    assert v.verdict == UNKNOWN and any("E-GRAPH-CUT" in r and "join" in r for r in v.reasons)
    # --no-window: the old hard error is kept
    with pytest.raises(QtError, match="E-ELAB-LOOP-LIMIT"):
        check_program(prog, make_contract("ibm", IBM), window=False)


def test_h3_smoke_20_round_repetition_code_windowed_matches_whole() -> None:
    """H3 smoke: a 20-round measure/feed-forward loop; one window gives the whole verdict."""
    c = make_contract("ibm", IBM)
    prog = program([], round_body(), [], n=20)
    whole = check_program(prog, c, policy="eq", unroll_limit=64)
    windowed = check_program(prog, c, policy="eq", unroll_limit=2)
    assert whole.verdict == windowed.verdict in (PROVED, PROVED_UNDER)
    assert len(windowed.results) < len(whole.results)  # the window checks one round, not 20
