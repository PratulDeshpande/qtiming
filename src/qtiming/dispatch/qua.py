"""QUA dispatch rules (plan 9.4.4). Spec: Docs/personality-spec/qua.md."""

from __future__ import annotations

from qtiming.core.ast import Barrier, Box, Delay, Gate, If, Seq, Stmt
from qtiming.core.labels import TOP
from qtiming.graph.builder import GraphBuilder, touched


def single_op(s: Stmt | None) -> Gate | Delay | None:
    while isinstance(s, (Seq, Box)):
        inner = s.stmts if isinstance(s, Seq) else (s.body,)
        if len(inner) != 1:
            return None
        s = inner[0]
    return s if isinstance(s, (Gate, Delay)) and len(s.qubits) == 1 else None


class QuaBuilder(GraphBuilder):
    personality = "qua"

    def __init__(self, contract):  # type: ignore[no-untyped-def]
        super().__init__(contract)
        self.dynamic: set[int] = set()
        self.tier = str(contract.param("qua", "align_tier", "same_fem"))
        self.skip_implicit = bool(contract.param("qua", "skip_implicit_align", False))

    def _align(self, qubits: list[int], nid: int, join_tag: str, extra: int | None = None) -> None:
        res = [f"q{q}" for q in qubits]
        ready: int | None = None
        if extra is not None:
            ready = self.node("join", nid, "bready")  # resources only: when the arm COULD start
            self.join_from(res, ready, "qua.block-ready")
        j = self.node("join", nid, join_tag)
        if ready is not None and extra is not None:
            self.g.add_edge(ready, j, 0, TOP, "qua.block-start")
            self.g.add_edge(extra, j, 0, TOP, "qua.cond-valid")
            self.g.fact("ready", nid, extra, ready)
        else:
            self.join_from(res, j, "qua.align")
        last = j
        if any(q in self.dynamic for q in qubits):  # non-deterministic align: uncertain gap
            last = self.node("align", nid, "align")
            self.g.add_edge(j, last, self.latvar(nid, "align", "align", self.tier), TOP,
                            "qua.align-gap")
        self.set_front(res, last, real=False)
        self.dynamic.difference_update(qubits)

    def barrier(self, s: Barrier) -> None:
        self._align(list(s.qubits), s.nid, "join")

    def if_(self, s: If) -> None:
        part = sorted(touched(s.then_) | (touched(s.else_) if s.else_ else set()))
        v = self.cond_valid(s.cond, s.nid)
        if self.skip_implicit:
            for q in part:
                ready = self.node("start", s.nid, f"ready{q}")
                self.g.add_edge(v, ready, 0, TOP, "qua.cond-valid")
                self.join_from([f"q{q}"], ready, "qua.ready")
                self.set_front([f"q{q}"], ready, real=False)
        else:
            self._align(part, s.nid, "ialign", extra=v)
        lit_t, lit_f = self.cond_labels(s.cond, s.nid)
        lone = single_op(s.then_) if s.else_ is None else None
        before = {r: list(x) for r, x in self.front.items()}
        arms = [(lit_t, self.arm(s.then_, lit_t))]
        if lone is not None:  # false path waits as long as the play would last
            q = lone.qubits[0]
            saved, saved_ctx = self.front, self.ctx
            from qtiming.core.labels import conj

            merged = conj(saved_ctx, lit_f)
            assert merged is not None
            self.front = {r: list(x) for r, x in saved.items()}
            self.ctx = merged
            self.span(lone.nid, (q,), lone.dur, "false-wait", tags=("fstart", "fend"))
            arms.append((lit_f, self.front))
            self.front, self.ctx = saved, saved_ctx
        else:
            arms.append((lit_f, self.arm(s.else_, lit_f)))
        self.merge_arms(before, arms)
        if lone is None:
            self.dynamic.update(part)
