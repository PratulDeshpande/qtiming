"""Strong controllability by the Vidal-Fargier rewrite (plan 12.4), not pseudo-controllability.

Every requirement touching a contingent end ``C`` (link ``A -> C``, ``theta`` in ``[lo, hi]``)
is rewritten onto the executable activation with the worst case over the box (convention E):

    X - C <= w   ->  X - A  <= w + lo            (C as early as possible)
    C - X <= w   ->  A - X  <= w - hi            (C as late as possible)
    C1 - C2 <= w ->  A1 - A2 <= w - hi1 + lo2    (different links)
    C - C <= w   ->  constant 0 <= w             (same end)

A requirement between ``C`` and its own activation falls out of the first two rows as a
constant self-loop (``C - A <= w`` needs ``hi <= w``; ``A - C <= w`` needs ``-lo <= w``).
The result is an STN over the executable points; consistent iff the STNU is SC.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from qtiming.solve.synth.model import STNU, Edge
from qtiming.solve.synth.stn import bellman_ford, solution


@dataclass
class SCResult:
    strongly_controllable: bool
    schedule: dict[int, Fraction] | None
    witness: list[str] | None


def strongly_controllable(stnu: STNU) -> SCResult:
    stnu.validate()
    by_end = {k.c: k for k in stnu.contingent}
    edges: list[Edge] = []
    for u, v, w, tag in stnu.requirements:
        ku, kv = by_end.get(u), by_end.get(v)
        if ku and kv:
            if u == v:
                if w < 0:
                    return SCResult(False, None, [f"{tag}@const"])
                continue
            edges.append((ku.a, kv.a, w - kv.hi + ku.lo, f"{tag}@C1=hi,C2=lo"))
        elif kv:  # C - X <= w
            edges.append((u, kv.a, w - kv.hi, f"{tag}@theta=hi"))
        elif ku:  # X - C <= w
            edges.append((ku.a, v, w + ku.lo, f"{tag}@theta=lo"))
        else:
            edges.append((u, v, w, tag))
    _, cyc = bellman_ford(stnu.n_points, edges)
    if cyc is not None:
        return SCResult(False, None, [e[3] for e in cyc])
    sol = solution(stnu.n_points, edges)
    assert sol is not None
    return SCResult(True, {i: sol[i] for i in range(stnu.n_points) if i not in by_end}, None)
