"""End to end check: elaborate, build the graph, generate obligations, verify, combine."""

from __future__ import annotations

from dataclasses import fields, is_dataclass, replace
from typing import Any

from qtiming.contract.model import Contract
from qtiming.core.ast import If, Policy, Stmt, While
from qtiming.core.errors import QtError
from qtiming.core.provenance import weakest
from qtiming.core.time import Interval
from qtiming.dispatch import build_graph
from qtiming.elab import elaborate
from qtiming.graph.invariants import check_invariants
from qtiming.oblig.generate import NOT_GENERATED, generate
from qtiming.solve.dispatcher import SolveCfg, verify

from .minimise import minimise
from .model import REFUTED, ObResult, Verdict, combine
from .replay import require_replay

_CHILDREN = ("stmts", "body", "then_", "else_", "default", "exhaust")


def with_policy(s: Any, pol: Policy) -> Any:
    """Copy of the program with every unannotated If/While given policy `pol` (CLI --policy)."""
    if isinstance(s, tuple):
        return tuple(with_policy(x, pol) for x in s)
    if not is_dataclass(s):
        return s
    ch = {f.name: with_policy(getattr(s, f.name), pol) for f in fields(s) if f.name in _CHILDREN}
    if isinstance(s, (If, While)) and s.policy is None:
        ch["policy"] = pol
    return replace(s, **ch)


def check_program(
    prog: Stmt, contract: Contract, *, policy: str | None = None, cfg: SolveCfg | None = None
) -> Verdict:
    if policy:
        prog = with_policy(prog, Policy(policy))  # type: ignore[arg-type]
    eff = policy or contract.branch.default_policy
    try:
        el = elaborate(prog, contract)
    except QtError as e:
        if e.code == "E-ELAB-POLICY-REJECTED":  # lint L2: a policy-incompatible request
            return Verdict(REFUTED, contract.name, contract.sha256, eff, (), None, (),
                           (f"policy-incompatible: {e.message}",), NOT_GENERATED)
        raise
    g = build_graph(el.body, contract)
    check_invariants(g)
    results = []
    for o in generate(g, el, contract):
        r = verify(g, o, cfg)
        if r.kind == "refuted":  # shrink, then require the independent executor to agree
            r = minimise(g, o, r)
            require_replay(g, o, r, el.body, contract)
        results.append(ObResult(o, r))
    verdict, reasons = combine(results, el.missing)
    ass = {a for r in results for a in r.obl.assumptions}
    wk = weakest(ass)
    notes = [f"contract assumed value: {a}" for a in contract.assumed]
    notes += [w for w in contract.warnings]
    return Verdict(
        verdict, contract.name, contract.sha256, eff,
        tuple(sorted(ass, key=lambda a: a.key)), None if wk is None else wk.name.lower(),
        tuple(results), tuple(reasons), NOT_GENERATED, tuple(notes),
    )


def with_latency_hi(contract: Contract, key: str, hi_dt: int) -> Contract:
    """The contract with latency `key` re-bounded to [lo, hi_dt]."""
    lats = []
    for cl in contract.latencies:
        if cl.latency.key == key:
            iv = Interval(cl.latency.iv.lo, hi_dt)
            cl = replace(cl, latency=replace(cl.latency, iv=iv))
        lats.append(cl)
    return replace(contract, latencies=tuple(lats))


def max_safe(prog: Stmt, contract: Contract, key: str, *, policy: str | None = None,
             cap_factor: int = 64) -> int | None:
    """Largest hi (dt) of latency `key` for which the program, RE-ELABORATED, still verifies
    (PROVED or PROVED-UNDER). Bisection assumes monotonicity (a looser bound only hurts); the
    result is re-checked at its endpoints. None if it already fails at the current bound."""
    cur = contract.latency(key).latency.iv
    if cur.hi is None:
        return None

    def ok(h: int) -> bool:
        v = check_program(prog, with_latency_hi(contract, key, h), policy=policy).verdict
        return v in ("PROVED", "PROVED-UNDER")

    if not ok(cur.hi):
        return None
    lo, hi = cur.hi, max(cur.hi, 1) * cap_factor
    if ok(hi):
        return hi  # not bounded within the search cap
    while hi - lo > 1:
        mid = (lo + hi) // 2
        lo, hi = (mid, hi) if ok(mid) else (lo, mid)
    return lo
