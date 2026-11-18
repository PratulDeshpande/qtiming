"""The front end's output: a TQ program plus what it declared. Pure: no Qiskit."""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass, replace
from fractions import Fraction
from typing import Any, Protocol

from qtiming.core.ast import BitRef, For, Node, SourceLoc, Stmt
from qtiming.core.errors import QtError


class ContractView(Protocol):
    """What the front end needs from a contract. `contract` and `frontend` are sibling layers
    and may not import each other, so this is structural; `qtiming.contract.Contract` fits."""

    @property
    def dt_ns(self) -> Fraction: ...

    def duration(self, name: str) -> int: ...


@dataclass(frozen=True, slots=True)
class Program:
    body: Stmt
    qubits: tuple[int, ...]
    bits: tuple[BitRef, ...]
    vars: tuple[tuple[str, int], ...]  # real-time classical variables (name, width)
    notes: tuple[QtError, ...]  # warnings and notes from the front end


def _norm_value(v: Any) -> Any:
    if isinstance(v, Node):
        return normalise(v)
    if isinstance(v, tuple):
        return tuple(_norm_value(x) for x in v)
    return v


def normalise(s: Any) -> Any:
    """A copy with source locations and elaboration origins cleared, for comparing ASTs that
    came from different front ends. Node ids are kept (both walkers assign them in source order).
    A loop's variable name is cleared too: Qiskit's importer renames unused ones."""
    assert is_dataclass(s) and isinstance(s, Node)
    changes: dict[str, Any] = {"loc": SourceLoc(""), "origin_nid": None}
    if isinstance(s, For):
        changes["var"] = ""
    for f in fields(s):
        if f.name not in changes:
            changes[f.name] = _norm_value(getattr(s, f.name))
    return replace(s, **changes)
