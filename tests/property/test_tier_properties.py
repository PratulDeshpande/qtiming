"""Plan 16.2 properties 8 (cone invariance) and 11 (Tier 1 containment), on random programs."""

from __future__ import annotations

import os
import random
import sys
from fractions import Fraction
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "personality"))
sys.path.insert(0, str(Path(__file__).parents[1] / "differential"))
from _support import build, make_contract  # noqa: E402
from test_graph_vs_executor import ACCEPTED, CONTRACTS, gen, with_policy  # noqa: E402

from qtiming.core.ast import Policy  # noqa: E402
from qtiming.core.errors import QtError  # noqa: E402
from qtiming.dispatch import build_graph  # noqa: E402
from qtiming.elab import elaborate  # noqa: E402
from qtiming.graph.invariants import bit_props  # noqa: E402
from qtiming.graph.lteg import _env, dispatch_times, holds  # noqa: E402
from qtiming.oblig.generate import ancestors, generate  # noqa: E402
from qtiming.oblig.model import Diff, Variation  # noqa: E402
from qtiming.solve.interval import diff_lower, diff_upper, forms  # noqa: E402

N = int(os.environ.get("QTIMING_PROP_N", "80"))


def programs(pers: str, policy: str | None):  # type: ignore[no-untyped-def]
    contract = make_contract(pers, CONTRACTS[pers])
    for seed in range(N):
        prog, _ = build(gen(pers, random.Random(seed)))
        if policy:
            prog = with_policy(prog, Policy(policy))  # type: ignore[arg-type]
        try:
            el = elaborate(prog, contract)
            g = build_graph(el.body, contract)
        except QtError:
            continue
        yield seed, g, generate(g, el, contract)


@pytest.mark.parametrize("pers,policy", ACCEPTED)
def test_cone_invariance_property_8(pers: str, policy: str | None) -> None:
    """Times of an obligation's nodes are the same on its cone as on the full graph."""
    checked = 0
    for seed, g, obs in programs(pers, policy):
        theta = {v.occurrence: Fraction(v.lo) for v in g.lats}
        rng = random.Random(seed)
        for o in obs:
            cone = ancestors(g, o.nodes())
            for _ in range(4):
                omega = {p: rng.getrandbits(1) for p in bit_props(g)}
                full = dispatch_times(g, omega, theta)
                part = dispatch_times(g, omega, theta, restrict=cone)
                for n in o.nodes():
                    assert full.get(n) == part.get(n), f"{pers}/{policy} seed {seed} node {n}"
                checked += 1
    assert checked > 0


@pytest.mark.parametrize("pers,policy", ACCEPTED)
def test_tier1_containment_property_11(pers: str, policy: str | None) -> None:
    """For random (omega, theta) the true t_x - t_y lies inside the Tier 1 bounds."""
    checked = 0
    for seed, g, obs in programs(pers, policy):
        box = {v.id: (v.lo, v.hi) for v in g.lats}
        rng = random.Random(seed + 99)
        for o in obs:
            if not isinstance(o.check, (Diff, Variation)):
                continue
            c = o.check
            cone = ancestors(g, o.nodes())
            fmax, fmin = forms(g, cone, o.guard, box)
            if c.x not in fmax or c.y not in fmax:
                continue
            up = diff_upper(fmax[c.x], fmin[c.y], box)
            lo = diff_lower(fmin[c.x], fmax[c.y], box)
            for _ in range(6):
                omega = {p: rng.getrandbits(1) for p in bit_props(g)}
                theta = {v.occurrence: Fraction(rng.randint(v.lo * 4, (v.hi or v.lo) * 4), 4)
                         for v in g.lats}
                t = dispatch_times(g, omega, theta)
                if not holds(o.guard, _env(g, omega)) or c.x not in t or c.y not in t:
                    continue
                d = t[c.x] - t[c.y]
                if up is not None:
                    assert d <= up, f"{pers}/{policy} seed {seed}: {d} > upper {up}"
                if lo is not None:
                    assert d >= lo, f"{pers}/{policy} seed {seed}: {d} < lower {lo}"
                checked += 1
    assert checked > 0
