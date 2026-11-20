"""Morris (2014) style O(N^3) dynamic controllability check for STNUs (convention E).

UNVERIFIED: rules transcribed from memory and validated only by agreement with
``bruteforce_dc``; see ``Docs/theory/dc-rules.md``. Do not use as a sole verdict source.

Labelled distance graph (edge ``X -> Y`` weight ``w`` means ``t_Y - t_X <= w``):
ordinary edges, lower-case edges ``A -> C (c:lo)`` and upper-case edges ``X -> A (C:v)``
(a wait: ``X >= A - v`` unless C has been observed). Rules are applied to a fixpoint;
the STNU is DC iff no negative ordinary cycle (or negative label self-loop) appears.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from qtiming.solve.synth.model import STNU
from qtiming.solve.synth.stn import bellman_ford

UNVERIFIED = True


@dataclass
class DCResult:
    dc: bool
    reason: str | None


def dynamically_controllable(stnu: STNU) -> DCResult:
    stnu.validate()
    n = stnu.n_points
    links = stnu.contingent
    ordinary: dict[tuple[int, int], tuple[Fraction, str]] = {}
    labels: dict[tuple[int, int, int], tuple[Fraction, str]] = {}
    failure: list[str] = []

    def add_ord(x: int, y: int, w: Fraction, tag: str) -> bool:
        if x == y:
            if w < 0:
                failure.append(tag)
            return False
        if (x, y) not in ordinary or w < ordinary[(x, y)][0]:
            ordinary[(x, y)] = (w, tag)
            return True
        return False

    def add_label(x: int, z: int, k: int, v: Fraction, tag: str) -> bool:
        if x == z and v < 0:  # an activation would have to wait for its own contingent end
            failure.append(tag)
            return False
        if (x, z, k) not in labels or v < labels[(x, z, k)][0]:
            labels[(x, z, k)] = (v, tag)
            return True
        return False

    for u, v, w, tag in stnu.requirements:
        add_ord(u, v, w, tag)
    for k, link in enumerate(links):
        add_label(link.c, link.a, k, -link.hi, f"{link.tag}:upper")
        # nature's guarantees hold in every run, so they are implied ordinary constraints
        add_ord(link.c, link.a, -link.lo, f"{link.tag}:lo")
        add_ord(link.a, link.c, link.hi, f"{link.tag}:hi")

    for _ in range(200):
        changed = False
        ords = list(ordinary.items())
        lbls = list(labels.items())
        for (x, y), (w1, t1) in ords:
            for (y2, z), (w2, t2) in ords:  # R1: ordinary + ordinary
                if y2 == y:
                    changed |= add_ord(x, z, w1 + w2, f"{t1}+{t2}")
            for (y2, z, k), (v, t2) in lbls:  # R2: ordinary + upper-case
                if y2 == y:
                    changed |= add_label(x, z, k, w1 + v, f"{t1}+{t2}")
        for k, link in enumerate(links):
            a, c, lo = link.a, link.c, link.lo
            for (c2, b), (v, t) in ords:  # R3: lower-case reduction
                if c2 == c and v < 0:
                    changed |= add_ord(a, b, lo + v, f"lc({link.tag})+{t}")
            for (c2, b, k2), (v, t) in lbls:  # R4: cross-case
                if c2 == c and v < 0 and k2 != k:
                    changed |= add_label(a, b, k2, lo + v, f"lc({link.tag})+{t}")
        for (x, z, k), (v, t) in lbls:  # R5: label removal
            if v >= -links[k].lo:
                changed |= add_ord(x, z, v, f"unlabel({t})")
        if failure:
            return DCResult(False, f"negative loop: {failure[0]}")
        _, cyc = bellman_ford(n, [(x, y, w, t) for (x, y), (w, t) in ordinary.items()])
        if cyc is not None:
            return DCResult(False, "negative cycle: " + " ; ".join(e[3] for e in cyc))
        if not changed:
            return DCResult(True, None)
    raise RuntimeError("DC propagation did not reach a fixpoint")  # pragma: no cover
