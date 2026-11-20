"""Rigid-graph detection (plan 12.9): tree-shaped dispatch, so the dispatch is the only strategy.

Rigid means: no snapping, and for every non-origin node the (label-conjoined) in-edges are
pairwise mutually exclusive, so at most one is active in any scenario and the `max` of the
dispatch rule has a single live argument. Then DC of the equality encoding equals "the
obligations hold for the dispatch under every latency" (theorem target T5).
"""

from __future__ import annotations

from itertools import combinations

from qtiming.core.labels import conj
from qtiming.graph.lteg import LTEG


def rigid_violation(g: LTEG) -> str | None:
    """None when `g` is rigid, else a plain-words reason."""
    for n in g.nodes:
        if n.snap is not None:
            return f"node {n.id} ({n.kind}) snaps to a grid"
        if n.id == g.origin:
            continue
        ins = [g.edges[i] for i in g.in_edges[n.id]]
        for a, b in combinations(ins, 2):
            both = conj(a.label, b.label)
            if both is not None:  # a scenario exists where both edges are active
                return f"node {n.id} ({n.kind}) has two in-edges that can be live together"
    return None


def is_rigid(g: LTEG) -> bool:
    return rigid_violation(g) is None
