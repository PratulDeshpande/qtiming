"""Counterexample-guided repair of a REFUTED program (plan 12.8).

Scope of this build: O1 (commit-lead / RT-core underflow) is repaired by inserting a declared
`delay` of the exact shortfall (rounded UP to dt) in front of the violating operation. Every
candidate is RE-VERIFIED by the normal pipeline before it is offered, so a suggested patch is
checked, never trusted. O3 (deadline) is refused with advice: a delay only makes it worse. Other
obligation kinds report "no automatic patch" with the reason, never a guess.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, fields, is_dataclass, replace
from typing import Any

from qtiming.contract.model import Contract
from qtiming.core.ast import Delay, Gate, Seq, Stmt
from qtiming.solve.dispatcher import SolveCfg
from qtiming.verdict.model import REFUTED, Verdict
from qtiming.verdict.run import check_program

_CHILDREN = ("stmts", "body", "then_", "else_", "default", "exhaust")


@dataclass(frozen=True, slots=True)
class Hunk:
    nid: int  # node the delay is inserted in front of
    dur: int  # dt
    code: str  # obligation repaired
    why: str


@dataclass(frozen=True, slots=True)
class RepairResult:
    status: str  # ok | fixed | unsupported | gave-up | unknown
    before: Verdict
    after: Verdict
    program: Stmt
    hunks: tuple[Hunk, ...]
    message: str

    @property
    def idle_dt(self) -> int:
        return sum(h.dur for h in self.hunks)


def _kids(s: Any) -> list[Any]:
    out: list[Any] = []
    for name in _CHILDREN:
        v = getattr(s, name, None)
        out += list(v) if isinstance(v, tuple) else [v]
    out += [c for _, c in getattr(s, "cases", ())]
    return [c for c in out if c is not None and is_dataclass(c)]


def _max_nid(s: Any) -> int:
    return max([getattr(s, "nid", -1), *(_max_nid(c) for c in _kids(s))])


def _find(s: Any, nid: int) -> Any | None:
    if getattr(s, "nid", None) == nid and not isinstance(s, Seq):
        return s
    for c in _kids(s):
        hit = _find(c, nid)
        if hit is not None:
            return hit
    return None


def _wrap(s: Any, nid: int, delay: Delay) -> Any:
    """Copy of `s` with `Seq(delay, node nid)` in place of node `nid`."""
    if not is_dataclass(s):
        return s
    if getattr(s, "nid", None) == nid and not isinstance(s, Seq):
        return Seq(nid=delay.nid + 1, loc=s.loc, stmts=(delay, s))
    ch: dict[str, Any] = {}
    for f in fields(s):
        v = getattr(s, f.name)
        if f.name in _CHILDREN:
            ch[f.name] = (tuple(_wrap(x, nid, delay) for x in v) if isinstance(v, tuple)
                          else _wrap(v, nid, delay))
        elif f.name == "cases":
            ch[f.name] = tuple((k, _wrap(c, nid, delay)) for k, c in v)
    return replace(s, **ch) if ch else s


def _first_refuted(v: Verdict) -> Any | None:
    return next((r for r in v.results
                 if r.res.kind == "refuted" and r.obl.severity == "safety"), None)


def _build(prog: Stmt, extra: dict[int, int]) -> tuple[Stmt, dict[int, Delay]]:
    """`prog` with one declared delay of `extra[nid]` dt in front of each listed node."""
    cur: Any = prog
    nid = _max_nid(prog) + 1
    made: dict[int, Delay] = {}
    for at, dur in extra.items():
        node = _find(cur, at)
        d = Delay(nid=nid, loc=node.loc, qubits=node.qubits, dur=dur, declared=True)
        cur, nid = _wrap(cur, at, d), nid + 2
        made[at] = d
    return cur, made


def repair(prog: Stmt, contract: Contract, *, policy: str | None = None,
           cfg: SolveCfg | None = None, max_iter: int = 20) -> RepairResult:
    """The inserted delay is itself an instruction (it costs issue time on ARTIQ), so a node's
    delay is GROWN while its shortfall strictly shrinks, and abandoned when it stops shrinking."""
    before = check_program(prog, contract, policy=policy, cfg=cfg)
    cur, v = prog, before
    extra: dict[int, int] = {}
    last: dict[int, Any] = {}  # nid -> shortfall seen at the previous step
    codes: dict[int, str] = {}

    def hunks() -> tuple[Hunk, ...]:
        return tuple(Hunk(n, d, codes[n], f"delay of {d} dt before node {n}")
                     for n, d in extra.items())

    def stop(status: str, msg: str) -> RepairResult:
        return RepairResult(status, before, v, cur, hunks(), msg)

    for _ in range(max_iter):
        if v.verdict != REFUTED:
            if v.verdict == "UNKNOWN":
                return stop("unknown", "the program is UNKNOWN: " + "; ".join(v.reasons))
            return stop("fixed" if extra else "ok",
                        "patched program re-verified" if extra else "nothing to repair")
        bad = _first_refuted(v)
        if bad is None:  # REFUTED without an obligation: a policy-incompatible request
            return stop("unsupported", "refuted by a policy rejection: choose a compatible policy")
        o, res = bad.obl, bad.res
        if o.code == "O3":
            return stop("unsupported",
                        "O3 (deadline): a delay makes it worse; change the policy or the program")
        if o.code != "O1" or not res.shortfall or res.shortfall <= 0:
            return stop("unsupported", f"no automatic patch for {o.code} ({o.message})")
        if not isinstance(_find(cur, o.nid), Gate):
            return stop("unsupported", f"{o.code} at node {o.nid}: cannot place a delay before it")
        if o.nid in last and res.shortfall >= last[o.nid]:
            return stop("gave-up", f"{o.code} at node {o.nid}: a longer delay does not close it")
        last[o.nid] = res.shortfall
        codes[o.nid] = o.code
        extra[o.nid] = extra.get(o.nid, 0) + math.ceil(res.shortfall)
        cur, _made = _build(prog, extra)
        v = check_program(cur, contract, policy=policy, cfg=cfg)
    return stop("gave-up", f"no fix within {max_iter} steps")
