"""Q1 personality (predicated, RT queue). Spec: docs/personality-spec/q1.md.

One sequencer: the classical Q1 core issues instructions in program order into a FIFO that the
real-time (RT) core drains on a rigid timeline.
"""

from __future__ import annotations

from fractions import Fraction

from qtiming.core.ast import Barrier, Box, Delay, Gate, If, Measure, Seq, Stmt
from qtiming.core.errors import QtError
from qtiming.core.labels import Expr

from .engine import Engine

Cond = tuple[Expr, bool]  # (condition, polarity under which the instruction executes)


def _rt_instrs(s: Stmt | None) -> list[Gate | Delay]:
    if s is None:
        return []
    if isinstance(s, Seq):
        return [i for x in s.stmts for i in _rt_instrs(x)]
    if isinstance(s, Box):
        return _rt_instrs(s.body)
    if isinstance(s, (Gate, Delay)):
        return [s]
    if isinstance(s, Barrier):
        return []
    raise QtError("E-EXEC-UNSUPPORTED", f"Q1 conditional arms may not contain {type(s).__name__}")


class Q1Exec(Engine):
    personality = "q1"

    def start(self) -> None:
        self.nop = Fraction(self.contract.cost("nop"))
        self.depth = int(self.contract.cap("rt_queue_depth", 32))  # type: ignore[call-overload]
        self.else_time = Fraction(
            self.contract.param("q1", "else_time_dt", 1)  # type: ignore[call-overload]
        )
        self.ic = Fraction(0)  # Q1-core issue clock
        self.starts: list[Fraction] = []  # RT start time of each instruction so far
        self.prev_end = Fraction(0)  # RT time at which the next instruction would start

    def _rt(self, nid: int, dur: int, op: str, cond: Cond | None) -> None:
        k = len(self.starts)
        ic = self.ic + self.nop
        if k >= self.depth:  # queue full: the Q1 core stalls until a slot frees up
            ic = max(ic, self.starts[k - self.depth])
        self.ic = ic
        ex = ic if k == 0 else self.prev_end
        self.rec(nid, "issue", ic)
        executed = True
        if cond is not None:
            executed = self.cond_value(cond[0]) == cond[1]
            v = self.cond_valid(cond[0])
            if ex < v:
                self.violate("stale-read", nid, ex, v - ex, "condition read before result valid")
        if ex < ic:
            self.violate("underflow-halt", nid, ex, ic - ex, "RT queue empty when needed")
            self.halt()
            return
        self.rec(nid, "exec", ex, "rt", op)
        self.starts.append(ex)
        self.prev_end = ex + (dur if executed else self.else_time)

    def gate(self, s: Gate) -> None:
        self._rt(s.nid, s.dur, s.name, None)

    def delay(self, s: Delay) -> None:
        self._rt(s.nid, s.dur, "wait", None)

    def barrier(self, s: Barrier) -> None:  # single sequencer: nothing to join
        return

    def measure(self, s: Measure) -> None:
        self._rt(s.nid, self.contract.duration("measure"), "acquire", None)
        if self.halted:
            return
        end = self.times[(s.nid, "exec")] + self.contract.duration("measure")
        prop = self.record_outcome(s)
        self.valid[prop] = end + self.draw("measure", "branch", s.tier, s.nid)
        self.rec(s.nid, "valid", self.valid[prop])

    def if_(self, s: If) -> None:
        for arm, pol in ((s.then_, True), (s.else_, False)):
            if arm is None:
                continue
            self.ic += self.nop  # the set_cond instruction itself runs on the Q1 core
            self.rec(s.nid, "set_cond" if pol else "set_cond_else", self.ic)
            for ins in _rt_instrs(arm):
                self._rt(ins.nid, ins.dur, ins.name if isinstance(ins, Gate) else "wait",
                         (s.cond, pol))
