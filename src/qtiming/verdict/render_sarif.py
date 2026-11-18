"""SARIF 2.1.0 rendering (plan 13.6): one `result` per refuted or unknown obligation, one note per
assumption. `partialFingerprints` hashes (code, nid, contract sha) so CI deduplicates runs."""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from typing import Any

from qtiming.core.errors import QtError

from .model import Verdict

SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"
LEVEL = {"refuted": "error", "unknown": "warning"}

DESCRIPTIONS = {
    "O1": "No underflow: every timed output is committed early enough",
    "O2a": "Result valid when consulted (stale-read safety)",
    "O2b": "No stall: the EQ wait covers the feedback latency",
    "O3": "Deadline from the arrival of a result",
    "O4": "No unplanned gap: idle gaps must not vary with outcomes or latencies",
    "O5": "Capacity: lanes, collisions, trigger-network occupancy",
    "O7": "Join determinism: a block ends at the same time for every outcome",
    "ASSUME": "A contract number the verdict relies on",
    "POLICY": "The requested timing policy is incompatible with the backend",
}


def _fp(code: str, nid: int, sha: str) -> str:
    return hashlib.sha256(f"{code}|{nid}|{sha}".encode()).hexdigest()[:32]


def _location(v: Verdict, nid: int) -> list[dict[str, Any]]:
    loc = v.locs.get(nid)
    art = {"uri": (loc.file if loc and loc.file else "program").replace("\\", "/")}
    phys: dict[str, Any] = {"artifactLocation": art}
    if loc and loc.line > 0:
        region: dict[str, int] = {"startLine": loc.line}
        if loc.col > 0:
            region["startColumn"] = loc.col
        phys["region"] = region
    return [{"physicalLocation": phys}]


def render_sarif(v: Verdict, dt_ns: Fraction, lint: list[QtError] | None = None) -> str:
    results: list[dict[str, Any]] = []
    used: set[str] = set()

    def add(rule: str, level: str, text: str, nid: int, props: dict[str, Any]) -> None:
        used.add(rule)
        results.append({
            "ruleId": f"V-{rule}" if rule in DESCRIPTIONS else rule, "level": level,
            "message": {"text": text}, "locations": _location(v, nid),
            "partialFingerprints": {"qtiming/v1": _fp(rule, nid, v.contract_sha256)},
            "properties": {"contractSha256": v.contract_sha256, "policy": v.policy, **props},
        })

    for r in v.results:
        if r.res.kind not in LEVEL:
            continue
        txt = f"{r.obl.code}: {r.obl.message}"
        if r.res.reason and r.res.reason != r.obl.message:
            txt += f" ({r.res.reason})"
        if r.res.shortfall is not None:
            txt += f"; short by {float(r.res.shortfall * dt_ns):g} ns"
        add(r.obl.code, LEVEL[r.res.kind], txt, r.obl.nid, {
            "tier": r.res.tier,
            "counterexample": {"omega": dict(r.res.omega),
                               "theta": {k: str(x) for k, x in r.res.theta.items()}}
            if r.res.kind == "refuted" else None})
    for reason in v.reasons:
        if reason.startswith("policy-incompatible"):
            add("POLICY", "error", reason, -1, {})
    for a in v.assumptions:
        hi = "unbounded" if a.hi is None else f"{float(a.hi * dt_ns):g} ns"
        add("ASSUME", "note", f"relies on {a.key} in [{float(a.lo * dt_ns):g} ns, {hi}] "
            f"({a.prov.cls.name.lower()}: {a.prov.source})", -1, {"latency": a.key})
    for e in lint or []:
        used.add(e.code)
        loc = e.loc
        uri = (loc.file if loc and loc.file else "program").replace("\\", "/")
        phys: dict[str, Any] = {"artifactLocation": {"uri": uri}}
        if loc and loc.line > 0:
            phys["region"] = {"startLine": loc.line}
        results.append({"ruleId": e.code,
                        "level": {"error": "error", "warning": "warning"}.get(e.severity, "note"),
                        "message": {"text": e.message + (f" Hint: {e.hint}" if e.hint else "")},
                        "locations": [{"physicalLocation": phys}]})
    rules = [{"id": (f"V-{c}" if c in DESCRIPTIONS else c),
              "shortDescription": {"text": DESCRIPTIONS.get(c, c)}} for c in sorted(used)]
    doc = {
        "$schema": SCHEMA, "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {"name": "qtiming", "informationUri": "https://github.com/",
                                "rules": rules}},
            "results": results,
            "properties": {"verdict": v.verdict, "contract": v.contract,
                           "contractSha256": v.contract_sha256,
                           "notChecked": list(v.not_checked)},
        }],
    }
    return json.dumps(doc, indent=2)
