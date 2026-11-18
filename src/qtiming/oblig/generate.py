"""Obligation generation (plan 10.6) from the facts the dispatch builders recorded on the LTEG.

Generated: O1, O2a, O2b, O3, O4, O5 (ARTIQ sed, Q1 trigger-network occupancy), O7 (EQ blocks).
NOT generated yet (`NOT_GENERATED`): O6 blocking calls, O8 grids, O9 loop windows, O4a, and O7 for
SYNC with a spread bound. The verdict lists them so a PROVED is never read as covering them.
"""

from __future__ import annotations

from qtiming.contract.model import Contract
from qtiming.core.labels import TOP, Label, conj
from qtiming.core.provenance import Assumption
from qtiming.elab import ElabProgram
from qtiming.graph.lteg import LTEG, LatVar

from .model import Check, Code, Diff, Events, Obligation, Variation

NOT_GENERATED = (
    "O4a (off by default)", "O6 (blocking calls)", "O8 (grid)", "O9 (loop windows)",
    "O7 for SYNC with a spread bound",
)


def ancestors(g: LTEG, nodes: tuple[int, ...]) -> set[int]:
    seen: set[int] = set()
    stack = list(nodes)
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        stack += [g.edges[e].src for e in g.in_edges[n]]
    return seen


def make(g: LTEG, code: Code, nid: int, guard: Label, check: Check, message: str, *,
         needs: tuple[str, ...] = (), hard: bool = False) -> Obligation:
    o = Obligation(code, nid, guard, check, frozenset(), frozenset(), hard, "safety", message,
                   needs)
    cone = ancestors(g, o.nodes())
    lats: dict[int, LatVar] = {}
    for n in cone:
        for ei in g.in_edges[n]:
            w = g.edges[ei].w
            if isinstance(w, LatVar):
                lats[w.id] = w
    ass = frozenset(Assumption(v.key, v.lo, v.hi, v.prov) for v in lats.values())
    return Obligation(code, nid, guard, check, frozenset(lats), ass, hard, "safety", message,
                      needs)


def _label(g: LTEG, *nodes: int) -> Label:
    lab: Label = TOP
    for n in nodes:
        c = conj(lab, g.nodes[n].label)
        if c is not None:
            lab = c
    return lab


def generate(g: LTEG, el: ElabProgram, c: Contract) -> list[Obligation]:
    out: list[Obligation] = []
    pers = c.personality
    facts = g.facts

    # O1: no underflow
    for nid, issue, commit in facts.get("commit", []):
        needs = () if c.commit_lead is not None else ("timeline.commit_lead",)
        out.append(make(g, "O1", nid, _label(g, commit, issue),
                        Diff(commit, issue, ">=", c.commit_lead or 0),
                        "RTIO event must be committed at least commit_lead before its timestamp",
                        needs=needs))
    for nid, issue, ex in facts.get("rt", []):
        out.append(make(g, "O1", nid, _label(g, ex, issue), Diff(ex, issue, ">=", 0),
                        "the RT core must never need an instruction the Q1 core has not issued"))

    # O2a: result valid when consulted (predicated reads)
    for nid, ex, v in facts.get("cond_read", []):
        out.append(make(g, "O2a", nid, _label(g, ex, v), Diff(ex, v, ">=", 0),
                        "the condition result must be valid when the RT core consults it"))

    # O2b: no stall (EQ branches only)
    for nid, v, ready in facts.get("ready", []):
        pol = el.policy_map.get(nid)
        if pol is not None and pol.kind == "eq":
            out.append(make(g, "O2b", nid, _label(g, ready, v), Diff(ready, v, ">=", 0),
                            "EQ wait must cover the feedback latency so the branch never stalls"))

    # O3: deadlines
    tags = ("start", "exec", "commit", "cpu")
    for wnid, (deadline, prop) in el.within.items():
        valid = next((n.id for n in g.nodes if n.obs == prop), None)
        if valid is None:
            continue
        for _q, nids in el.first_ops.get(wnid, {}).items():
            for first in nids:
                node = next((i for t in tags for i in g.by_key(first, t)), None)
                if node is None:
                    continue
                out.append(make(g, "O3", wnid, _label(g, node, valid),
                                Diff(node, valid, "<=", deadline),
                                "first operation must start within the deadline after the result",
                                hard=wnid in el.hard))

    # O4: no unplanned gap (a gap whose length varies breaks compile-time DD / phase tracking)
    if pers in ("ibm", "qua"):
        bound = dict(c.idle_variation).get("default", 0)
        seen: set[tuple[int, int, Label]] = set()
        for nid, res, end, start, lab in facts.get("gap", []):
            guard = conj(lab, g.nodes[start].label)
            if guard is None or (start, end, guard) in seen:
                continue
            seen.add((start, end, guard))
            out.append(make(g, "O4", nid, guard, Variation(start, end, bound),
                            f"idle gap on {res} must not vary with outcomes or latencies"))

    # O5: capacity
    if pers == "artiq" and facts.get("commit"):
        items = tuple((cm, f"q{n}", iss) for n, iss, cm in facts["commit"])
        params = (("lanes", int(c.cap("lanes", 8))), ("coarse", int(c.cap("coarse_mu", 8))))  # type: ignore[call-overload]
        out.append(make(g, "O5", facts["commit"][0][0], TOP, Events("sed", items, params),
                        "SED lanes: no sequence error, collision or busy drop"))
    if pers == "q1":
        busy = next((cl for cl in c.latencies if cl.latency.key == "trigger.network_busy"), None)
        ends = [n.id for n in g.nodes if n.kind == "end" and n.resource == "rt"]
        if busy is not None and busy.latency.iv.hi is not None:
            for a, b in zip(ends, ends[1:], strict=False):
                out.append(make(g, "O5", g.nodes[b].nid, _label(g, a, b),
                                Diff(b, a, ">=", busy.latency.iv.hi),
                                "a second trigger inside the network busy window is lost"))

    # O7: join determinism for EQ blocks
    bars = dict(facts.get("eqbar", []))
    for nid, bend in facts.get("blockend", []):
        pol = el.policy_map.get(nid)
        if pol is not None and pol.kind == "eq" and nid in bars:
            out.append(make(g, "O7", nid, _label(g, bend, bars[nid]),
                            Variation(bend, bars[nid], 0),
                            "an EQ block must end at the same time for every outcome"))
    for nid, first, nxt in facts.get("q1join", []):
        pol = el.policy_map.get(nid)
        if pol is not None and pol.kind == "eq":
            out.append(make(g, "O7", nid, _label(g, first, nxt), Variation(nxt, first, 0),
                            "an EQ block must take the same RT time for every outcome"))
    return out
