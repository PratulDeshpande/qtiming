"""Backend Target -> snapshot dict (Section 7.4). Duck-typed: needs no qiskit import.

A snapshot is plain JSON so CI never needs network access:
  {"backend", "dt_ns", "alignments": {...}, "durations_ns": {name: ns}, "ambiguous": [...]}
Durations that differ across qubit tuples are NOT guessed; they are listed in `ambiguous`.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any


def _dec(x: Fraction) -> str:
    return str(x.numerator) if x.denominator == 1 else f"{x.numerator}/{x.denominator}"


def snapshot_from_target(target: Any, backend: str) -> dict[str, Any]:
    dt_ns = Fraction(str(target.dt)) * 10**9
    if (dt_ns * 1000).denominator != 1:  # must be an integer number of picoseconds
        raise ValueError(f"target dt = {target.dt} s is not an integer number of picoseconds")
    aligns = {
        "acquire": target.acquire_alignment,
        "pulse": target.pulse_alignment,
        "granularity": target.granularity,
        "min_length": target.min_length,
    }
    durations: dict[str, str] = {}
    ambiguous: list[str] = []
    for name in target.operation_names:
        vals = {
            Fraction(str(p.duration)) * 10**9
            for p in target[name].values()
            if p is not None and p.duration is not None
        }
        if len(vals) == 1:
            durations[name] = _dec(vals.pop())
        elif len(vals) > 1:
            ambiguous.append(name)
    return {
        "backend": backend,
        "dt_ns": _dec(dt_ns),
        "alignments": aligns,
        "durations_ns": durations,
        "ambiguous": sorted(ambiguous),
    }
