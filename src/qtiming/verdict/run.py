"""End to end check: elaborate, build the graph, generate obligations, verify, combine."""

from __future__ import annotations

from dataclasses import fields, is_dataclass, replace
from typing import Any

from qtiming.contract.model import Contract
from qtiming.core.ast import If, Policy, SourceLoc, Stmt, While
from qtiming.core.errors import QtError
from qtiming.core.provenance import weakest
from qtiming.core.time import Interval
from qtiming.dispatch import build_graph
from qtiming.elab import elaborate
from qtiming.exec.engine import ExecResult, execute
from qtiming.exec.oracle import Fixed
from qtiming.graph.invariants import check_invariants
from qtiming.graph.window import split_loops
from qtiming.oblig.generate import NOT_GENERATED, generate
from qtiming.solve.dispatcher import SolveCfg, verify

from .minimise import minimise
from .model import PROVED, PROVED_UNDER, REFUTED, UNKNOWN, ObResult, Verdict, combine
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


def collect_locs(s: Any, out: dict[int, SourceLoc]) -> dict[int, SourceLoc]:
    if hasattr(s, "nid") and hasattr(s, "loc"):
        out.setdefault(s.nid, s.loc)
    for name in _CHILDREN:
        v = getattr(s, name, None)
        for c in (v if isinstance(v, tuple) else (v,)):
            if c is not None and hasattr(c, "nid"):
                collect_locs(c, out)
    return out


_RANK = {REFUTED: 0, UNKNOWN: 1, PROVED_UNDER: 2, PROVED: 3}


def _merge(vs: list[Verdict], notes: tuple[str, ...]) -> Verdict:
    """Conjunction of window verdicts (plan 9.7): the minimum, assumptions and results unioned."""
    worst = min(vs, key=lambda v: _RANK[v.verdict])
    ass = {a for v in vs for a in v.assumptions}
    wk = weakest(ass)
    locs: dict[int, SourceLoc] = {}
    for v in vs:
        locs |= v.locs
    return replace(
        worst, assumptions=tuple(sorted(ass, key=lambda a: a.key)),
        weakest_class=None if wk is None else wk.name.lower(),
        results=tuple(r for v in vs for r in v.results),
        reasons=tuple(dict.fromkeys(r for v in vs for r in v.reasons)),
        notes=tuple(dict.fromkeys((*notes, *(n for v in vs for n in v.notes)))), locs=locs,
        traces=next((v.traces for v in vs if v.verdict == REFUTED), vs[0].traces))


def check_program(
    prog: Stmt, contract: Contract, *, policy: str | None = None, cfg: SolveCfg | None = None,
    first_failure: bool = False, window: bool = True, unroll_limit: int = 64,
) -> Verdict:
    """Check `prog`; loops over `unroll_limit` are windowed (plan 9.7) unless `window=False`."""
    if window:
        try:
            w = split_loops(prog, contract, unroll_limit)
        except QtError as e:
            if e.code != "E-GRAPH-CUT":
                raise
            return Verdict(UNKNOWN, contract.name, contract.sha256,
                           policy or contract.branch.default_policy, (), None, (),
                           (f"{e.code}: {e.message}",), NOT_GENERATED)
        if w.bodies:
            parts = [_check_whole(p, contract, policy, cfg, first_failure, unroll_limit)
                     for p in (w.rest, *w.bodies)]
            return _merge(parts, w.notes)
    return _check_whole(prog, contract, policy, cfg, first_failure, unroll_limit)


def _check_whole(prog: Stmt, contract: Contract, policy: str | None, cfg: SolveCfg | None,
                 first_failure: bool, unroll_limit: int) -> Verdict:
    if policy:
        prog = with_policy(prog, Policy(policy))  # type: ignore[arg-type]
    eff = policy or contract.branch.default_policy
    try:
        el = elaborate(prog, contract, unroll_limit=unroll_limit)
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
        if first_failure and r.kind == "refuted":
            break
    verdict, reasons = combine(results, el.missing)
    ass = {a for r in results for a in r.obl.assumptions}
    wk = weakest(ass)
    notes = [f"contract assumed value: {a}" for a in contract.assumed]
    notes += [w for w in contract.warnings]
    traces: list[tuple[str, ExecResult]] = []
    bad = next((r for r in results if r.res.kind == "refuted"), None)
    try:
        if bad is not None:
            traces.append(("counterexample", execute(el.body, contract,
                                                      Fixed(bad.res.omega, bad.res.theta))))
            if bad.res.second is not None:
                traces.append(("second execution", execute(
                    el.body, contract, Fixed(bad.res.second, bad.res.second_theta or {}))))
        else:
            traces.append(("typical run", execute(el.body, contract, Fixed())))
    except QtError as e:  # e.g. an unspecified ARTIQ commit_lead: no trace, the verdict stands
        notes.append(f"no executor trace: {e.message}")
    return Verdict(
        verdict, contract.name, contract.sha256, eff,
        tuple(sorted(ass, key=lambda a: a.key)), None if wk is None else wk.name.lower(),
        tuple(results), tuple(reasons), NOT_GENERATED, tuple(notes),
        locs=collect_locs(el.body, {}), traces=tuple(traces),
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
