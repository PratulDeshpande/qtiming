"""Stable node ids and proposition keys (occurrence-keyed, so loop iterations stay distinct)."""

from __future__ import annotations


class IdGen:
    """Source-order nid generator. One per front-end run; ids are never recomputed."""

    def __init__(self) -> None:
        self._n = 0

    def next(self) -> int:
        n = self._n
        self._n += 1
        return n


def _iter(it: int | None) -> str:
    return "" if it is None else f"#i{it}"


def bit_prop(reg: str, idx: int, nid: int, it: int | None = None) -> str:
    """Bit written by measurement node `nid` (iteration `it`): 'c[0]@m17#i3'."""
    return f"{reg}[{idx}]@m{nid}{_iter(it)}"


def cond_prop(nid: int, it: int | None = None) -> str:
    """Derived proposition for the condition of node `nid`: 'cond@n42#i3'."""
    return f"cond@n{nid}{_iter(it)}"


def lat_occurrence(key: str, meas_nid: int, it: int | None = None) -> str:
    """One contingent latency occurrence (key + the measurement it follows): 'ff.default@m17#i3'."""
    return f"{key}@m{meas_nid}{_iter(it)}"
