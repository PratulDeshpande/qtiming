"""Integer `dt` time, intervals, and ns -> dt conversion rounded by ROLE (finding F7)."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from .errors import QtError
from .provenance import Prov

Dt = int  # integer multiples of the backend dt
Time = Fraction  # solver / executor time (exact rational, in dt)

Role = Literal[
    "latency_lo",  # uncertain interval lower end   -> floor (outward)
    "latency_hi",  # uncertain interval upper end   -> ceil  (outward)
    "deadline",  # upper-bound requirement D        -> floor (tighter)
    "gap_bound",  # upper-bound requirement G       -> floor (tighter)
    "spread_bound",  # upper-bound requirement Delta -> floor (tighter)
    "commit_lead",  # lower-bound requirement       -> ceil  (tighter)
    "min_separation",  # lower-bound requirement    -> ceil  (tighter)
    "exact",  # fixed gate / measure duration       -> must be an exact multiple of dt
]

_ROUND: dict[str, str] = {
    "latency_lo": "floor",
    "latency_hi": "ceil",
    "deadline": "floor",
    "gap_bound": "floor",
    "spread_bound": "floor",
    "commit_lead": "ceil",
    "min_separation": "ceil",
    "exact": "exact",
}


def ns_to_dt(ns: Fraction | int | str, dt_ns: Fraction, role: Role, *, what: str = "") -> Dt:
    """Convert nanoseconds to integer dt, rounding in the SOUND direction for `role`.

    `ns` must be a Fraction, int or decimal string (never a float): the loader converts TOML
    floats with Fraction(str(x)) so 0.1 never becomes 0.1000000000000000055.
    """
    q = Fraction(ns) / Fraction(dt_ns)
    mode = _ROUND[role]
    if mode == "floor":
        return q.numerator // q.denominator
    if mode == "ceil":
        return -((-q.numerator) // q.denominator)
    if q.denominator != 1:
        raise QtError(
            "E-TIME-EXACT",
            f"{what or 'value'} = {ns} ns is not an integer multiple of dt = {dt_ns} ns",
            hint="fix the contract or Target; fixed durations must be exact",
        )
    return q.numerator


def dt_to_ns(x: Time | Dt, dt_ns: Fraction) -> Fraction:
    return Fraction(x) * Fraction(dt_ns)


@dataclass(frozen=True, slots=True)
class Interval:
    """Closed interval [lo, hi] of dt; hi=None means unbounded above (dependants are UNKNOWN)."""

    lo: Dt
    hi: Dt | None

    def __post_init__(self) -> None:
        if self.hi is not None and self.lo > self.hi:
            raise QtError("E-INTERVAL", f"empty interval [{self.lo}, {self.hi}]")

    @property
    def bounded(self) -> bool:
        return self.hi is not None

    def __add__(self, o: Interval) -> Interval:
        hi = None if self.hi is None or o.hi is None else self.hi + o.hi
        return Interval(self.lo + o.lo, hi)

    def hull(self, o: Interval) -> Interval:
        hi = None if self.hi is None or o.hi is None else max(self.hi, o.hi)
        return Interval(min(self.lo, o.lo), hi)

    def contains(self, x: Time | Dt) -> bool:
        return self.lo <= x and (self.hi is None or x <= self.hi)


@dataclass(frozen=True, slots=True)
class Latency:
    """A named uncertain latency from the contract: interval plus structured provenance."""

    key: str  # contract name, e.g. "ff.default"
    iv: Interval
    prov: Prov
