"""Shrink a counterexample before reporting (plan 13.4), checking with exact Tier 0 evaluation.

Greedy: set each latency to an endpoint (vertex lemma, T10) and each outcome bit to 0, keeping a
change only if the obligation is still violated. Variation witnesses are left as found.
"""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

from qtiming.graph.lteg import LTEG, _env, dispatch_times, holds
from qtiming.oblig.model import Diff, Mod, Obligation
from qtiming.solve.concrete import Result, _eval_check


def _still_fails(g: LTEG, o: Obligation, omega: dict[str, int],
                 theta: dict[str, Fraction]) -> bool:
    if not holds(o.guard, _env(g, omega)):
        return False
    ok, m, _ = _eval_check(o, dispatch_times(g, omega, theta))
    return m is not None and not ok


def minimise(g: LTEG, o: Obligation, r: Result) -> Result:
    if not isinstance(o.check, (Diff, Mod)) or r.kind != "refuted" or not r.theta:
        return r
    omega, theta = dict(r.omega), dict(r.theta)
    if not _still_fails(g, o, omega, theta):
        return r  # not exactly reproducible by Tier 0 evaluation: report as found
    for v in g.lats:
        for cand in (Fraction(v.lo), Fraction(v.hi) if v.hi is not None else None):
            if cand is None:
                continue
            old = theta[v.occurrence]
            theta[v.occurrence] = cand
            if _still_fails(g, o, omega, theta):
                break
            theta[v.occurrence] = old
    for p in sorted(omega):
        if omega[p]:
            omega[p] = 0
            if not _still_fails(g, o, omega, theta):
                omega[p] = 1
    return replace(r, omega=omega, theta=theta)
