"""Q1 dispatch rules (plan 9.4.2). Spec: Docs/personality-spec/q1.md.

Two chains: the Q1-core issue chain (unconditional) and the RT chain, whose edge weights are
guarded by the condition literal (executed: dur, skipped: else_time).
"""

from __future__ import annotations

from qtiming.core.ast import Barrier, Box, Delay, Gate, If, Measure, Seq, Stmt
from qtiming.core.errors import QtError
from qtiming.core.labels import TOP, Label
from qtiming.graph.builder import GraphBuilder


def rt_instrs(s: Stmt | None) -> list[Gate | Delay]:
    if s is None:
        return []
    if isinstance(s, Seq):
        return [i for x in s.stmts for i in rt_instrs(x)]
    if isinstance(s, Box):
        return rt_instrs(s.body)
    if isinstance(s, (Gate, Delay)):
        return [s]
    if isinstance(s, Barrier):
        return []
    raise QtError("E-GRAPH-UNSUPPORTED", f"Q1 conditional arms may not contain {type(s).__name__}")


class Q1Builder(GraphBuilder):
    personality = "q1"

    def __init__(self, contract):  # type: ignore[no-untyped-def]
        super().__init__(contract)
        self.nop = contract.cost("nop")
        self.depth = int(contract.cap("rt_queue_depth", 32))
        self.else_time = int(contract.param("q1", "else_time_dt", 1))
        self.last_issue = self.g.origin
        self.execs: list[int] = []
        self.prev: tuple[int, int, tuple[Label, Label] | None] | None = None  # node, dur, cond
        self.pending_join: list[tuple[int, int]] = []  # (if nid, first exec in block)

    def _issue(self, nid: int, tag: str, k_for_queue: int | None) -> int:
        n = self.g.add_node("issue", nid, tag)
        self.g.add_edge(self.last_issue, n, self.nop, TOP, "q1.issue-chain")
        if k_for_queue is not None and k_for_queue >= self.depth:
            self.g.add_edge(self.execs[k_for_queue - self.depth], n, 0, TOP, "q1.back-pressure")
        self.last_issue = n
        return n

    def _rt(self, nid: int, dur: int, cond: tuple[Label, Label] | None, cond_expr_valid: int | None
            ) -> int:
        k = len(self.execs)
        issue = self._issue(nid, "issue", k)
        ex = self.g.add_node("exec", nid, "exec", "rt")
        for if_nid, first in self.pending_join:  # first instruction after a conditional block
            self.g.fact("q1join", if_nid, first, ex)
        self.pending_join = []
        if k == 0:
            self.g.add_edge(issue, ex, 0, TOP, "q1.rt-start")
        else:
            assert self.prev is not None
            pn, pd, pc = self.prev
            if pc is None:
                self.g.add_edge(pn, ex, pd, TOP, "q1.rt-chain")
            else:
                self.g.add_edge(pn, ex, pd, pc[0], "q1.rt-chain")
                self.g.add_edge(pn, ex, self.else_time, pc[1], "q1.rt-skip")
        self.g.fact("rt", nid, issue, ex)
        if cond_expr_valid is not None:
            self.g.fact("cond_read", nid, ex, cond_expr_valid)
        self.execs.append(ex)
        self.prev = (ex, dur, cond)
        return ex

    def gate(self, s: Gate) -> None:
        self._rt(s.nid, s.dur, None, None)

    def delay(self, s: Delay) -> None:
        self._rt(s.nid, s.dur, None, None)

    def barrier(self, s: Barrier) -> None:
        return

    def measure(self, s: Measure) -> None:
        dur = self.contract.duration("measure")
        ex = self._rt(s.nid, dur, None, None)
        end = self.g.add_node("end", s.nid, "end", "rt")
        self.g.add_edge(ex, end, dur, TOP, "q1.acquire")
        self.add_valid(s, end, "measure", "branch")

    def if_(self, s: If) -> None:
        lit_t, lit_f = self.cond_labels(s.cond, s.nid)
        v = self.cond_valid(s.cond, s.nid)
        first_k = len(self.execs)
        for arm, lit, pol in ((s.then_, lit_t, "set_cond"), (s.else_, lit_f, "set_cond_else")):
            if arm is None:
                continue
            self._issue(s.nid, pol, None)  # set_cond runs on the Q1 core, takes no RT time
            for ins in rt_instrs(arm):
                self._rt(ins.nid, ins.dur, (lit, lit_f if lit == lit_t else lit_t), v)
        if len(self.execs) > first_k:
            self.pending_join.append((s.nid, self.execs[first_k]))
