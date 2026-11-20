"""relax.py, rigid.py: N_geq(P) from a hand-built LTEG; T6 against Tier 1; T5 on rigid graphs."""

from __future__ import annotations

import pytest

from qtiming.core.labels import TOP, Lit
from qtiming.core.provenance import Prov, ProvClass
from qtiming.graph.lteg import LTEG
from qtiming.oblig.model import Diff, Obligation, Variation
from qtiming.solve.dispatcher import SolveCfg, verify
from qtiming.solve.synth.relax import Unbounded, relax
from qtiming.solve.synth.rigid import is_rigid, rigid_violation
from qtiming.solve.synth.sc import strongly_controllable

PROV = Prov(ProvClass.VENDOR, "test")


def _graph(hi: int | None) -> tuple[LTEG, int, int]:
    """origin -> a (5) -> b via a latency in [0, hi]."""
    g = LTEG("ibm", "x")
    o = g.add_node("origin", 0, "o")
    a = g.add_node("start", 1, "a")
    b = g.add_node("start", 2, "b")
    g.add_edge(o, a, 5, TOP, "o->a")
    g.add_edge(a, b, g.add_lat("k", "k@1", 0, hi, PROV), TOP, "a->b")
    return g, a, b


def _ob(g: LTEG, b: int, a: int, bound: int) -> Obligation:
    return Obligation("O3", 2, TOP, Diff(b, a, "<=", bound), frozenset({0}), frozenset(), False,
                      "safety", "deadline")


@pytest.mark.parametrize(("hi", "bound"), [(10, 5), (10, 10), (4, 5), (0, 0)])
def test_relaxed_sc_is_necessary_for_the_dispatch_being_safe(hi: int, bound: int) -> None:
    """T6: if verification proves the obligation, N_geq must be (strongly) controllable."""
    g, a, b = _graph(hi)
    ob = _ob(g, b, a, bound)
    proved = verify(g, ob, SolveCfg(use_tier2=False)).kind == "proved"
    sc = strongly_controllable(relax(g, [ob], {}).stnu).strongly_controllable
    assert sc or not proved


def test_a_deadline_the_latency_can_exceed_is_not_controllable() -> None:
    g, a, b = _graph(10)
    r = relax(g, [_ob(g, b, a, 5)], {})
    assert len(r.stnu.contingent) == 1
    assert not strongly_controllable(r.stnu).strongly_controllable


def test_unbounded_latency_is_reported_not_guessed() -> None:
    g, a, b = _graph(None)
    with pytest.raises(Unbounded):
        relax(g, [_ob(g, b, a, 5)], {})


def test_non_diff_obligations_are_skipped_with_a_note() -> None:
    g, a, b = _graph(10)
    ob = Obligation("O7", 2, TOP, Variation(b, a, 3), frozenset(), frozenset(), False,
                    "safety", "spread")
    assert "Variation" in relax(g, [ob], {}).notes[0]


def test_rigid_detection() -> None:
    g, _, _ = _graph(10)
    assert is_rigid(g)
    j = g.add_node("join", 3, "j")  # two unconditional in-edges: a max with two live arguments
    g.add_edge(1, j, 1, TOP, "x")
    g.add_edge(2, j, 1, TOP, "y")
    assert "two in-edges" in (rigid_violation(g) or "")


def test_exclusive_branch_labels_are_still_rigid() -> None:
    g, _, _ = _graph(10)
    j = g.add_node("join", 3, "j")
    g.add_edge(1, j, 1, frozenset({Lit("c", True)}), "x")
    g.add_edge(2, j, 1, frozenset({Lit("c", False)}), "y")
    assert is_rigid(g)


@pytest.mark.parametrize(("hi", "bound"), [(10, 5), (10, 10), (4, 5), (3, 2), (6, 6)])
def test_t5_on_a_rigid_graph_dc_agrees_with_verification(hi: int, bound: int) -> None:
    """Rigid dispatch: DC of the equality encoding iff the obligation holds for every latency."""
    from qtiming.solve.synth.stnu_dc import dynamically_controllable

    g, a, b = _graph(hi)
    assert is_rigid(g)
    ob = _ob(g, b, a, bound)
    proved = verify(g, ob, SolveCfg(use_tier2=False)).kind == "proved"
    dc = dynamically_controllable(relax(g, [ob], {}, strategy=False).stnu).dc
    assert dc == (hi <= bound) == proved
