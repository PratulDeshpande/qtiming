"""Obligations (plan 10.1): small, named, independently checkable claims about the LTEG.

They are checked against the fixed dispatch and are never added to the graph as constraints.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Union

from qtiming.core.labels import Label
from qtiming.core.provenance import Assumption

Code = Literal["O1", "O2a", "O2b", "O3", "O4", "O4a", "O5", "O6", "O7", "O8", "O9"]


@dataclass(frozen=True, slots=True)
class Diff:
    """t[x] - t[y] (<= | >=) c, with c in dt."""

    x: int
    y: int
    op: Literal["<=", ">="]
    c: int


@dataclass(frozen=True, slots=True)
class Variation:
    """max - min over all executions where the guard holds of (t[x] - t[y]) is <= bound."""

    x: int
    y: int
    bound: int


@dataclass(frozen=True, slots=True)
class Mod:
    """t[x] is a multiple of g, plus residue."""

    x: int
    g: int
    residue: int = 0


@dataclass(frozen=True, slots=True)
class Events:
    """O5: a concrete event list in SUBMISSION order, checked by the personality's rules."""

    kind: Literal["sed", "collision", "busy", "net_occupancy", "count"]
    items: tuple[tuple[int, str, int], ...]  # (commit node id, channel, issue node id)
    params: tuple[tuple[str, int], ...]


Check = Union[Diff, Variation, Mod, Events]  # noqa: UP007


@dataclass(frozen=True, slots=True)
class Obligation:
    code: Code
    nid: int  # origin AST node it protects (for reports)
    guard: Label  # outcomes under which it must hold
    check: Check
    deps: frozenset[int]  # LatVar ids in the cone of influence
    assumptions: frozenset[Assumption]
    hard: bool  # discharged only by cyc/cert evidence
    severity: Literal["safety", "advisory"]
    message: str
    needs: tuple[str, ...] = ()  # contract keys required but absent: the result is UNKNOWN

    def nodes(self) -> tuple[int, ...]:
        c = self.check
        if isinstance(c, (Diff, Variation)):
            return (c.x, c.y)
        if isinstance(c, Mod):
            return (c.x,)
        return tuple(i for it in c.items for i in (it[0], it[2]))
