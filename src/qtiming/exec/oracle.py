"""Oracles: where outcomes (bits) and latency realisations come from during a run."""

from __future__ import annotations

import random
from collections.abc import Mapping
from fractions import Fraction
from typing import Protocol

from qtiming.core.errors import QtError
from qtiming.core.time import Interval


class Oracle(Protocol):
    def outcome(self, prop: str) -> int: ...
    def latency(self, occurrence: str, iv: Interval) -> Fraction: ...


class NeedChoice(Exception):
    """Raised by a strict `Fixed` when a run asks for a value the assignment does not give."""

    def __init__(self, kind: str, key: str, iv: Interval | None = None) -> None:
        super().__init__(kind, key)
        self.kind, self.key, self.iv = kind, key, iv


class Fixed:
    """Replays a counterexample. Unspecified latencies take the interval midpoint, unspecified
    bits 0, and the defaults used are recorded in `defaulted`. `strict` raises `NeedChoice`."""

    def __init__(
        self,
        omega: Mapping[str, int] | None = None,
        theta: Mapping[str, Fraction | int] | None = None,
        *,
        strict: bool = False,
    ) -> None:
        self.omega, self.theta, self.strict = dict(omega or {}), dict(theta or {}), strict
        self.defaulted: list[str] = []

    def outcome(self, prop: str) -> int:
        if prop in self.omega:
            return int(self.omega[prop])
        if self.strict:
            raise NeedChoice("bit", prop)
        self.defaulted.append(prop)
        return 0

    def latency(self, occurrence: str, iv: Interval) -> Fraction:
        if occurrence in self.theta:
            v = Fraction(self.theta[occurrence])
            if not iv.contains(v):
                raise QtError("E-EXEC-THETA", f"{occurrence} = {v} outside [{iv.lo}, {iv.hi}]")
            return v
        if self.strict:
            raise NeedChoice("lat", occurrence, iv)
        self.defaulted.append(occurrence)
        return Fraction(iv.lo) if iv.hi is None else Fraction(iv.lo + iv.hi, 2)


class Random:
    """Seeded coin outcomes; latencies uniform on a 1/8 dt grid inside [lo, hi]."""

    def __init__(self, seed: int) -> None:
        self._r = random.Random(seed)

    def outcome(self, prop: str) -> int:
        return self._r.getrandbits(1)

    def latency(self, occurrence: str, iv: Interval) -> Fraction:
        if iv.hi is None:
            raise QtError("E-EXEC-UNBOUNDED", f"{occurrence}: unbounded latency, use Fixed")
        return Fraction(self._r.randint(iv.lo * 8, iv.hi * 8), 8)


class Extreme:
    """Every latency at `lo` or `hi` (`pick`), bits from `omega` (default 0)."""

    def __init__(self, pick: str = "hi", omega: Mapping[str, int] | None = None) -> None:
        self.pick, self.omega = pick, dict(omega or {})

    def outcome(self, prop: str) -> int:
        return int(self.omega.get(prop, 0))

    def latency(self, occurrence: str, iv: Interval) -> Fraction:
        if self.pick == "hi" and iv.hi is not None:
            return Fraction(iv.hi)
        return Fraction(iv.lo)
