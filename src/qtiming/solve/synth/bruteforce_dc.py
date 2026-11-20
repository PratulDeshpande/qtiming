"""Independent integer game solver for tiny STNUs (oracle for ``stnu_dc``; <= 7 points).

Dynamic controllability game, integer ticks ``0..horizon``. Executables are the points that are
not contingent ends. At every tick ``t``:

1. Nature reveals which active contingent ends occur at ``t``. A link ``(a, c, lo, hi)`` is
   active once ``a`` has fired at ``ta``; ``c`` may occur at any ``t`` in ``[ta+lo, ta+hi]`` and
   MUST occur at ``ta+hi`` if it has not yet (so ``lo >= 1`` is required: the end cannot occur
   at the tick of its own activation).
2. The executor then observes them (standard semantics: it sees contingent ends of tick ``t``
   at the same instant) and chooses ANY subset of unfired executables to fire at ``t``
   (simultaneity allowed; order within a tick is irrelevant).

The executor wins iff every point fires and every requirement ``t_v - t_u <= w`` holds.
Executables may only fire at ``t <= horizon``; the game runs until ``horizon + max(hi)`` so
nature can still finish its links. Integer strategies are assumed sufficient for integer
networks (standard result for STNUs, here validated only by agreement with ``stnu_dc``).

``sc_bruteforce``: one schedule of the executables in ``[0, horizon]`` that works at all
theta corners (constraints are linear in theta, so corners suffice).
``wc_bruteforce``: for every integer theta combination the induced STN is consistent (this uses
``stn.consistent``, so it is not independent of the STN code).
"""

from __future__ import annotations

import itertools
from functools import cache

from qtiming.solve.synth.model import STNU
from qtiming.solve.synth.stn import consistent

_MASK = -1  # a fired point whose constraints are all resolved (keeps the memo key small)


def _ints(stnu: STNU) -> list[tuple[int, int, int]]:
    stnu.validate()
    vals = [w for _, _, w, _ in stnu.requirements]
    vals += [x for k in stnu.contingent for x in (k.lo, k.hi)]
    if any(v != int(v) for v in vals) or any(k.lo < 1 for k in stnu.contingent):
        raise ValueError("bruteforce needs integer bounds and lo >= 1")
    return [(u, v, int(w)) for u, v, w, _ in stnu.requirements]


def dc(stnu: STNU, horizon: int) -> bool:
    reqs = _ints(stnu)
    n = stnu.n_points
    links = [(k.a, k.c, int(k.lo), int(k.hi)) for k in stnu.contingent]
    ends = {c for _, c, _, _ in links}
    execs = [i for i in range(n) if i not in ends]
    limit = horizon + max((hi for *_, hi in links), default=0)
    touch = [[(u, v) for u, v, _ in reqs if p in (u, v)] for p in range(n)]
    link_of_act = {a: c for a, c, _, _ in links}
    act_of_end = {c: (a, lo) for a, c, lo, _ in links}

    def real(x: int | None) -> bool:
        return x is not None and x != _MASK

    def violated(times: tuple[int | None, ...]) -> bool:
        return any(real(times[u]) and real(times[v]) and times[v] - times[u] > w  # type: ignore[operator]
                   for u, v, w in reqs)

    def doomed(t: int, times: tuple[int | None, ...]) -> bool:
        """Cheap bound check: a constraint no later firing (at > t) can satisfy."""
        for u, v, w in reqs:
            tu, tv = times[u], times[v]
            if real(tu) and tv is None:
                lb = t + 1
                if v in act_of_end:
                    a, lo = act_of_end[v]
                    if real(times[a]):
                        lb = max(lb, times[a] + lo)  # type: ignore[operator]
                if lb > tu + w:  # type: ignore[operator]
                    return True
            if real(tv) and tu is None and u not in ends and horizon < tv - w:  # type: ignore[operator]
                return True
        return False

    def mask(times: list[int | None]) -> tuple[int | None, ...]:
        for p in range(n):
            if not real(times[p]):
                continue
            if p in link_of_act and times[link_of_act[p]] is None:
                continue
            if all(times[u if v == p else v] is not None for u, v in touch[p]):
                times[p] = _MASK
        return tuple(times)

    def exec_can_win(t: int, base: list[int | None]) -> bool:
        free = [e for e in execs if base[e] is None] if t <= horizon else []
        for r in range(len(free) + 1):
            for fire in itertools.combinations(free, r):
                nxt = list(base)
                for e in fire:
                    nxt[e] = t
                tup = tuple(nxt)
                if violated(tup) or doomed(t, tup):
                    continue
                if win(t + 1, mask(nxt)):
                    return True
        return False

    @cache
    def win(t: int, times: tuple[int | None, ...]) -> bool:
        if all(x is not None for x in times):
            return True
        if t > limit:
            return False
        active = [(c, times[a], lo, hi) for a, c, lo, hi in links
                  if times[a] is not None and times[c] is None]
        forced = [c for c, ta, _, hi in active if t == ta + hi]  # type: ignore[operator]
        optional = [c for c, ta, lo, hi in active
                    if ta + lo <= t < ta + hi]  # type: ignore[operator]
        for r in range(len(optional) + 1):
            for extra in itertools.combinations(optional, r):
                base = list(times)
                for c in forced + list(extra):
                    base[c] = t
                if violated(tuple(base)) or not exec_can_win(t, base):
                    return False
        return True

    return win(0, (None,) * n)


def sc_bruteforce(stnu: STNU, horizon: int) -> bool:
    reqs = _ints(stnu)
    ends = {k.c for k in stnu.contingent}
    execs = [i for i in range(stnu.n_points) if i not in ends]
    corners = list(itertools.product(*[(int(k.lo), int(k.hi)) for k in stnu.contingent]))
    for sched in itertools.product(range(horizon + 1), repeat=len(execs)):
        times = dict(zip(execs, sched, strict=True))
        ok = True
        for corner in corners:
            full = dict(times)
            for k, th in zip(stnu.contingent, corner, strict=True):
                full[k.c] = times[k.a] + th
            if any(full[v] - full[u] > w for u, v, w in reqs):
                ok = False
                break
        if ok:
            return True
    return False


def wc_bruteforce(stnu: STNU) -> bool:
    _ints(stnu)
    ranges = [range(int(k.lo), int(k.hi) + 1) for k in stnu.contingent]
    for thetas in itertools.product(*ranges):
        edges = list(stnu.requirements)
        for k, th in zip(stnu.contingent, thetas, strict=True):
            edges.append((k.a, k.c, th, k.tag))
            edges.append((k.c, k.a, -th, k.tag))
        if not consistent(stnu.n_points, edges):
            return False
    return True
