"""QUA personality (resync, implicit aligns). Spec: docs/personality-spec/qua.md."""

from __future__ import annotations

from collections import defaultdict
from fractions import Fraction

from qtiming.core.ast import Barrier, Box, Delay, Gate, If, Measure, Seq, Stmt

from .engine import Engine, touched


def _single_op_element(s: Stmt | None) -> bool:
    """A lone Gate/Delay on one element: QUA compiles it to a conditional play with an
    equal-length wait on the false path, so the element's end time is outcome independent."""
    while isinstance(s, (Seq, Box)):
        inner = s.stmts if isinstance(s, Seq) else (s.body,)
        if len(inner) != 1:
            return False
        s = inner[0]
    return isinstance(s, (Gate, Delay)) and len(s.qubits) == 1


class QuaExec(Engine):
    personality = "qua"

    def start(self) -> None:
        self.clock: dict[int, Fraction] = defaultdict(Fraction)
        self.dynamic: set[int] = set()  # elements whose clock depends on outcomes/latencies
        self.tier = str(self.contract.param("qua", "align_tier", "same_fem"))
        self.skip_implicit = bool(self.contract.param("qua", "skip_implicit_align", False))

    def _span(self, qubits: tuple[int, ...], dur: int, nid: int, op: str) -> Fraction:
        start = max(self.clock[q] for q in qubits)
        end = start + dur
        for q in qubits:
            self.clock[q] = end
        self.rec(nid, "start", start)
        for q in qubits:
            self.rec(nid, "end", end, f"elem:q{q}", op)
        return end

    def gate(self, s: Gate) -> None:
        self._span(s.qubits, s.dur, s.nid, s.name)

    def delay(self, s: Delay) -> None:
        self._span(s.qubits, s.dur, s.nid, "delay")

    def _align(self, qs: tuple[int, ...] | list[int], nid: int, tag: str) -> Fraction:
        j = max((self.clock[q] for q in qs), default=Fraction(0))
        self.rec(nid, tag, j)
        if any(q in self.dynamic for q in qs):  # non-deterministic align: uncertain gap
            j = j + self.draw("align", "align", self.tier, nid)
            self.rec(nid, "align", j)
        for q in qs:
            self.clock[q] = j
            self.dynamic.discard(q)
        return j

    def barrier(self, s: Barrier) -> None:
        self._align(s.qubits, s.nid, "join")

    def measure(self, s: Measure) -> None:
        end = self._span((s.qubit,), self.contract.duration(
            "measure_2" if s.variant == "mid" else "measure"), s.nid, "measure")
        prop = self.record_outcome(s)
        self.valid[prop] = end + self.draw("measure", "branch", s.tier, s.nid)
        self.rec(s.nid, "valid", self.valid[prop])

    def if_(self, s: If) -> None:
        part = sorted(touched(s.then_) | (touched(s.else_) if s.else_ else set()))
        v = self.cond_valid(s.cond)
        if self.skip_implicit:
            for q in part:
                self.clock[q] = max(v, self.clock[q])
        else:
            base = max([v, *(self.clock[q] for q in part)])
            for q in part:
                self.clock[q] = base
            self._align(part, s.nid, "ialign")
        taken = self.cond_value(s.cond)
        arm = s.then_ if taken else s.else_
        if arm is not None:
            self.exec_stmt(arm)
        if not (s.else_ is None and _single_op_element(s.then_)):
            self.dynamic.update(part)
