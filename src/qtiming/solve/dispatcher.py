"""Tier dispatcher (plan 11.1): route each obligation to the cheapest sound tier.

Tier 0 (exact) when the cone has no latency variable; Tier 1 (sound, never refutes) otherwise.
Tier 2 (exact SMT, counterexamples) is not built yet: what Tier 1 cannot prove is UNKNOWN, and the
reason says so. Tier 3 synthesis is never called from here (import-linter `synthesis-isolated`).
"""

from __future__ import annotations

from dataclasses import dataclass

from qtiming.graph.lteg import LTEG
from qtiming.oblig.model import Obligation

from .concrete import Result, tier0
from .interval import tier1


@dataclass(frozen=True, slots=True)
class SolveCfg:
    tier0_scenario_cap: int = 4096
    use_tier1: bool = True
    use_tier2: bool = True
    timeout_ms: int = 10_000


def _tier2(g: LTEG, o: Obligation, cfg: SolveCfg) -> Result | None:
    if not cfg.use_tier2:
        return None
    try:
        from .smt import tier2
    except ImportError:  # z3 is an optional extra
        return Result("unknown", reason="Tier 2 needs z3: pip install 'qtiming[z3]'")
    return tier2(g, o, cfg.timeout_ms)


def verify(g: LTEG, o: Obligation, cfg: SolveCfg | None = None) -> Result:
    cfg = cfg or SolveCfg()
    if o.needs:
        return Result("unknown", reason=f"missing contract field: {', '.join(o.needs)}")
    if not o.deps:
        r = tier0(g, o, cfg.tier0_scenario_cap)
        if r.kind != "unknown":
            return r
    elif cfg.use_tier1:
        t1 = tier1(g, o)
        if t1.proved:
            return Result("proved", 1, margin=t1.margin)
    r2 = _tier2(g, o, cfg)
    if r2 is not None:
        return r2
    unbounded = sorted({v.key for v in g.lats if v.id in o.deps and v.hi is None})
    if unbounded:
        return Result("unknown", reason=f"latency bound missing: {', '.join(unbounded)}")
    return Result("unknown", reason="Tier 1 inconclusive and Tier 2 is disabled")
