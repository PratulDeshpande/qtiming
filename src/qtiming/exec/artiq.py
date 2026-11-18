"""ARTIQ personality (exposed cursor + CPU clock). Spec: docs/personality-spec/artiq.md.

Written separately from the graph builder and the symbolic O5 encoding on purpose: all three are
checked against the same golden traces.
"""

from __future__ import annotations

from fractions import Fraction

from qtiming.core.ast import Barrier, Delay, Gate, If, Measure
from qtiming.core.errors import QtError

from .engine import Engine, SilentDrop


class ArtiqExec(Engine):
    personality = "artiq"

    def start(self) -> None:
        c = self.contract
        self.lanes = int(c.cap("lanes", 8))  # type: ignore[call-overload]
        self.coarse = int(c.cap("coarse_mu", 8))  # type: ignore[call-overload]
        self.cost = Fraction(c.cost("cpu_issue"))
        self.cursor = Fraction(0)
        self.cpu = Fraction(0)
        self.top: list[Fraction | None] = [None] * self.lanes
        self.cur = 0
        self.by_slot: dict[tuple[str, int], Fraction] = {}
        self.busy_until: dict[str, Fraction] = {}

    def gate(self, s: Gate) -> None:
        lead = self.contract.commit_lead
        if lead is None:
            raise QtError(
                "E-EXEC-PARAM",
                "ARTIQ commit_lead is unspecified; the executor will not guess it",
                s.loc,
                hint="pass --assume timeline.commit_lead=<ns>",
            )
        self.cpu += self.cost
        issue, t = self.cpu, self.cursor
        self.rec(s.nid, "issue", issue)
        self.rec(s.nid, "commit", t)
        slack = t - issue
        if slack < lead:
            self.violate("underflow", s.nid, issue, lead - slack, "RTIO event stamped too late")
            self.halt()
            return
        ch = "q" + "_".join(map(str, s.qubits))
        self._commit(s.nid, ch, t, s.dur, issue)
        self.cursor += s.dur

    def _commit(self, nid: int, ch: str, t: Fraction, busy: int, issue: Fraction) -> None:
        coarse, fine = divmod(int(t), self.coarse)
        now_c = int(issue) // self.coarse
        for step in range(self.lanes):
            lane = (self.cur + step) % self.lanes
            top = self.top[lane]
            if top is None or top <= now_c or coarse > top:
                self.top[lane] = Fraction(coarse)
                self.cur = lane
                break
        else:
            self.drops.append(SilentDrop("sequence", nid, t, ch))
            return
        if self.by_slot.get((ch, coarse), Fraction(fine)) != fine:
            self.drops.append(SilentDrop("collision", nid, t, ch))
            return
        if t < self.busy_until.get(ch, Fraction(-1)):
            self.drops.append(SilentDrop("busy", nid, t, ch))
            return
        self.by_slot[(ch, coarse)] = Fraction(fine)
        self.busy_until[ch] = t + busy
        self.rec(nid, "emit", t, ch, "event")

    def delay(self, s: Delay) -> None:
        self.cpu += self.cost
        self.cursor += s.dur
        self.rec(s.nid, "end", self.cursor)

    def barrier(self, s: Barrier) -> None:
        return

    def measure(self, s: Measure) -> None:
        dur = self.contract.duration("measure")
        self.rec(s.nid, "start", self.cursor)
        self.cursor += dur
        self.rec(s.nid, "end", self.cursor)
        prop = self.record_outcome(s)
        theta = self.draw("input", "cpu", s.tier, s.nid)
        self.cpu = max(self.cpu + self.cost, self.cursor + theta)  # CPU blocks for the data
        self.valid[prop] = self.cpu
        self.rec(s.nid, "valid", self.cpu)

    def if_(self, s: If) -> None:
        self.cpu += self.cost
        arm = s.then_ if self.cond_value(s.cond) else s.else_
        if arm is not None:
            self.exec_stmt(arm)
