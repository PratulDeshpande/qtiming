"""The frozen, validated Contract the rest of the pipeline sees (all times integer dt)."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from qtiming.core.errors import QtError
from qtiming.core.time import Latency


@dataclass(frozen=True, slots=True)
class ContractLatency:
    latency: Latency
    src: str
    dst: str
    tier: str
    lo_ns: Fraction  # as declared, before outward rounding
    hi_ns: Fraction | None
    data_dependent: bool
    placeholder: bool


@dataclass(frozen=True, slots=True)
class IssueCost:
    name: str
    fields: tuple[tuple[str, int], ...]  # (field, dt); upper bounds rounded up
    prov_cls: str
    source: str


@dataclass(frozen=True, slots=True)
class BranchSpec:
    klass: str
    default_policy: str
    allow_nested: bool
    allow_measure_in_branch: bool
    allow_loops: bool
    max_cond_bits: int


@dataclass(frozen=True, slots=True)
class Contract:
    name: str
    version: str
    personality: str
    dt_ns: Fraction
    grid: tuple[tuple[str, int], ...]
    late_policy: str
    commit_lead: int | None
    durations: tuple[tuple[str, int], ...]
    latencies: tuple[ContractLatency, ...]
    issue_cost: tuple[IssueCost, ...]
    branch: BranchSpec
    capacity: tuple[tuple[str, object], ...]
    params: tuple[tuple[str, object], ...]
    idle_variation: tuple[tuple[str, int], ...]
    dd_inserted: str
    while_supported: bool
    extras: tuple[tuple[str, object], ...]
    overrides: tuple[str, ...]
    assumed: tuple[str, ...]
    missing: tuple[str, ...]
    warnings: tuple[str, ...]
    target_snapshot: str | None
    sha256: str

    def latency(self, key: str) -> ContractLatency:
        for cl in self.latencies:
            if cl.latency.key == key:
                return cl
        raise QtError("E-CT-MISSING", f"contract {self.name!r} has no latency {key!r}")

    def duration(self, name: str) -> int:
        for n, d in self.durations:
            if n == name:
                return d
        raise QtError(
            "E-CT-MISSING",
            f"contract {self.name!r} has no duration for {name!r}",
            hint="add it to [durations] or import it from the backend Target",
        )
