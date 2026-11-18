"""ARTIQ dispatch rules (plan 9.4.3). Spec: Docs/personality-spec/artiq.md.

Two chains: the CPU wall clock and the cursor (stamped time). The commit node's time is the
cursor, so it does not move when the CPU is late; O1 (commit - issue >= lead) is a fact, not an
edge (finding F2). The SED lane rules (O5) belong to the obligation layer.
"""

from __future__ import annotations

from qtiming.core.ast import Barrier, Delay, Gate, If, Measure
from qtiming.core.labels import TOP
from qtiming.graph.builder import GraphBuilder


class ArtiqBuilder(GraphBuilder):
    personality = "artiq"

    def __init__(self, contract):  # type: ignore[no-untyped-def]
        super().__init__(contract)
        self.cost = contract.cost("cpu_issue")

    def cpu_step(self, nid: int, tag: str, kind: str = "cpu") -> int:
        n = self.node(kind, nid, tag, "cpu")
        for src, lab in self.entries("cpu"):
            self.g.add_edge(src, n, self.cost, lab, "artiq.cpu-chain")
        self.set_front(["cpu"], n)
        return n

    def gate(self, s: Gate) -> None:
        issue = self.cpu_step(s.nid, "issue", "issue")
        commit = self.node("commit", s.nid, "commit", "cursor")
        self.join_from(["cursor"], commit, "artiq.stamp")
        self.g.fact("commit", s.nid, issue, commit)
        after = self.node("cursor", s.nid, "cend", "cursor")
        self.g.add_edge(commit, after, s.dur, TOP, "artiq.pulse")
        self.set_front(["cursor"], after)

    def delay(self, s: Delay) -> None:
        self.cpu_step(s.nid, "cpu")
        end = self.node("cursor", s.nid, "end", "cursor")
        for src, lab in self.entries("cursor"):
            self.g.add_edge(src, end, s.dur, lab, "artiq.delay")
        self.set_front(["cursor"], end)

    def barrier(self, s: Barrier) -> None:
        return

    def measure(self, s: Measure) -> None:
        start = self.node("cursor", s.nid, "start", "cursor")
        self.join_from(["cursor"], start, "artiq.gate-window")
        end = self.node("cursor", s.nid, "end", "cursor")
        self.g.add_edge(start, end, self.contract.duration("measure"), TOP, "artiq.window")
        self.set_front(["cursor"], end)
        from qtiming.core.ids import bit_prop

        prop = bit_prop(s.cbit.reg, s.cbit.idx, s.nid)
        v = self.node("valid", s.nid, "valid", "cpu", obs=prop)
        for src, lab in self.entries("cpu"):  # CPU keeps issuing ...
            self.g.add_edge(src, v, self.cost, lab, "artiq.cpu-chain")
        # ... but blocks until the input event data arrives: a second in-edge (a MAX)
        self.g.add_edge(end, v, self.latvar(s.nid, "input", "cpu", s.tier), TOP, "artiq.in2cpu")
        self.set_front(["cpu"], v)
        self.valid_node[prop] = v

    def if_(self, s: If) -> None:
        self.cpu_step(s.nid, "cpu")
        lit_t, lit_f = self.cond_labels(s.cond, s.nid)
        before = {r: list(x) for r, x in self.front.items()}
        arms = [(lit_t, self.arm(s.then_, lit_t)), (lit_f, self.arm(s.else_, lit_f))]
        self.merge_arms(before, arms)
