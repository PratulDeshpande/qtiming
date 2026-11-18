"""Graph invariants hold on every golden program; deliberately broken graphs are caught."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "personality"))
from _support import cases, load_case  # noqa: E402

from qtiming.core.errors import QtError  # noqa: E402
from qtiming.core.labels import TOP  # noqa: E402
from qtiming.core.provenance import Prov, ProvClass  # noqa: E402
from qtiming.dispatch import build_graph  # noqa: E402
from qtiming.graph.invariants import check_invariants  # noqa: E402
from qtiming.graph.lteg import LTEG  # noqa: E402

ALL = [(p, c) for p in ["ibm", "q1", "artiq", "qua"] for c in cases(p)]


@pytest.mark.parametrize("pers,path", ALL, ids=[f"{p}/{c.stem}" for p, c in ALL])
def test_invariants_hold_on_goldens(pers: str, path) -> None:  # type: ignore[no-untyped-def]
    c = load_case(path)
    check_invariants(build_graph(c.prog, c.contract))


def test_backward_edge_is_a_cycle_error() -> None:
    g = LTEG("ibm", "x")
    o = g.add_node("origin", -1, "origin")
    a = g.add_node("start", 0, "start")
    g.add_edge(a, o, 1, TOP, "bad")
    with pytest.raises(QtError, match="E-GRAPH-CYCLE"):
        check_invariants(g)


def test_latency_variable_used_twice_is_rejected() -> None:
    g = LTEG("ibm", "x")
    o = g.add_node("origin", -1, "origin")
    a = g.add_node("end", 0, "end")
    b = g.add_node("end", 1, "end")
    lv = g.add_lat("k", "k@m0", 0, 5, Prov(ProvClass.VENDOR, "t"))
    g.add_edge(o, a, lv, TOP, "x")
    g.add_edge(o, b, lv, TOP, "x")
    with pytest.raises(QtError, match="E-GRAPH-LATVAR"):
        check_invariants(g)
