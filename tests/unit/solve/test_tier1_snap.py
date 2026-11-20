"""Tier 1 must never PROVE an obligation about a node whose time is unbounded (soundness).

Regression: a snapped node downstream of a latency with no upper bound was dropped from the
forms, and its absence was then read as "the node cannot exist under the guard": a vacuous PROVED.
"""

from __future__ import annotations

from qtiming.core.labels import TOP
from qtiming.core.provenance import Prov, ProvClass
from qtiming.graph.lteg import LTEG
from qtiming.oblig.model import Diff, Obligation
from qtiming.solve.interval import tier1


def _graph(hi: int | None) -> tuple[LTEG, int, int]:
    """origin -> a (0) ; a -> s (latency [0, hi]); s snaps to a grid of 8."""
    g = LTEG("ibm", "x")
    o = g.add_node("origin", 0, "o")
    a = g.add_node("start", 1, "a")
    s = g.add_node("start", 2, "s", snap=8)
    g.add_edge(o, a, 0, TOP, "o->a")
    g.add_edge(a, s, g.add_lat("k", "k@1", 0, hi, Prov(ProvClass.VENDOR, "t")), TOP, "a->s")
    return g, a, s


def _ob(s: int, a: int, bound: int) -> Obligation:
    return Obligation("O3", 2, TOP, Diff(s, a, "<=", bound), frozenset({0}), frozenset(), False,
                      "safety", "deadline")


def test_unbounded_latency_into_a_snapped_node_is_not_proved() -> None:
    g, a, s = _graph(None)
    assert not tier1(g, _ob(s, a, 0)).proved


def test_bounded_snapped_node_is_still_proved_when_it_holds() -> None:
    g, a, s = _graph(5)  # s in [0, 8] after snapping, so s - a <= 8
    assert tier1(g, _ob(s, a, 8)).proved
    assert not tier1(g, _ob(s, a, 7)).proved
