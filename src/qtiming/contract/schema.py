"""Pydantic v2 input models. Floats are rejected in time fields (strict str|int only)."""

from __future__ import annotations

from fractions import Fraction
from typing import Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, model_validator

Num = Union[StrictStr, StrictInt]  # noqa: UP007  decimal string or int; never float

PROV = Literal["vendor", "msigma", "pctl", "mmax", "sched", "cyc", "cert"]
LATE = Literal["raise", "drop_log", "delay", "defer_round", "halt", "compile_error", "mixed"]
_FROZEN = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


def frac(x: Num) -> Fraction:
    """Exact decimal parse (never via float)."""
    return Fraction(str(x))


class Meta(BaseModel):
    model_config = _FROZEN
    name: str
    version: str
    schema_: Literal["qtiming-contract/0.2"] = Field(alias="schema")
    personality: Literal["ibm", "artiq", "q1", "qua"]


class LatencyIn(BaseModel):
    model_config = _FROZEN
    key: str
    src: str
    dst: str
    tier: str = "default"
    lo_ns: Num = 0
    hi_ns: Num | None = None  # None = unbounded; dependants are UNKNOWN
    data_dependent: StrictBool = False
    prov: PROV
    source: str
    n: StrictInt | None = None
    p: Num | None = None
    load: str | None = None
    k_sigma: Num | None = None
    placeholder: StrictBool = False
    meta: dict[str, str] = {}

    @model_validator(mode="after")
    def _check(self) -> LatencyIn:
        if self.prov == "mmax" and self.n is None:
            raise ValueError("prov=mmax requires n")
        if self.prov == "pctl" and (self.p is None or self.load is None):
            raise ValueError("prov=pctl requires p and load")
        if self.prov == "msigma" and self.k_sigma is None:
            raise ValueError("prov=msigma requires k_sigma")
        if self.prov in ("msigma", "pctl") and self.hi_ns is None:
            raise ValueError("msigma/pctl entries must state hi_ns explicitly; hi is never derived")
        if self.hi_ns is not None and frac(self.lo_ns) > frac(self.hi_ns):
            raise ValueError(f"lo_ns {self.lo_ns} > hi_ns {self.hi_ns}")
        return self


class Branch(BaseModel):
    model_config = _FROZEN
    klass: Literal["predicated", "equalized", "resync", "exposed", "restricted"] = Field(
        alias="class")
    default_policy: Literal["eq", "sync", "exp"]
    allow_nested: bool = True
    allow_measure_in_branch: bool = True
    allow_loops: bool = True
    max_cond_bits: int = 64


class Timebase(BaseModel):
    model_config = _FROZEN
    dt_ns: Num  # "from_target" allowed only when [target] present
    grid: dict[str, StrictInt] = {}
    latency_resolution: Literal["continuous", "dt"] = "continuous"


class Timeline(BaseModel):
    model_config = _FROZEN
    late_policy: LATE
    commit_lead: Any = None  # number (ns) or {lo_ns, prov}


class ContractIn(BaseModel):
    model_config = _FROZEN
    meta: Meta
    target: dict[str, Any] | None = None
    timebase: Timebase
    timeline: Timeline
    issue_cost: dict[str, Any] = {}
    capacity: dict[str, Any] = {}
    durations: dict[str, Any] = {}
    latency: list[LatencyIn] = Field(min_length=1)
    topology: dict[str, Any] | None = None
    feedback_tier: list[dict[str, Any]] = []
    branch: Branch
    personality_params: dict[str, Any] = {}
    dep: list[dict[str, Any]] = []
    domain_call: list[dict[str, Any]] = []
    sync: dict[str, Any] | None = None
    idle: dict[str, Any] = {}
    loop: dict[str, Any] = {}
    evidence: list[dict[str, Any]] = []
