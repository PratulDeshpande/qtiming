"""Structured provenance and assumption sets (finding F8)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import IntEnum
from fractions import Fraction


class ProvClass(IntEnum):
    """Evidence class, ordered by strength. The order only NAMES the weakest class.

    VENDOR documentation claim; MSIGMA mean+spread; PCTL percentile under a load;
    MMAX sample maximum over n runs; SCHED scheduler-reported value for one compiled job;
    CYC cycle-counted design bound; CERT formally certified worst case.
    """

    VENDOR = 0
    MSIGMA = 1
    PCTL = 2
    MMAX = 3
    SCHED = 4
    CYC = 5
    CERT = 6

    @property
    def may_discharge_hard(self) -> bool:
        return self >= ProvClass.CYC


@dataclass(frozen=True, slots=True)
class Prov:
    cls: ProvClass
    source: str  # citation, URL, job id, measurement id
    n: int | None = None  # MMAX: sample count
    p: Fraction | None = None  # PCTL: percentile
    load: str | None = None  # PCTL: stated load
    k_sigma: Fraction | None = None  # MSIGMA: k used by whoever STATED hi
    meta: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if self.cls == ProvClass.MMAX and self.n is None:
            raise ValueError("mmax provenance requires n")
        if self.cls == ProvClass.PCTL and (self.p is None or self.load is None):
            raise ValueError("pctl provenance requires p and load")
        if self.cls == ProvClass.MSIGMA and self.k_sigma is None:
            raise ValueError("msigma provenance requires k_sigma")


@dataclass(frozen=True, slots=True)
class Assumption:
    """One latency value a proof relied on. The verdict lists all of them."""

    key: str  # contract latency key, e.g. "ff.intra"
    lo: int  # dt
    hi: int | None  # dt
    prov: Prov


def weakest(assumptions: Iterable[Assumption]) -> ProvClass | None:
    """Weakest class among the assumptions; None for an empty set."""
    classes = [a.prov.cls for a in assumptions]
    return min(classes) if classes else None


def combine(*sets: frozenset[Assumption]) -> frozenset[Assumption]:
    """Union. The full list is kept; it is never collapsed to a single class."""
    out: set[Assumption] = set()
    for s in sets:
        out |= s
    return frozenset(out)


def can_discharge(hard: bool, assumptions: frozenset[Assumption]) -> bool:
    """A hard obligation may be discharged only if every assumption is CYC or CERT."""
    return (not hard) or all(a.prov.cls.may_discharge_hard for a in assumptions)
