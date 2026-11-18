"""Verdicts (plan 13): the result, the assumptions it rests on, margins, and the evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any

from qtiming.core.ast import SourceLoc
from qtiming.core.provenance import Assumption, ProvClass, can_discharge, weakest
from qtiming.exec.engine import ExecResult
from qtiming.oblig.model import Obligation
from qtiming.solve.concrete import Result

PROVED = "PROVED"
PROVED_UNDER = "PROVED-UNDER"
REFUTED = "REFUTED"
UNKNOWN = "UNKNOWN"
EXIT_CODE = {PROVED: 0, PROVED_UNDER: 0, REFUTED: 1, UNKNOWN: 3}


@dataclass(frozen=True, slots=True)
class ObResult:
    obl: Obligation
    res: Result


@dataclass(frozen=True, slots=True)
class Verdict:
    verdict: str
    contract: str
    contract_sha256: str
    policy: str
    assumptions: tuple[Assumption, ...]
    weakest_class: str | None
    results: tuple[ObResult, ...]
    reasons: tuple[str, ...]  # why UNKNOWN / REFUTED, in plain words
    not_checked: tuple[str, ...]  # obligation kinds this build does not generate
    notes: tuple[str, ...] = ()
    max_safe: dict[str, Any] = field(default_factory=dict)
    locs: dict[int, SourceLoc] = field(default_factory=dict)  # ast nid -> source location
    traces: tuple[tuple[str, ExecResult], ...] = ()  # executor runs shown in reports

    @property
    def exit_code(self) -> int:
        return EXIT_CODE[self.verdict]


def combine(results: list[ObResult], missing: frozenset[str]) -> tuple[str, list[str]]:
    """Order REFUTED < UNKNOWN < PROVED-UNDER < PROVED; the program verdict is the minimum."""
    reasons: list[str] = []
    refuted = [r for r in results if r.res.kind == "refuted" and r.obl.severity == "safety"]
    if refuted:
        reasons = [f"{r.obl.code} at node {r.obl.nid}: {r.res.reason}" for r in refuted]
        return REFUTED, list(dict.fromkeys(reasons))
    unknown = [r for r in results if r.res.kind == "unknown"]
    if unknown or missing:
        reasons = [f"{r.obl.code} at node {r.obl.nid}: {r.res.reason}" for r in unknown]
        reasons += [f"contract bound missing: {k}" for k in sorted(missing)]
        return UNKNOWN, list(dict.fromkeys(reasons))
    ass: set[Assumption] = set()
    for r in results:
        ass |= r.obl.assumptions
    blocked = [r for r in results if r.obl.hard and not can_discharge(True, r.obl.assumptions)]
    weak = weakest(ass)
    if blocked or (weak is not None and weak < ProvClass.CYC):
        return PROVED_UNDER, []
    return PROVED, []


def to_dict(v: Verdict, dt_ns: Fraction) -> dict[str, Any]:
    """JSON-ready report (plan 13.2). Margins and bounds are given in ns and as exact fractions."""

    def ns(x: Fraction | int | None) -> str | None:
        return None if x is None else str(Fraction(x) * dt_ns)

    return {
        "verdict": v.verdict,
        "policy": v.policy,
        "contract": {"name": v.contract, "sha256": v.contract_sha256},
        "assumptions": [
            {"latency": a.key, "lo_dt": a.lo, "hi_dt": a.hi, "lo_ns": ns(a.lo), "hi_ns": ns(a.hi),
             "prov": a.prov.cls.name.lower(), "source": a.prov.source}
            for a in v.assumptions
        ],
        "weakest_class": v.weakest_class,
        "obligations": [
            {"code": r.obl.code, "nid": r.obl.nid, "result": r.res.kind, "tier": r.res.tier,
             "margin_dt": None if r.res.margin is None else str(r.res.margin),
             "margin_ns": ns(r.res.margin), "reason": r.res.reason or None}
            for r in v.results
        ],
        "counterexamples": [
            {"obligation": {"code": r.obl.code, "nid": r.obl.nid}, "tier": r.res.tier,
             "message": r.obl.message,
             "omega": dict(r.res.omega), "theta": {k: str(x) for k, x in r.res.theta.items()},
             "shortfall_dt": None if r.res.shortfall is None else str(r.res.shortfall),
             "second": None if r.res.second is None else {
                 "omega": dict(r.res.second),
                 "theta": {k: str(x) for k, x in (r.res.second_theta or {}).items()}}}
            for r in v.results if r.res.kind == "refuted"
        ],
        "reasons": list(v.reasons),
        "not_checked": list(v.not_checked),
        "notes": list(v.notes),
        "max_safe": v.max_safe,
    }
