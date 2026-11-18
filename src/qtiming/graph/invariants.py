"""Invariants checked after graph construction (plan 9.5), I1 to I6. I7 (cuts) lands with windowing.

A violation is a BUILDER bug, so these raise `QtError` with the plan's codes.
"""

from __future__ import annotations

import itertools
from fractions import Fraction

from qtiming.core.errors import QtError
from qtiming.core.labels import conj

from .lteg import LTEG, LatVar, dispatch_times


def bit_props(g: LTEG) -> list[str]:
    """Bit propositions the graph's labels (directly or via derived conditions) depend on."""
    derived_ops = {o for d in g.derived.values() for o in d.operands}
    labelled = {lit.prop for n in g.nodes for lit in n.label} | {
        lit.prop for e in g.edges for lit in e.label
    }
    return sorted(p for p in labelled | derived_ops if p not in g.derived)


def check_invariants(g: LTEG, *, max_props: int = 12) -> None:
    # I1: acyclic. Construction order is topological, so every edge must point forward.
    for e in g.edges:
        if e.src >= e.dst:
            raise QtError("E-GRAPH-CYCLE", f"edge {e.tag} goes backward: {e.src} -> {e.dst}")
    # I2: label well-formedness: an edge's labels may not contradict its endpoints'
    for e in g.edges:
        dst, src = g.nodes[e.dst].label, g.nodes[e.src].label
        if conj(e.label, dst) is None or conj(src, e.label) is None:
            raise QtError("E-GRAPH-LABEL", f"edge {e.tag} label contradicts an endpoint")
    # I5: each latency variable is used by exactly one edge
    uses: dict[int, int] = {}
    for e in g.edges:
        if isinstance(e.w, LatVar):
            uses[e.w.id] = uses.get(e.w.id, 0) + 1
    for v in g.lats:
        if uses.get(v.id, 0) != 1:
            n_uses = uses.get(v.id, 0)
            raise QtError("E-GRAPH-LATVAR", f"latency {v.occurrence} used {n_uses} times")
    # I6: integer constant weights; every label proposition is a bit with a valid node or derived
    valid_props = {n.obs for n in g.nodes if n.obs}
    for e in g.edges:
        if not isinstance(e.w, (int, LatVar)):
            raise QtError("E-GRAPH-PROP", f"edge {e.tag} has a non-integer weight")
    for p in bit_props(g):
        if p not in valid_props:
            raise QtError("E-GRAPH-PROP", f"label proposition {p!r} has no valid node")
    # I3: definedness: under every outcome, every node whose label holds is reached
    props = bit_props(g)
    theta = {v.occurrence: Fraction(v.lo) for v in g.lats}
    if len(props) > max_props:
        return  # too many to enumerate; the differential tests cover larger programs
    from .lteg import _env, holds

    for bits in itertools.product((0, 1), repeat=len(props)):
        omega = dict(zip(props, bits, strict=True))
        t = dispatch_times(g, omega, theta)
        env = _env(g, omega)
        for n in g.nodes:
            if holds(n.label, env) and n.id not in t:
                raise QtError("E-GRAPH-LABEL",
                              f"node {n.kind}/{n.tag}@{n.nid} has no active in-edge under {omega}")
