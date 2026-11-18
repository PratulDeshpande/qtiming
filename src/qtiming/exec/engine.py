"""Reference executor core: the deterministic interpreter of an ELABORATED TQ program.

Independent second implementation of each personality's dispatch spec (plan principle 9): it
imports only `core` and the loaded Contract, never graph/solver/elab code. Time is `Fraction` dt.
Nothing quantum is simulated; outcomes come from the oracle.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

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
from qtiming.core.ids import lat_occurrence
from qtiming.core.labels import EBin, EBit, EUn, Expr, evaluate
from qtiming.core.time import Interval

from .oracle import Oracle


@dataclass(frozen=True, slots=True)
class Violation:
    # underflow, underflow-halt, stale-read, stall, deadline, gap, capacity, grid, sync-spread
    kind: str
    nid: int
    t: Fraction
    shortfall: Fraction | None
    detail: str


@dataclass(frozen=True, slots=True)
class SilentDrop:
    kind: str  # sequence, collision, busy
    nid: int
    t: Fraction
    channel: str


@dataclass(frozen=True, slots=True)
class TraceEvent:
    t: Fraction
    resource: str
    op: str
    nid: int


@dataclass(frozen=True, slots=True)
class ExecResult:
    trace: tuple[TraceEvent, ...]
    violations: tuple[Violation, ...]
    drops: tuple[SilentDrop, ...]
    times: dict[tuple[int, str], Fraction]  # (nid, tag) -> time, for replay comparison
    halted: bool


def props_of(e: Expr) -> list[str]:
    if isinstance(e, EBit):
        return [e.prop]
    if isinstance(e, EUn):
        return props_of(e.a)
    if isinstance(e, EBin):
        return props_of(e.a) + props_of(e.b)
    return []


def touched(s: Stmt) -> set[int]:
    """Qubits touched by a statement (static)."""
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


class Engine:
    """Shared machinery. Subclasses implement the personality's statement semantics."""

    personality = ""

    def __init__(self, prog: Stmt, contract: Contract, oracle: Oracle) -> None:
        if contract.personality != self.personality:
            raise QtError(
                "E-EXEC-PERSONALITY",
                f"contract {contract.name!r} is for {contract.personality!r}, "
                f"not {self.personality!r}",
            )
        self.prog, self.contract, self.oracle = prog, contract, oracle
        self.sigma: dict[str, int] = {}
        self.valid: dict[str, Fraction] = {}
        self.times: dict[tuple[int, str], Fraction] = {}
        self.trace: list[TraceEvent] = []
        self.violations: list[Violation] = []
        self.drops: list[SilentDrop] = []
        self.halted = False

    # -- services ---------------------------------------------------------------------
    def rec(self, nid: int, tag: str, t: Fraction | int, resource: str = "", op: str = "") -> None:
        self.times[(nid, tag)] = Fraction(t)
        if resource:
            self.trace.append(TraceEvent(Fraction(t), resource, op or tag, nid))

    def violate(
        self, kind: str, nid: int, t: Fraction, shortfall: Fraction | None, detail: str
    ) -> None:
        self.violations.append(Violation(kind, nid, Fraction(t), shortfall, detail))

    def halt(self) -> None:
        self.halted = True

    def draw(self, src: str, dst: str, tier: str, nid: int) -> Fraction:
        """Realise the contract latency src->dst for `tier`, occurrence keyed by node `nid`."""
        cl = self.contract.find_latency(src, dst, tier)
        iv = Interval(cl.latency.iv.lo, cl.latency.iv.hi)
        return Fraction(self.oracle.latency(lat_occurrence(cl.latency.key, nid), iv))

    def record_outcome(self, m: Measure) -> str:
        from qtiming.core.ids import bit_prop

        prop = bit_prop(m.cbit.reg, m.cbit.idx, m.nid)
        self.sigma[prop] = int(self.oracle.outcome(prop))
        return prop

    def cond_value(self, cond: Expr) -> bool:
        ps = props_of(cond)
        missing = [p for p in ps if p not in self.sigma]
        if missing:
            raise QtError("E-EXEC-UNBOUND", f"condition reads {missing[0]!r} before it is measured")
        return bool(evaluate(cond, {p: self.sigma[p] for p in ps}))

    def cond_valid(self, cond: Expr) -> Fraction:
        return max((self.valid[p] for p in props_of(cond)), default=Fraction(0))

    # -- driver -------------------------------------------------------------------------
    def run(self) -> ExecResult:
        self.start()
        self.exec_stmt(self.prog)
        self.finish()
        return ExecResult(
            tuple(self.trace), tuple(self.violations), tuple(self.drops), dict(self.times),
            self.halted,
        )

    def start(self) -> None:
        """Personality hook: initialise state."""

    def finish(self) -> None:
        """Personality hook: after the last statement."""

    def exec_stmt(self, s: Stmt) -> None:
        if self.halted:
            return
        if isinstance(s, Seq):
            for x in s.stmts:
                self.exec_stmt(x)
        elif isinstance(s, Box):
            self.exec_stmt(s.body)
        elif isinstance(s, Gate):
            self.gate(s)
        elif isinstance(s, Delay):
            self.delay(s)
        elif isinstance(s, Barrier):
            self.barrier(s)
        elif isinstance(s, Measure):
            self.measure(s)
        elif isinstance(s, Reset):
            self.reset(s)
        elif isinstance(s, If):
            self.if_(s)
        elif isinstance(s, (For, While, Switch, Assign, Call, Within)):
            raise QtError(
                "E-EXEC-UNSUPPORTED",
                f"{type(s).__name__} is not executable: elaborate (unroll/lower) the program first",
                s.loc,
            )
        else:  # pragma: no cover
            raise QtError("E-EXEC-UNSUPPORTED", f"unknown statement {type(s).__name__}")

    def gate(self, s: Gate) -> None:
        raise NotImplementedError

    def delay(self, s: Delay) -> None:
        raise NotImplementedError

    def barrier(self, s: Barrier) -> None:
        raise NotImplementedError

    def measure(self, s: Measure) -> None:
        raise NotImplementedError

    def reset(self, s: Reset) -> None:
        self.gate(
            Gate(nid=s.nid, loc=s.loc, name="reset", qubits=(s.qubit,),
                 dur=self.contract.duration("reset"))
        )

    def if_(self, s: If) -> None:
        raise NotImplementedError


def execute(prog: Stmt, contract: Contract, oracle: Oracle | None = None) -> ExecResult:
    """Run `prog` under the contract's personality. Default oracle: `Fixed()` (all-zero bits)."""
    from .artiq import ArtiqExec
    from .ibm import IbmExec
    from .oracle import Fixed
    from .q1 import Q1Exec
    from .qua import QuaExec

    cls: dict[str, type[Engine]] = {
        "ibm": IbmExec, "q1": Q1Exec, "artiq": ArtiqExec, "qua": QuaExec,
    }
    return cls[contract.personality](prog, contract, oracle or Fixed()).run()
