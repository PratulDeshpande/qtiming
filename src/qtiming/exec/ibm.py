"""IBM personality (restricted block model). Spec: docs/personality-spec/ibm.md."""

from __future__ import annotations

from collections import defaultdict
from fractions import Fraction

from qtiming.core.ast import Barrier, Box, Delay, Gate, If, Measure, Seq, Stmt
from qtiming.core.errors import QtError

from .engine import Engine, touched


def chain_durations(s: Stmt) -> dict[int, int]:
    """Static per-qubit duration of an arm made only of gates, delays and barriers."""
    clock: dict[int, int] = defaultdict(int)

    def go(x: Stmt) -> None:
        if isinstance(x, Seq):
            for y in x.stmts:
                go(y)
        elif isinstance(x, Box):
            go(x.body)
        elif isinstance(x, (Gate, Delay)):
            start = max(clock[q] for q in x.qubits)
            for q in x.qubits:
                clock[q] = start + x.dur
        elif isinstance(x, Barrier):
            j = max((clock[q] for q in x.qubits), default=0)
            for q in x.qubits:
                clock[q] = j
        else:
            raise QtError("E-EXEC-UNSUPPORTED", f"IBM arms may not contain {type(x).__name__}")

    go(s)
    return dict(clock)


class IbmExec(Engine):
    personality = "ibm"

    def start(self) -> None:
        self.clock: dict[int, Fraction] = defaultdict(Fraction)

    def _span(self, qubits: tuple[int, ...], dur: int, nid: int, op: str) -> Fraction:
        start = max(self.clock[q] for q in qubits)
        end = start + dur
        for q in qubits:
            self.clock[q] = end
        self.rec(nid, "start", start)
        for q in qubits:
            self.rec(nid, "end", end, f"q{q}", op)
        return end

    def gate(self, s: Gate) -> None:
        self._span(s.qubits, s.dur, s.nid, s.name)

    def delay(self, s: Delay) -> None:
        self._span(s.qubits, s.dur, s.nid, "delay")

    def barrier(self, s: Barrier) -> None:
        j = max((self.clock[q] for q in s.qubits), default=Fraction(0))
        for q in s.qubits:
            self.clock[q] = j
        self.rec(s.nid, "join", j)

    def measure(self, s: Measure) -> None:
        end = self._span((s.qubit,), self.contract.duration(
            "measure_2" if s.variant == "mid" else "measure"), s.nid, "measure")
        prop = self.record_outcome(s)
        self.valid[prop] = end + self.draw("measure", "branch", s.tier, s.nid)
        self.rec(s.nid, "valid", self.valid[prop])

    def if_(self, s: If) -> None:
        br = self.contract.branch
        for arm in (s.then_, s.else_):
            if arm is not None and not br.allow_nested and _has_if_or_measure(arm):
                raise QtError("E-EXEC-UNSUPPORTED", "IBM arms may not nest ifs or measure", s.loc)
        res = sorted(touched(s.then_) | (touched(s.else_) if s.else_ else set()))
        v = self.cond_valid(s.cond)
        mode = self.contract.param("ibm", "block_start", "all_resources")
        join = self.contract.param("ibm", "join_behavior", "pad_to_longest_block")
        if mode == "all_resources":
            b = max([v, *(self.clock[q] for q in res)])
            starts = {q: b for q in res}
        else:  # per_resource
            starts = {q: max(v, self.clock[q]) for q in res}
            b = min(starts.values()) if starts else v
        taken = bool(self.cond_value(s.cond))
        arm = s.then_ if taken else s.else_
        dmax = max(
            (max(chain_durations(a).values(), default=0) for a in (s.then_, s.else_) if a),
            default=0,
        )
        for q in res:
            self.clock[q] = starts[q]
        self.rec(s.nid, "bstart", b)
        if arm is not None:
            self.exec_stmt(arm)
        d_taken = max((self.clock[q] - starts[q] for q in res), default=Fraction(0))
        bend = b + (dmax if join == "pad_to_longest_block" else d_taken)
        for q in res:
            self.clock[q] = bend
        self.rec(s.nid, "bend", bend)


def _has_if_or_measure(s: Stmt) -> bool:
    if isinstance(s, (If, Measure)):
        return True
    if isinstance(s, Seq):
        return any(_has_if_or_measure(x) for x in s.stmts)
    if isinstance(s, Box):
        return _has_if_or_measure(s.body)
    return False
