"""Tier 1: interval abstraction with affine-max forms (plan 11.3). Sound; never refutes.

A node's time is bounded by a MAX of affine terms in the latency variables. Subtracting two forms
cancels shared variables, which is what recovers correlations (the Appendix A proof).
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from qtiming.core.labels import Label, conj, implies
from qtiming.graph.lteg import LTEG, LatVar
from qtiming.oblig.generate import ancestors
from qtiming.oblig.model import Diff, Obligation, Variation

K = 32  # terms kept per form before collapsing to a constant


@dataclass(frozen=True, slots=True)
class Term:
    c: Fraction
    a: tuple[tuple[int, int], ...] = ()  # (latency variable id, integer coefficient)

    def plus(self, w: int | LatVar) -> Term:
        if isinstance(w, int):
            return Term(self.c + w, self.a)
        d = dict(self.a)
        d[w.id] = d.get(w.id, 0) + 1
        return Term(self.c, tuple(sorted((k, v) for k, v in d.items() if v)))

    def minus(self, o: Term) -> Term:
        d = dict(self.a)
        for k, v in o.a:
            d[k] = d.get(k, 0) - v
        return Term(self.c - o.c, tuple(sorted((k, v) for k, v in d.items() if v)))


Box = dict[int, tuple[int, int | None]]  # var id -> (lo, hi)


def ubound(t: Term, box: Box) -> Fraction | None:
    x = t.c
    for k, coef in t.a:
        lo, hi = box[k]
        if coef > 0:
            if hi is None:
                return None
            x += coef * hi
        else:
            x += coef * lo
    return x


def lbound(t: Term, box: Box) -> Fraction | None:
    x = t.c
    for k, coef in t.a:
        lo, hi = box[k]
        if coef > 0:
            x += coef * lo
        else:
            if hi is None:
                return None
            x += coef * hi
    return x


def _prune(terms: list[Term], box: Box, upper: bool) -> list[Term]:
    """Drop duplicates and dominated terms; collapse past K terms (sound, loses correlation)."""
    terms = list(dict.fromkeys(terms))
    keep = []
    for a in terms:
        dominated = False
        for b in terms:
            if b == a:
                continue
            lb = lbound(b.minus(a), box)  # b >= a for every theta
            if lb is not None and lb >= 0:
                dominated = True
                break
        if not dominated:
            keep.append(a)
    if len(keep) > K:
        bs = [ubound(t, box) if upper else lbound(t, box) for t in keep]
        finite = [b for b in bs if b is not None]
        if upper:
            if len(finite) != len(bs):
                return keep  # cannot collapse an unbounded form: keep it exact
            return [Term(max(finite))]
        return [Term(max(finite))] if finite else [Term(Fraction(0))]
    return keep


@dataclass(slots=True)
class T1Result:
    proved: bool
    margin: Fraction | None = None
    reason: str = ""


def forms(
    g: LTEG, cone: set[int], guard: Label, box: Box
) -> tuple[dict[int, list[Term]], dict[int, list[Term]]]:
    fmax: dict[int, list[Term]] = {g.origin: [Term(Fraction(0))]}
    fmin: dict[int, list[Term]] = {g.origin: [Term(Fraction(0))]}
    for n in g.nodes:
        if n.id == g.origin or n.id not in cone:
            continue
        if conj(n.label, guard) is None:
            continue  # cannot exist under the guard
        mx: list[Term] = []
        mn: list[Term] = []
        for ei in g.in_edges[n.id]:
            e = g.edges[ei]
            if e.src not in fmax or conj(e.label, guard) is None:
                continue
            mx += [t.plus(e.w) for t in fmax[e.src]]
            if implies(guard, e.label) and implies(guard, g.nodes[e.src].label) and e.src in fmin:
                mn += [t.plus(e.w) for t in fmin[e.src]]
        if not mx:
            continue
        mx = _prune(mx, box, True)
        mn = _prune(mn, box, False) if mn else [Term(Fraction(0))]  # times are non-negative
        if n.snap:  # ceil to grid is monotone: bound each side by constants
            ub = [ubound(t, box) for t in mx]
            if any(u is None for u in ub):
                continue
            grid = n.snap
            top = max(u for u in ub if u is not None)
            mx = [Term(Fraction(grid * -((-top) // grid)))]
            lbs = [x for x in (lbound(t, box) for t in mn) if x is not None]
            mn = [Term(Fraction(grid * -((-max(lbs)) // grid)))] if lbs else [Term(Fraction(0))]
        fmax[n.id], fmin[n.id] = mx, mn
    return fmax, fmin


def diff_upper(fx_max: list[Term], fy_min: list[Term], box: Box) -> Fraction | None:
    best: Fraction | None = None
    for b in fy_min:
        ubs = [ubound(a.minus(b), box) for a in fx_max]
        if any(u is None for u in ubs):
            continue
        cand = max(u for u in ubs if u is not None)
        best = cand if best is None or cand < best else best
    return best


def diff_lower(fx_min: list[Term], fy_max: list[Term], box: Box) -> Fraction | None:
    best: Fraction | None = None
    for a in fx_min:
        lbs = [lbound(a.minus(b), box) for b in fy_max]
        if any(x is None for x in lbs):
            continue
        cand = min(x for x in lbs if x is not None)
        best = cand if best is None or cand > best else best
    return best


def tier1(g: LTEG, o: Obligation) -> T1Result:
    c = o.check
    if not isinstance(c, (Diff, Variation)):
        return T1Result(False, reason="Tier 1 handles Diff and Variation only")
    box: Box = {v.id: (v.lo, v.hi) for v in g.lats}
    cone = ancestors(g, o.nodes())
    fmax, fmin = forms(g, cone, o.guard, box)
    if c.x not in fmax or c.y not in fmax:
        return T1Result(True, None, "vacuous: a node cannot exist under the guard")
    if isinstance(c, Diff):
        if c.op == "<=":
            up = diff_upper(fmax[c.x], fmin[c.y], box)
            if up is not None and up <= c.c:
                return T1Result(True, Fraction(c.c) - up)
            return T1Result(False, reason="upper bound too weak")
        lo = diff_lower(fmin[c.x], fmax[c.y], box)
        if lo is not None and lo >= c.c:
            return T1Result(True, lo - c.c)
        return T1Result(False, reason="lower bound too weak")
    up = diff_upper(fmax[c.x], fmin[c.y], box)
    lo = diff_lower(fmin[c.x], fmax[c.y], box)
    if up is not None and lo is not None and up - lo <= c.bound:
        return T1Result(True, Fraction(c.bound) - (up - lo))
    return T1Result(False, reason="spread bound too weak")
