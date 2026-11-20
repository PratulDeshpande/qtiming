"""Elaboration (plan 8): make each branch's timing policy explicit program structure.

EQ inserts a barrier, a wait of `hi` and arm padding; SYNC adds a join where the personality has
none; EXP keeps the programmer's delays; loops are unrolled with fresh proposition names.
Elaboration is not verification: it inserts statements, it never decides safety. The output is
itself valid TQ and elaborating it again changes nothing (idempotence, plan 8.9): an elaborated
`If` carries `origin_nid` and is left alone.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from qtiming.contract.compat import compat
from qtiming.contract.model import Contract
from qtiming.core.ast import (
    Assign,
    Barrier,
    Box,
    Call,
    Delay,
    For,
    Gate,
    If,
    Measure,
    Policy,
    Reset,
    Seq,
    Stmt,
    Switch,
    While,
    Within,
)
from qtiming.core.errors import QtError
from qtiming.core.ids import bit_prop
from qtiming.core.labels import Derived, EBin, EBit, EUn, Expr
from qtiming.frontend.payload import parse_within, to_dt


@dataclass(frozen=True, slots=True)
class ElabProgram:
    body: Stmt
    derived: tuple[Derived, ...]
    first_ops: dict[int, dict[int, tuple[int, ...]]]  # within nid -> qubit -> first-op nids
    within: dict[int, tuple[int, str]]  # within nid -> (deadline dt, anchor proposition)
    hard: frozenset[int]  # within nids whose box carries timing.hard
    missing: frozenset[str]  # contract keys needed but unbounded (dependants are UNKNOWN)
    policy_map: dict[int, Policy]  # effective policy per branch nid
    contract_sha256: str


def _children(s: Stmt) -> list[Stmt]:
    out: list[Stmt] = []
    for f in ("stmts", "body", "then_", "else_", "default", "exhaust"):
        v = getattr(s, f, None)
        if isinstance(v, tuple):
            out += [x for x in v if isinstance(x, Stmt.__args__)]  # type: ignore[attr-defined]
        elif v is not None and isinstance(v, Stmt.__args__):  # type: ignore[attr-defined]
            out.append(v)
    return out


def _max_nid(s: Stmt) -> int:
    return max([s.nid, *(_max_nid(c) for c in _children(s))])


def _props(e: Expr) -> list[str]:
    if isinstance(e, EBit):
        return [e.prop]
    if isinstance(e, EUn):
        return _props(e.a)
    if isinstance(e, EBin):
        return _props(e.a) + _props(e.b)
    return []


def _subst(e: Expr, m: dict[str, str]) -> Expr:
    if isinstance(e, EBit):
        return EBit(m.get(e.prop, e.prop))
    if isinstance(e, EUn):
        return EUn(e.op, _subst(e.a, m))
    if isinstance(e, EBin):
        return EBin(e.op, _subst(e.a, m), _subst(e.b, m))
    return e


def qubits_of(s: Stmt | None) -> set[int]:
    if s is None:
        return set()
    if isinstance(s, (Gate, Delay, Barrier)):
        return set(s.qubits)
    if isinstance(s, (Measure, Reset)):
        return {s.qubit}
    return set().union(*(qubits_of(c) for c in _children(s))) if _children(s) else set()


class Elaborator:
    def __init__(self, contract: Contract, unroll_limit: int = 64) -> None:
        self.c = contract
        self.limit = unroll_limit
        self.next = 0
        self.meas: dict[str, Measure] = {}
        self.missing: set[str] = set()
        self.policy_map: dict[int, Policy] = {}
        self.first_ops: dict[int, dict[int, tuple[int, ...]]] = {}
        self.within: dict[int, tuple[int, str]] = {}
        self.hard: set[int] = set()
        self.last_write: dict[tuple[str, int], str] = {}

    def fresh(self) -> int:
        self.next += 1
        return self.next

    # -- cloning with fresh ids (loop unrolling) ----------------------------------------
    def clone(self, s: Stmt, m: dict[str, str]) -> Stmt:
        kw: dict[str, Any] = {"nid": self.fresh(), "origin_nid": s.origin_nid or s.nid}
        if isinstance(s, Measure):
            m[bit_prop(s.cbit.reg, s.cbit.idx, s.nid)] = bit_prop(s.cbit.reg, s.cbit.idx,
                                                                   kw["nid"])
            return replace(s, **kw)
        if isinstance(s, Seq):
            return replace(s, stmts=tuple(self.clone(x, m) for x in s.stmts), **kw)
        if isinstance(s, (Box, Within, For)):
            return replace(s, body=self.clone(s.body, m), **kw)
        if isinstance(s, If):
            kw["origin_nid"] = None  # set only on ELABORATED Ifs: elab_if skips those
            return replace(s, cond=_subst(s.cond, m), then_=self.clone(s.then_, m),
                           else_=self.clone(s.else_, m) if s.else_ else None, **kw)
        if isinstance(s, While):
            return replace(s, cond=_subst(s.cond, m), body=self.clone(s.body, m),
                           exhaust=self.clone(s.exhaust, m), **kw)
        return replace(s, **kw)

    # -- static durations of elaborated statements --------------------------------------
    def dur(self, s: Stmt | None) -> dict[int, int]:
        clock: dict[int, int] = {}

        def go(x: Stmt) -> None:
            if isinstance(x, Seq):
                for y in x.stmts:
                    go(y)
            elif isinstance(x, (Box, Within)):
                go(x.body)
            elif isinstance(x, (Gate, Delay)):
                st = max(clock.get(q, 0) for q in x.qubits)
                for q in x.qubits:
                    clock[q] = st + x.dur
            elif isinstance(x, Measure):
                d = self.c.duration("measure_2" if x.variant == "mid" else "measure")
                clock[x.qubit] = clock.get(x.qubit, 0) + d
            elif isinstance(x, Barrier):
                j = max((clock.get(q, 0) for q in x.qubits), default=0)
                for q in x.qubits:
                    clock[q] = j
            elif isinstance(x, If) and x.origin_nid is not None:
                a, b = self.dur(x.then_), self.dur(x.else_)  # elaborated EQ block: equal arms
                if a != b:
                    raise QtError("E-ELAB-EQ-VARIABLE-ARM", "nested block has unequal arms", x.loc)
                st = max((clock.get(q, 0) for q in a), default=0)
                for q, d in a.items():
                    clock[q] = st + d
            else:
                raise QtError("E-ELAB-EQ-VARIABLE-ARM",
                              f"EQ cannot equalise an arm containing {type(x).__name__}", x.loc)

        if s is not None:
            go(s)
        return clock

    # -- main ---------------------------------------------------------------------------
    def elab(self, s: Stmt, m: dict[str, str]) -> Stmt:
        if isinstance(s, Measure):
            prop = bit_prop(s.cbit.reg, s.cbit.idx, s.nid)
            self.meas[prop] = s
            self.last_write[(s.cbit.reg, s.cbit.idx)] = prop
            return s
        if isinstance(s, (Gate, Delay, Barrier, Reset)):
            return s
        if isinstance(s, Seq):
            return replace(s, stmts=tuple(self.elab(x, m) for x in s.stmts))
        if isinstance(s, Box):
            body = self.elab(s.body, m)
            anns = dict(s.annotations)
            if "within" in anns:  # the front end validated it; here it becomes a deadline
                dur, anchor = parse_within(anns["within"])
                w = Within(nid=s.nid, loc=s.loc, deadline=to_dt(dur, self.c.dt_ns, "deadline"),
                           anchor=anchor, body=body)
                self.record_within(w, body)
                if "hard" in anns:
                    self.hard.add(w.nid)
            return replace(s, body=body)
        if isinstance(s, Within):
            body = self.elab(s.body, m)
            self.record_within(s, body)
            return body
        if isinstance(s, For):
            if s.n > self.limit:
                raise QtError("E-ELAB-LOOP-LIMIT",
                              f"for loop of {s.n} > unroll limit {self.limit}", s.loc,
                              hint="loop summarisation (windowing) is not implemented yet")
            out = tuple(self.elab(self.clone(s.body, m), m) for _ in range(s.n))
            return Seq(nid=self.fresh(), loc=s.loc, stmts=out, origin_nid=s.nid)
        if isinstance(s, While):
            return self.elab_while(s, m)
        if isinstance(s, If):
            return self.elab_if(s, m)
        if isinstance(s, (Assign, Switch, Call)):
            raise QtError("E-ELAB-UNSUPPORTED", f"{type(s).__name__} is not elaborated yet", s.loc)
        raise QtError("E-ELAB-UNSUPPORTED", type(s).__name__)  # pragma: no cover

    def record_within(self, s: Within, body: Stmt) -> None:
        anchor = self.last_write.get((s.anchor.reg, s.anchor.idx))
        if anchor is None:
            raise QtError("E-ELAB-WITHIN-ANCHOR",
                          f"within anchor {s.anchor.reg}[{s.anchor.idx}] is never written", s.loc)
        self.within[s.nid] = (s.deadline, anchor)
        firsts: dict[int, list[int]] = {}
        self._firsts(body, firsts, set(), False)
        self.first_ops[s.nid] = {q: tuple(v) for q, v in firsts.items()}

    def _firsts(self, s: Stmt, out: dict[int, list[int]], seen: set[int], in_arm: bool) -> None:
        """First USER operation per qubit; both arms of a branch are alternatives. Synthesised
        prefix delays and barriers are skipped; padding inside an arm counts (plan A.3)."""
        if isinstance(s, Seq):
            for x in s.stmts:
                self._firsts(x, out, seen, in_arm)
        elif isinstance(s, (Gate, Delay, Measure)):
            if isinstance(s, Delay) and s.origin_nid is not None and not in_arm:
                return
            for q in (s.qubits if not isinstance(s, Measure) else (s.qubit,)):
                if q not in seen:
                    out.setdefault(q, []).append(s.nid)
                    seen.add(q)
        elif isinstance(s, If):
            merged = set(seen)
            for arm in (s.then_, s.else_):
                if arm is not None:
                    sa = set(seen)
                    self._firsts(arm, out, sa, True)
                    merged |= sa
            seen |= merged

    def elab_while(self, s: While, m: dict[str, str]) -> Stmt:
        """Capped while as nested ifs: iteration j exists only if iterations < j all looped."""
        if s.cap > self.limit:
            raise QtError("E-ELAB-LOOP-LIMIT", f"while cap {s.cap} > unroll limit {self.limit}",
                          s.loc)
        cur = dict(m)
        # The condition names the bit's measurement BEFORE the loop. A body that re-measures the
        # bit writes a new proposition each iteration, which `clone` only remaps under the body
        # measurement's own id; so iteration j+1 must read the bit's latest write, or every
        # unrolled iteration tests the stale pre-loop outcome (contradictory nested arms).
        locs = {p: (self.meas[p].cbit.reg, self.meas[p].cbit.idx)
                for p in _props(s.cond) if p in self.meas}

        def rec(j: int) -> Stmt:
            latest = {p: self.last_write[loc] for p, loc in locs.items()
                      if j > 0 and loc in self.last_write}
            cond = _subst(s.cond, {**cur, **latest})
            if j == s.cap:
                then: Stmt = self.elab(self.clone(s.exhaust, cur), cur)
            else:
                body = self.elab(self.clone(s.body, cur), cur)
                then = Seq(nid=self.fresh(), loc=s.loc, stmts=(body, rec(j + 1)), origin_nid=s.nid)
            return self.elab_if(
                If(nid=self.fresh(), loc=s.loc, cond=cond, then_=then, else_=None,
                   policy=s.policy), cur)

        return rec(0)

    def elab_if(self, s: If, m: dict[str, str]) -> Stmt:
        if s.origin_nid is not None:  # already elaborated: idempotence
            return s
        then_ = self.elab(s.then_, m)
        else_ = self.elab(s.else_, m) if s.else_ else None
        pol = s.policy or Policy(self.c.branch.default_policy)  # type: ignore[arg-type]
        cp = compat(pol.kind, self.c.branch.klass)
        if not cp.accepted:
            raise QtError("E-ELAB-POLICY-REJECTED",
                          f"policy {pol.kind!r} is not accepted on {self.c.branch.klass} "
                          f"backends: {cp.note}", s.loc)
        self.policy_map[s.nid] = pol
        node = replace(s, then_=then_, else_=else_, policy=pol, origin_nid=s.nid)
        res = sorted(qubits_of(then_) | qubits_of(else_))
        if pol.kind == "eq" and self.c.personality != "artiq":
            return self.eq(node, res)
        if pol.kind == "sync" and self.c.personality == "qua":  # QUA joins only via align
            return Seq(nid=self.fresh(), loc=s.loc, origin_nid=s.nid, stmts=(
                node, Barrier(nid=self.fresh(), loc=s.loc, qubits=tuple(res), origin_nid=s.nid)))
        return node  # ibm: the block model joins; artiq/exp: the programmer's delays decide

    def eq(self, node: If, res: list[int]) -> Stmt:
        loc, org = node.loc, node.nid
        w, meas_res = 0, set()
        for p in dict.fromkeys(_props(node.cond)):
            mm = self.meas.get(p)
            if mm is None:
                raise QtError("E-ELAB-UNBOUND", f"condition reads {p!r} before a measurement", loc)
            cl = self.c.find_latency("measure", "branch", mm.tier)
            meas_res.add(mm.qubit)
            if cl.latency.iv.hi is None:  # unbounded: wait lo, dependants become UNKNOWN
                self.missing.add(cl.latency.key)
            w = max(w, cl.latency.iv.lo if cl.latency.iv.hi is None else cl.latency.iv.hi)
        if self.c.personality == "q1":
            self.q1_equalisable(node)
            then_, else_ = node.then_, node.else_
        else:
            da, db = self.dur(node.then_), self.dur(node.else_)
            d = {r: max(da.get(r, 0), db.get(r, 0)) for r in res}

            def pad(arm: Stmt | None, got: dict[int, int]) -> Stmt:
                extra = tuple(
                    Delay(nid=self.fresh(), loc=loc, qubits=(r,), dur=d[r] - got.get(r, 0),
                          declared=True, origin_nid=org)
                    for r in res if d[r] > got.get(r, 0))
                return Seq(nid=self.fresh(), loc=loc, origin_nid=org,
                           stmts=((arm,) if arm is not None else ()) + extra)

            then_, else_ = pad(node.then_, da), pad(node.else_, db)
        prefix: list[Stmt] = [Barrier(nid=self.fresh(), loc=loc,
                                      qubits=tuple(sorted(set(res) | meas_res)), origin_nid=org)]
        if w:
            prefix += [Delay(nid=self.fresh(), loc=loc, qubits=(r,), dur=w, declared=True,
                             origin_nid=org) for r in res]
        return Seq(nid=self.fresh(), loc=loc, origin_nid=org,
                   stmts=(*prefix, replace(node, then_=then_, else_=else_)))

    def q1_equalisable(self, node: If) -> None:
        """Q1 per-instruction timeline (plan 8.5): the two outcome totals must agree."""
        def instrs(s: Stmt | None) -> list[int]:
            if s is None:
                return []
            if isinstance(s, (Gate, Delay)):
                return [s.dur]
            if isinstance(s, Barrier):
                return []
            if isinstance(s, (Seq, Box)):
                return [d for c in _children(s) for d in instrs(c)]
            raise QtError("E-ELAB-Q1-NOT-EQUALISABLE",
                          f"Q1 arms may only hold RT instructions, found {type(s).__name__}",
                          s.loc)

        e = int(self.c.param("q1", "else_time_dt", 1))  # type: ignore[call-overload]
        a, b = instrs(node.then_), instrs(node.else_)
        t_true, t_false = sum(a) + len(b) * e, len(a) * e + sum(b)
        if t_true != t_false:
            raise QtError(
                "E-ELAB-Q1-NOT-EQUALISABLE",
                f"arm totals differ: {t_true} dt when true, {t_false} dt when false", node.loc,
                hint="match RT instruction counts and durations, or use policy sync/exp",
            )


def elaborate(prog: Stmt, contract: Contract, *, unroll_limit: int = 64) -> ElabProgram:
    el = Elaborator(contract, unroll_limit)
    el.next = _max_nid(prog)
    body = el.elab(prog, {})
    return ElabProgram(body, (), el.first_ops, el.within, frozenset(el.hard),
                       frozenset(el.missing), el.policy_map, contract.sha256)
