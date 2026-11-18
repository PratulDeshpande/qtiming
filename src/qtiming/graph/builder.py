"""Common LTEG construction (plan 9.3). Personalities subclass this in `qtiming.dispatch`.

State is a per-resource FRONTIER: the list of (node, label) alternatives that "the previous
operation on this resource" may be, because after a branch a resource's last event depends on the
outcome. The labels of one frontier are mutually exclusive and exhaustive, so every successor has
at least one active in-edge (invariant I3).
"""

from __future__ import annotations

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
    Reset,
    Seq,
    Stmt,
    Switch,
    While,
    Within,
)
from qtiming.core.errors import QtError
from qtiming.core.ids import bit_prop, cond_prop, lat_occurrence
from qtiming.core.labels import TOP, Derived, EBit, EUn, Expr, Label, Lit, Prop, conj
from qtiming.core.time import Interval

from .lteg import LTEG, LatVar

Front = dict[str, list[tuple[int, Label]]]


def props_of(e: Expr) -> list[Prop]:
    from qtiming.core.labels import EBin

    if isinstance(e, EBit):
        return [e.prop]
    if isinstance(e, EUn):
        return props_of(e.a)
    if isinstance(e, EBin):
        return props_of(e.a) + props_of(e.b)
    return []


def touched(s: Stmt) -> set[int]:
    if isinstance(s, (Gate, Delay, Barrier)):
        return set(s.qubits)
    if isinstance(s, (Measure, Reset)):
        return {s.qubit}
    if isinstance(s, Seq):
        return set().union(*(touched(x) for x in s.stmts)) if s.stmts else set()
    if isinstance(s, Box):
        return touched(s.body)
    if isinstance(s, If):
        return touched(s.then_) | (touched(s.else_) if s.else_ else set())
    return set()


class GraphBuilder:
    personality = ""

    def __init__(self, contract: Contract) -> None:
        if contract.personality != self.personality:
            raise QtError(
                "E-GRAPH-PERSONALITY",
                f"contract is for {contract.personality!r}, builder for {self.personality!r}",
            )
        self.contract = contract
        self.g = LTEG(self.personality, contract.sha256)
        self.g.origin = self.g.add_node("origin", -1, "origin")
        self.front: Front = {}
        self.ctx: Label = TOP
        self.valid_node: dict[Prop, int] = {}
        # (frontier node, resource) -> alternatives for the end of the last REAL op on r
        self.endof: dict[tuple[int, str], list[tuple[int, Label]]] = {}

    # -- frontier ---------------------------------------------------------------------
    def entries(self, r: str) -> list[tuple[int, Label]]:
        """Alternatives for "the previous op on r" that can occur in the current context."""
        alts = self.front.get(r, [(self.g.origin, TOP)])
        return [(n, lab) for n, lab in alts if conj(lab, self.ctx) is not None]

    def join_from(self, resources: list[str], dst: int, tag: str) -> None:
        for r in resources:
            for n, lab in self.entries(r):
                self.g.add_edge(n, dst, 0, lab, tag)

    def ends(self, r: str) -> list[tuple[int, Label]]:
        """End nodes of the last real op on r (joins and aligns are transparent), under ctx."""
        out: list[tuple[int, Label]] = []
        for n, lab in self.entries(r):
            for e, el in self.endof.get((n, r), [(n, TOP)]):
                c = conj(lab, el)
                if c is not None:
                    out.append((e, c))
        return out

    def set_front(self, resources: list[str], node: int, real: bool = True) -> None:
        """`real`: node ends an op. Otherwise it is a join: gap bookkeeping passes through."""
        for r in resources:
            prev = [(node, TOP)] if real else self.ends(r)
            self.front[r] = [(node, TOP)]
            self.endof[(node, r)] = prev

    def node(self, kind: str, nid: int, tag: str, resource: str | None = None,
             obs: Prop | None = None) -> int:
        return self.g.add_node(kind, nid, tag, resource, self.ctx, obs)

    def latvar(self, nid: int, src: str, dst: str, tier: str) -> LatVar:
        cl = self.contract.find_latency(src, dst, tier)
        iv = Interval(cl.latency.iv.lo, cl.latency.iv.hi)
        return self.g.add_lat(cl.latency.key, lat_occurrence(cl.latency.key, nid), iv.lo, iv.hi,
                              cl.latency.prov)

    # -- conditions -------------------------------------------------------------------
    def cond_labels(self, cond: Expr, nid: int) -> tuple[Label, Label]:
        """(label when the condition holds, label when it does not)."""
        if isinstance(cond, EBit):
            return frozenset({Lit(cond.prop, True)}), frozenset({Lit(cond.prop, False)})
        if isinstance(cond, EUn) and cond.op == "not" and isinstance(cond.a, EBit):
            p = cond.a.prop
            return frozenset({Lit(p, False)}), frozenset({Lit(p, True)})
        p = cond_prop(nid)
        self.g.derived[p] = Derived(p, cond, tuple(props_of(cond)))
        return frozenset({Lit(p, True)}), frozenset({Lit(p, False)})

    def cond_valid(self, cond: Expr, nid: int) -> int:
        """Node at which the condition's value is observable (the last operand's valid point)."""
        ops = [self.valid_node[p] for p in dict.fromkeys(props_of(cond))]
        if not ops:
            return self.g.origin
        if len(ops) == 1:
            return ops[0]
        v = self.node("valid", nid, "cvalid")
        for o in ops:
            self.g.add_edge(o, v, 0, TOP, "cond-operand")
        return v

    # -- branching --------------------------------------------------------------------
    def arm(self, s: Stmt | None, lit: Label) -> Front:
        """Build `s` under `ctx & lit`; returns the arm's frontier and restores the builder."""
        saved_front, saved_ctx = self.front, self.ctx
        merged = conj(saved_ctx, lit)
        assert merged is not None
        self.front = {r: list(v) for r, v in saved_front.items()}
        self.ctx = merged
        if s is not None:
            self.stmt(s)
        out = self.front
        self.front, self.ctx = saved_front, saved_ctx
        return out

    def merge_arms(self, before: Front, arms: list[tuple[Label, Front]]) -> None:
        keys = set(before) | {r for _, f in arms for r in f}
        for r in sorted(keys):
            if all(f.get(r) == before.get(r) for _, f in arms):
                continue  # no arm touched this resource
            alt: list[tuple[int, Label]] = []
            for lit, f in arms:
                for n, lab in f.get(r, before.get(r, [(self.g.origin, TOP)])):
                    c = conj(lab, lit)
                    if c is not None:
                        alt.append((n, c))
            self.front[r] = alt

    # -- statements -------------------------------------------------------------------
    def build(self, prog: Stmt) -> LTEG:
        self.stmt(prog)
        return self.g

    def stmt(self, s: Stmt) -> None:
        if isinstance(s, Seq):
            for x in s.stmts:
                self.stmt(x)
        elif isinstance(s, Box):
            self.stmt(s.body)
        elif isinstance(s, Gate):
            self.gate(s)
        elif isinstance(s, Delay):
            self.delay(s)
        elif isinstance(s, Barrier):
            self.barrier(s)
        elif isinstance(s, Measure):
            self.measure(s)
        elif isinstance(s, Reset):
            self.gate(Gate(nid=s.nid, loc=s.loc, name="reset", qubits=(s.qubit,),
                           dur=self.contract.duration("reset")))
        elif isinstance(s, If):
            self.if_(s)
        elif isinstance(s, (For, While, Switch, Assign, Call, Within)):
            raise QtError("E-GRAPH-UNELABORATED",
                          f"{type(s).__name__} must be elaborated before graph construction", s.loc)
        else:  # pragma: no cover
            raise QtError("E-GRAPH-UNSUPPORTED", type(s).__name__)

    # common rules (plan 9.3); personalities override what differs
    def span(self, nid: int, qubits: tuple[int, ...], dur: int, op: str,
             tags: tuple[str, str] = ("start", "end")) -> tuple[int, int]:
        res = [f"q{q}" for q in qubits]
        start = self.node("start", nid, tags[0])
        for r in res:
            for e, lab in self.ends(r):
                self.g.fact("gap", nid, r, e, start, lab)
        self.join_from(res, start, "common.ready")
        end = self.node("end", nid, tags[1], res[0])
        self.g.add_edge(start, end, dur, TOP, f"common.{op}")
        self.set_front(res, end)
        return start, end

    def gate(self, s: Gate) -> None:
        self.span(s.nid, s.qubits, s.dur, s.name)

    def delay(self, s: Delay) -> None:
        self.span(s.nid, s.qubits, s.dur, "delay")

    def barrier(self, s: Barrier) -> None:
        res = [f"q{q}" for q in s.qubits]
        j = self.node("join", s.nid, "join")
        self.join_from(res, j, "common.barrier")
        self.set_front(res, j, real=False)
        if s.origin_nid is not None:  # a synthesised EQ barrier: the reference for O7
            self.g.fact("eqbar", s.origin_nid, j)

    def measure_dur(self, s: Measure) -> int:
        return self.contract.duration("measure_2" if s.variant == "mid" else "measure")

    def measure(self, s: Measure) -> None:
        _, end = self.span(s.nid, (s.qubit,), self.measure_dur(s), "measure")
        self.add_valid(s, end, "measure", "branch")

    def add_valid(self, s: Measure, end: int, src: str, dst: str) -> int:
        prop = bit_prop(s.cbit.reg, s.cbit.idx, s.nid)
        v = self.node("valid", s.nid, "valid", obs=prop)
        self.g.add_edge(end, v, self.latvar(s.nid, src, dst, s.tier), TOP, "feedforward")
        self.valid_node[prop] = v
        return v

    def if_(self, s: If) -> None:
        raise NotImplementedError
