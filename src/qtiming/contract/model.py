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

    def find_latency(self, src: str, dst: str, tier: str = "default") -> ContractLatency:
        """The latency declared from `src` to `dst` for `tier` (falls back to tier 'default')."""
        hit = None
        for cl in self.latencies:
            if cl.src == src and cl.dst == dst:
                if cl.tier == tier:
                    return cl
                if cl.tier == "default" and hit is None:
                    hit = cl
        if hit is None:  # a single declared src->dst latency serves every tier
            cands = [cl for cl in self.latencies if cl.src == src and cl.dst == dst]
            hit = cands[0] if len(cands) == 1 else None
        if hit is None:
            raise QtError("E-CT-MISSING", f"contract {self.name!r} has no latency {src}->{dst}")
        return hit

    def param(self, personality: str, name: str, default: object = None) -> object:
        """A personality parameter from `[personality_params.<personality>]`."""
        for k, v in self.params:
            if k == personality and isinstance(v, tuple):
                for k2, v2 in v:
                    if k2 == name:
                        return v2
        return default

    def cap(self, name: str, default: object = None) -> object:
        for k, v in self.capacity:
            if k == name:
                return v
        return default

    def cost(self, name: str, field: str | None = None) -> int:
        """Issue cost in dt: `field` if given, else the first of ns, hi_ns, lo_ns present."""
        for ic in self.issue_cost:
            if ic.name == name:
                d = dict(ic.fields)
                for f in ((field,) if field else ("ns", "hi_ns", "lo_ns")):
                    if f in d:
                        return d[f]
        raise QtError("E-CT-MISSING", f"contract {self.name!r} has no issue_cost {name}")
