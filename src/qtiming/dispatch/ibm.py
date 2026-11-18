"""IBM dispatch rules (plan 9.4.1). Spec: Docs/personality-spec/ibm.md."""

from __future__ import annotations

from collections import defaultdict

from qtiming.core.ast import Barrier, Box, Delay, Gate, If, Measure, Seq, Stmt
from qtiming.core.errors import QtError
from qtiming.core.labels import TOP, conj
from qtiming.graph.builder import GraphBuilder, touched


def arm_duration(s: Stmt | None) -> int:
    """Static duration of an arm: its longest per-qubit chain (gates, delays, barriers only)."""
    clock: dict[int, int] = defaultdict(int)

    def go(x: Stmt) -> None:
        if isinstance(x, Seq):
            for y in x.stmts:
                go(y)
        elif isinstance(x, Box):
            go(x.body)
        elif isinstance(x, (Gate, Delay)):
            st = max(clock[q] for q in x.qubits)
            for q in x.qubits:
                clock[q] = st + x.dur
        elif isinstance(x, Barrier):
            j = max((clock[q] for q in x.qubits), default=0)
            for q in x.qubits:
                clock[q] = j
        else:
            raise QtError("E-GRAPH-UNSUPPORTED", f"IBM arms may not contain {type(x).__name__}")

    if s is not None:
        go(s)
    return max(clock.values(), default=0)


class IbmBuilder(GraphBuilder):
    personality = "ibm"

    def if_(self, s: If) -> None:
        for arm in (s.then_, s.else_):
            if arm is not None and not self.contract.branch.allow_nested and _nests(arm):
                raise QtError("E-GRAPH-UNSUPPORTED", "IBM arms may not nest ifs or measure", s.loc)
        if self.contract.param("ibm", "block_start", "all_resources") != "all_resources":
            raise QtError("E-GRAPH-UNSUPPORTED", "only block_start = all_resources is implemented")
        join = self.contract.param("ibm", "join_behavior", "pad_to_longest_block")
        res = [f"q{q}" for q in sorted(touched(s.then_) | (touched(s.else_) if s.else_ else set()))]
        v = self.cond_valid(s.cond, s.nid)
        b = self.node("start", s.nid, "bstart")
        self.g.add_edge(v, b, 0, TOP, "ibm.cond-valid")
        self.join_from(res, b, "ibm.block-start")
        self.g.fact("block", s.nid, v, b)
        self.set_front(res, b)
        lit_t, lit_f = self.cond_labels(s.cond, s.nid)
        arms = [(lit_t, self.arm(s.then_, lit_t)), (lit_f, self.arm(s.else_, lit_f))]
        bend = self.node("end", s.nid, "bend")  # after the arms: creation order is topological
        if join == "pad_to_longest_block":
            dmax = max(arm_duration(s.then_), arm_duration(s.else_))
            self.g.add_edge(b, bend, dmax, TOP, "ibm.pad")
        else:  # restart_at_join: the block ends when the taken arm ends
            for lit, front in arms:
                for r in res:
                    for n, lab in front.get(r, [(b, TOP)]):
                        c = conj(lab, lit)
                        if c is not None:
                            self.g.add_edge(n, bend, 0, c, "ibm.arm-end")
        self.set_front(res, bend)


def _nests(s: Stmt) -> bool:
    if isinstance(s, (If, Measure)):
        return True
    if isinstance(s, Seq):
        return any(_nests(x) for x in s.stmts)
    if isinstance(s, Box):
        return _nests(s.body)
    return False
