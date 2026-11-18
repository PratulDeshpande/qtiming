"""The graph side (builder + dispatch evaluation) must reproduce the same hand-computed goldens."""

from __future__ import annotations

import pytest
from _support import cases, expected_times, load_case

from qtiming.dispatch import build_graph
from qtiming.graph.lteg import evaluate_graph

ALL = [(p, c) for p in ["ibm", "q1", "artiq", "qua"] for c in cases(p)]


@pytest.mark.parametrize("pers,path", ALL, ids=[f"{p}/{c.stem}" for p, c in ALL])
def test_graph_reproduces_golden(pers: str, path) -> None:  # type: ignore[no-untyped-def]
    c = load_case(path)
    g = build_graph(c.prog, c.contract)
    times = evaluate_graph(g, c.omega, {k: v for k, v in c.theta.items()})
    for key, want in expected_times(c).items():
        if key[1] == "emit":  # an emitted event depends on drop rules (O5), executor/solver only
            continue
        assert times.get(key) == want, f"{c.name}: {key} = {times.get(key)}, want {want}"
    for who_tag in c.expect.get("absent", []):
        who, _, tag = who_tag.partition(".")
        if c.expect.get("halted") or tag == "emit":  # halting/dropping is not a dispatch edge
            continue
        assert (c.ids[who], tag) not in times, f"{c.name}: {who_tag} should not exist"
