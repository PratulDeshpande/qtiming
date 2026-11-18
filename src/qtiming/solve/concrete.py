"""Tier 0: exact concrete evaluation (plan 11.2). Applies when the cone has no latency variable.

It enumerates outcome scenarios and evaluates the ONE dispatch the hardware would perform in each.
Not a controllability notion (finding F4). Also the engine that replays solver witnesses.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Literal

from qtiming.graph.lteg import LTEG, _env, dispatch_times, holds
from qtiming.oblig.generate import ancestors
from qtiming.oblig.model import Diff, Events, Mod, Obligation, Variation


@dataclass(slots=True)
class Result:
    kind: Literal["proved", "refuted", "unknown"]
    tier: int | None = None
    margin: Fraction | None = None  # in dt: how far from failing the tightest case is
    reason: str = ""
    omega: dict[str, int] = field(default_factory=dict)
    theta: dict[str, Fraction] = field(default_factory=dict)
    shortfall: Fraction | None = None
    second: dict[str, int] | None = None  # Variation: the second execution's outcomes
    second_theta: dict[str, Fraction] | None = None
    event_time: Fraction | None = None


def sed_simulate(
    events: list[tuple[int, str, int, int]], lanes: int = 8, coarse_mu: int = 8
) -> list[tuple[int, str]]:
    """events: (submit_now_mu, channel, T_mu, busy_mu) in SUBMISSION order -> [(index, kind)] of
    dropped events. Plan 10.5; parameters the documentation does not fix are not modelled."""
    top: list[int | None] = [None] * lanes
    cur = 0
    drops: list[tuple[int, str]] = []
    by_slot: dict[tuple[str, int], int] = {}
    busy_until: dict[str, int] = {}
    for k, (now, ch, t, busy) in enumerate(events):
        coarse, fine = divmod(t, coarse_mu)
        now_c = now // coarse_mu
        placed = False
        for step in range(lanes):
            lane = (cur + step) % lanes
            tp = top[lane]
            if tp is None or tp <= now_c or coarse > tp:
                top[lane] = coarse
                cur = lane
                placed = True
                break
        if not placed:
            drops.append((k, "sequence"))
            continue
        if (ch, coarse) in by_slot and by_slot[(ch, coarse)] != fine:
            drops.append((k, "collision"))
            continue
        if t < busy_until.get(ch, -1):
            drops.append((k, "busy"))
            continue
        by_slot[(ch, coarse)] = fine
        busy_until[ch] = t + busy
    return drops


def relevant_props(g: LTEG, o: Obligation, cone: set[int]) -> list[str]:
    props = {lit.prop for n in cone for lit in g.nodes[n].label}
    props |= {lit.prop for lit in o.guard}
    for n in cone:
        for ei in g.in_edges[n]:
            props |= {lit.prop for lit in g.edges[ei].label}
    out: set[str] = set()
    for p in props:
        d = g.derived.get(p)
        out |= set(d.operands) if d else {p}
    return sorted(out)


def _eval_check(
    o: Obligation, t: dict[int, Fraction]
) -> tuple[bool, Fraction | None, Fraction | None]:
    """(ok, margin, event_time) for a single-scenario check; None margin = vacuous."""
    c = o.check
    if isinstance(c, Diff):
        if c.x not in t or c.y not in t:
            return True, None, None
        v = t[c.x] - t[c.y]
        m = (c.c - v) if c.op == "<=" else (v - c.c)
        return m >= 0, m, t[c.x]
    if isinstance(c, Mod):
        if c.x not in t:
            return True, None, None
        r = (t[c.x] - c.residue) % c.g
        return r == 0, Fraction(0) if r == 0 else -r, t[c.x]
    raise TypeError(type(c))


def _events_ok(o: Obligation, t: dict[int, Fraction]) -> tuple[bool, str]:
    c = o.check
    assert isinstance(c, Events)
    p = dict(c.params)
    evs = [(int(t[iss]), ch, int(t[cm]), 0) for cm, ch, iss in c.items if cm in t and iss in t]
    drops = sed_simulate(evs, p.get("lanes", 8), p.get("coarse", 8))
    return (not drops), ", ".join(f"event {k} dropped ({kind})" for k, kind in drops)


def tier0(g: LTEG, o: Obligation, cap: int = 4096) -> Result:
    cone = ancestors(g, o.nodes())
    props = relevant_props(g, o, cone)
    if 2 ** len(props) > cap:
        return Result("unknown", reason="too many outcome scenarios for Tier 0")
    margin: Fraction | None = None
    per_scenario: list[tuple[dict[str, int], Fraction]] = []
    for bits in itertools.product((0, 1), repeat=len(props)):
        omega = dict(zip(props, bits, strict=True))
        env = _env(g, omega)
        if not holds(o.guard, env):
            continue
        t = dispatch_times(g, omega, {}, restrict=cone)
        c = o.check
        if isinstance(c, Events):
            ok, why = _events_ok(o, t)
            if not ok:
                return Result("refuted", 0, reason=why, omega=omega)
            continue
        if isinstance(c, Variation):
            if c.x in t and c.y in t:
                per_scenario.append((omega, t[c.x] - t[c.y]))
            continue
        ok, m, when = _eval_check(o, t)
        if m is not None:
            margin = m if margin is None else min(margin, m)
        if not ok:
            assert m is not None
            return Result("refuted", 0, margin=m, reason=o.message, omega=omega,
                          shortfall=-m, event_time=when)
    if per_scenario:
        lo = min(per_scenario, key=lambda s: s[1])
        hi = max(per_scenario, key=lambda s: s[1])
        assert isinstance(o.check, Variation)
        margin = Fraction(o.check.bound) - (hi[1] - lo[1])
        if margin < 0:
            return Result("refuted", 0, margin=margin, reason=o.message, omega=hi[0],
                          shortfall=-margin, second=lo[0])
    return Result("proved", 0, margin=margin)
