"""Plan 16.2 property 5(e) / theorem T10: on snap-free graphs, Tier 2 finds a violation iff
exhaustive enumeration of outcomes times latency VERTICES finds one."""

from __future__ import annotations

import itertools
import os
import random
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("z3")
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
from qtiming.oblig.generate import generate  # noqa: E402
from qtiming.oblig.model import Diff, Variation  # noqa: E402
from qtiming.solve.smt import tier2  # noqa: E402

N = int(os.environ.get("QTIMING_VERTEX_N", "40"))


def brute_violates(g: Any, o: Any) -> bool:
    props = bit_props(g)
    if len(props) > 6 or len(g.lats) > 5:
        raise OverflowError
    verts = [[Fraction(v.lo), Fraction(v.hi)] for v in g.lats]
    c = o.check
    vals = []
    for bits in itertools.product((0, 1), repeat=len(props)):
        omega = dict(zip(props, bits, strict=True))
        if not holds(o.guard, _env(g, omega)):
            continue
        for vs in itertools.product(*verts):
            theta = {v.occurrence: x for v, x in zip(g.lats, vs, strict=True)}
            t = dispatch_times(g, omega, theta)
            if c.x not in t or c.y not in t:
                continue
            d = t[c.x] - t[c.y]
            if isinstance(c, Diff) and ((d > c.c) if c.op == "<=" else (d < c.c)):
                return True
            vals.append(d)
    return isinstance(c, Variation) and bool(vals) and max(vals) - min(vals) > c.bound


@pytest.mark.parametrize("pers,policy", [x for x in ACCEPTED if x[0] in ("ibm", "qua")])
def test_tier2_equals_vertex_enumeration(pers: str, policy: str | None) -> None:
    contract = make_contract(pers, CONTRACTS[pers])
    compared = 0
    for seed in range(N):
        prog, _ = build(gen(pers, random.Random(seed)))
        if policy:
            prog = with_policy(prog, Policy(policy))  # type: ignore[arg-type]
        try:
            el = elaborate(prog, contract)
            g = build_graph(el.body, contract)
        except QtError:
            continue
        for o in generate(g, el, contract):
            if not isinstance(o.check, (Diff, Variation)) or not o.deps:
                continue
            try:
                want = brute_violates(g, o)
            except OverflowError:
                continue
            r = tier2(g, o)
            assert r.kind in ("proved", "refuted"), r.reason
            assert (r.kind == "refuted") == want, (
                f"{pers}/{policy} seed {seed} {o.code}: tier2 {r.kind}, vertices say {want}")
            compared += 1
    assert compared > 0
