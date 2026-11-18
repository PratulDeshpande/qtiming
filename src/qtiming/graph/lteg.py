"""The labelled timed event graph (LTEG): the single IR every verification tier reads (plan 9).

Dispatch semantics (plan 9.1), for a fixed outcome assignment omega and latency realisation theta:

    exists(v) iff omega |= label(v) and (v is the origin or some in-edge of v is active)
    active(e) iff omega |= label(e) and exists(src(e))
    t(origin) = 0;  t(v) = snap_v(max over active in-edges (t(src) + w))

A MAX, not a set of difference constraints (finding F2).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Union

from qtiming.core.labels import TOP, Derived, Label, Prop, evaluate
from qtiming.core.provenance import Prov


@dataclass(frozen=True, slots=True)
class LatVar:
    """One contingent latency OCCURRENCE (fresh per measurement / align / consumer)."""

    id: int
    key: str  # contract key, e.g. "ff.default"
    occurrence: str  # "ff.default@m17": the executor's oracle key
    lo: int
    hi: int | None
    prov: Prov


Weight = Union[int, LatVar]  # noqa: UP007


@dataclass(frozen=True, slots=True)
class Node:
    id: int
    kind: str  # origin start end valid join issue exec cursor commit cpu align
    nid: int  # originating AST node
    tag: str  # event tag shared with the executor's times: (nid, tag)
    resource: str | None
    label: Label = TOP
    obs: Prop | None = None
    snap: int | None = None


@dataclass(frozen=True, slots=True)
class DEdge:
    src: int
    dst: int
    w: Weight
    label: Label
    tag: str


@dataclass(slots=True)
class LTEG:
    personality: str
    contract_sha256: str
    nodes: list[Node] = field(default_factory=list)
    edges: list[DEdge] = field(default_factory=list)
    lats: list[LatVar] = field(default_factory=list)
    derived: dict[Prop, Derived] = field(default_factory=dict)
    in_edges: dict[int, list[int]] = field(default_factory=dict)
    out_edges: dict[int, list[int]] = field(default_factory=dict)
    origin: int = 0
    # facts the obligation generator reads (node-id tuples), by kind:
    #   "commit":    (ast nid, issue node, commit node)        ARTIQ O1
    #   "rt":        (ast nid, issue node, exec node)           Q1 O1
    #   "cond_read": (ast nid, exec node, valid node)           Q1 O2a
    #   "block":     (ast nid, valid node, bstart node)         IBM/QUA branch start
    #   "ready":     (ast nid, valid node, bready node)         O2b (resources-only ready node)
    #   "gap":       (ast nid, resource, end node, start node, label)   O4
    #   "eqbar":     (if nid, barrier join node)                 EQ reference for O7
    #   "blockend":  (if nid, bend node)                         IBM block end
    #   "q1join":    (if nid, first exec in block, next exec)    Q1 O7
    facts: dict[str, list[tuple[Any, ...]]] = field(default_factory=dict)

    def fact(self, kind: str, *ids: Any) -> None:
        self.facts.setdefault(kind, []).append(tuple(ids))

    def add_node(self, kind: str, nid: int, tag: str, resource: str | None = None,
                 label: Label = TOP, obs: Prop | None = None, snap: int | None = None) -> int:
        n = Node(len(self.nodes), kind, nid, tag, resource, label, obs, snap)
        self.nodes.append(n)
        self.in_edges[n.id] = []
        self.out_edges[n.id] = []
        return n.id

    def add_edge(self, src: int, dst: int, w: Weight, label: Label, tag: str) -> None:
        e = DEdge(src, dst, w, label, tag)
        self.in_edges[dst].append(len(self.edges))
        self.out_edges[src].append(len(self.edges))
        self.edges.append(e)

    def add_lat(self, key: str, occurrence: str, lo: int, hi: int | None, prov: Prov) -> LatVar:
        v = LatVar(len(self.lats), key, occurrence, lo, hi, prov)
        self.lats.append(v)
        return v

    def by_key(self, nid: int, tag: str) -> list[int]:
        return [n.id for n in self.nodes if n.nid == nid and n.tag == tag]


def _env(g: LTEG, omega: Mapping[str, int]) -> dict[str, int]:
    env = dict(omega)
    for p, d in g.derived.items():  # derived propositions: exact definitions over bit props
        if all(o in omega for o in d.operands):  # a cone restriction may not bind unrelated ones
            env[p] = evaluate(d.expr, env)
    return env


def holds(label: Label, env: Mapping[str, int]) -> bool:
    return all(bool(env[lit.prop]) == lit.pos for lit in label)


def dispatch_times(
    g: LTEG,
    omega: Mapping[str, int],
    theta: Mapping[str, Fraction | int],
    restrict: set[int] | None = None,
) -> dict[int, Fraction]:
    """Dispatch time of every node that exists, keyed by node id (optionally only `restrict`)."""
    env = _env(g, omega)
    t: dict[int, Fraction] = {g.origin: Fraction(0)}
    for n in g.nodes:  # creation order is a topological order (every edge points forward)
        if n.id == g.origin or (restrict is not None and n.id not in restrict):
            continue
        if not holds(n.label, env):
            continue
        cands = []
        for ei in g.in_edges[n.id]:
            e = g.edges[ei]
            if e.src in t and holds(e.label, env):
                w = e.w if isinstance(e.w, int) else Fraction(theta[e.w.occurrence])
                cands.append(t[e.src] + w)
        if cands:
            x = max(cands)
            if n.snap:
                x = n.snap * -((-x) // n.snap)
            t[n.id] = x
    return t


def evaluate_graph(
    g: LTEG, omega: Mapping[str, int], theta: Mapping[str, Fraction | int]
) -> dict[tuple[int, str], Fraction]:
    """Dispatch times of every node that exists, keyed by (ast nid, tag)."""
    t = dispatch_times(g, omega, theta)
    return {(n.nid, n.tag): t[n.id] for n in g.nodes if n.id in t and n.id != g.origin}
