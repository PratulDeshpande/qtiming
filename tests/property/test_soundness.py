"""Property 1 (soundness, Tier 0/1 only): an obligation the checker PROVED is never violated.

Two independent witnesses: (a) graph evaluation under random (omega, theta), and (b) the reference
executor, which shares no code with the graph side. Tier 1 never reports REFUTED, and every
REFUTED comes from exact Tier 0 evaluation.
"""

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
from qtiming.exec.engine import execute  # noqa: E402
from qtiming.exec.oracle import Random  # noqa: E402
from qtiming.graph.invariants import bit_props  # noqa: E402
from qtiming.graph.lteg import _env, dispatch_times, holds  # noqa: E402
from qtiming.oblig.generate import generate  # noqa: E402
from qtiming.oblig.model import Diff, Variation  # noqa: E402
from qtiming.solve.dispatcher import verify  # noqa: E402

N = int(os.environ.get("QTIMING_PROP_N", "150"))
RUNS = 12


@pytest.mark.parametrize("pers,policy", ACCEPTED)
def test_proved_obligations_are_never_violated(pers: str, policy: str | None) -> None:
    contract = make_contract(pers, CONTRACTS[pers])
    proved_total = 0
    for seed in range(N):
        prog, _ = build(gen(pers, random.Random(seed)))
        if policy:
            prog = with_policy(prog, Policy(policy))  # type: ignore[arg-type]
        try:
            el = elaborate(prog, contract)
            g = build_graph(el.body, contract)
        except QtError:
            continue
        results = [(o, verify(g, o)) for o in generate(g, el, contract)]
        for _, r in results:
            if r.kind == "refuted":
                assert r.tier == 0  # Tier 1 never refutes; Tier 2 does not exist yet
        proved = [o for o, r in results if r.kind == "proved"]
        proved_total += len(proved)
        variation_vals: dict[int, list[Fraction]] = {id(o): [] for o in proved}
        rng = random.Random(seed * 7919 + 1)
        for _ in range(RUNS):
            omega = {p: rng.getrandbits(1) for p in bit_props(g)}
            theta = {v.occurrence: Fraction(rng.randint(v.lo * 4, (v.hi or v.lo) * 4), 4)
                     for v in g.lats}
            t = dispatch_times(g, omega, theta)
            env = _env(g, omega)
            for o in proved:
                if not holds(o.guard, env) or not isinstance(o.check, (Diff, Variation)):
                    continue
                c = o.check
                if c.x not in t or c.y not in t:
                    continue
                d = t[c.x] - t[c.y]
                if isinstance(c, Diff):
                    assert (d <= c.c) if c.op == "<=" else (d >= c.c), (
                        f"{pers}/{policy} seed {seed}: proved {o.code} violated: {d} {c.op} {c.c}")
                else:
                    variation_vals[id(o)].append(d)
        for o in proved:
            vals = variation_vals[id(o)]
            if vals and isinstance(o.check, Variation):
                assert max(vals) - min(vals) <= o.check.bound, (
                    f"{pers}/{policy} seed {seed}: proved {o.code} spread {max(vals) - min(vals)}")
        # the independent executor: a proved O1/O2a at a node means no violation at that node
        proved_at = {(o.code, o.nid) for o in proved}
        for k in range(RUNS):
            res = execute(el.body, contract, Random(seed * 31 + k))
            for v in res.violations:
                code = {"underflow": "O1", "underflow-halt": "O1", "stale-read": "O2a"}.get(v.kind)
                assert (code, v.nid) not in proved_at, (
                    f"{pers}/{policy} seed {seed}: executor violated proved {code} at {v.nid}")
    assert proved_total > 0, "no obligation was proved: the property was vacuous"
