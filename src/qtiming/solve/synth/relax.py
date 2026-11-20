"""LTEG -> relaxed STNU N_geq(P) for one outcome scenario omega (plan 12.2, theorem T6).

Every dispatch edge u -> v of weight w becomes the requirement `t_v - t_u >= w` (an executor may
wait longer than the hardware would). A latency edge becomes a contingent link from `u` to a FRESH
contingent end `c` plus `t_v - t_c >= 0`, so a node with several latency in-edges, or a latency end
that activates another link, stays well-formed. Snapping to a grid is dropped (it only restricts
dispatch, so dropping it keeps the relaxation a superset). Obligations of kind `Diff` become
requirements; `Variation`, `Mod` and `Events` are not expressible and are reported in `notes`.

`strategy=False` gives the rigid encoding of plan 12.9 instead: equalities, not lower bounds.

Conditional (labelled) networks are out of scope here: a scenario omega fixes every label, which
is what `qtiming repair` needs (it works on the counterexample's scenario).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from fractions import Fraction

from qtiming.graph.lteg import LTEG, LatVar, _env, holds
from qtiming.oblig.model import Diff, Obligation

from .model import STNU, Contingent
from .stn import Edge


class Unbounded(ValueError):
    """A latency on a relevant edge has no upper bound, so no contingent box exists."""


@dataclass(slots=True)
class Relaxed:
    stnu: STNU
    point: dict[int, int]  # LTEG node id -> STNU point
    notes: list[str] = field(default_factory=list)


def _exists(g: LTEG, env: Mapping[str, int]) -> set[int]:
    ex = {g.origin}
    for n in g.nodes:
        if n.id == g.origin or not holds(n.label, env):
            continue
        if any(g.edges[e].src in ex and holds(g.edges[e].label, env) for e in g.in_edges[n.id]):
            ex.add(n.id)
    return ex


def relax(g: LTEG, obligations: list[Obligation], omega: Mapping[str, int],
          *, strategy: bool = True) -> Relaxed:
    env = _env(g, omega)
    ex = _exists(g, env)
    point = {nid: i for i, nid in enumerate(sorted(ex))}
    n_pts = len(point)
    req: list[Edge] = []
    cont: list[Contingent] = []
    notes: list[str] = []

    def ge(pv: int, pu: int, w: Fraction | int, tag: str) -> None:  # t_v - t_u >= w (points)
        req.append((pv, pu, Fraction(-w), tag))  # convention E: lower bound = reversed edge
        if not strategy:  # equality: also t_v - t_u <= w
            req.append((pu, pv, Fraction(w), tag))

    for e in g.edges:
        if e.src not in ex or e.dst not in ex or not holds(e.label, env):
            continue
        if isinstance(e.w, LatVar):
            if e.w.hi is None:
                raise Unbounded(e.w.key)
            c = n_pts
            n_pts += 1
            cont.append(Contingent(point[e.src], c, Fraction(e.w.lo), Fraction(e.w.hi),
                                   f"{e.tag}:{e.w.occurrence}"))
            ge(point[e.dst], c, 0, e.tag)  # t_dst >= t_c
        else:
            ge(point[e.dst], point[e.src], e.w, e.tag)

    for o in obligations:
        if not holds(o.guard, env):
            continue
        c = o.check
        if not isinstance(c, Diff):
            notes.append(f"{o.code}@{o.nid}: {type(c).__name__} obligation is not a Diff; skipped")
            continue
        if c.x not in ex or c.y not in ex:
            continue
        tag = f"{o.code}@{o.nid}"
        if c.op == "<=":  # t_x - t_y <= c : edge y -> x with weight c
            req.append((point[c.y], point[c.x], Fraction(c.c), tag))
        else:  # t_x - t_y >= c : edge x -> y with weight -c
            req.append((point[c.x], point[c.y], Fraction(-c.c), tag))
    return Relaxed(STNU(n_pts, req, cont), point, notes)
