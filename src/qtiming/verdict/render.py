"""Plain-text rendering of a verdict (the JSON form lives in `verdict.model.to_dict`)."""

from __future__ import annotations

from fractions import Fraction

from qtiming.exec.engine import ExecResult

from .model import Verdict


def ascii_timeline(run: ExecResult, dt_ns: Fraction, width: int = 60) -> list[str]:
    """One row per resource, time axis in ns, an event drawn as the first letter of its op;
    a violating event is marked `!`."""
    if not run.trace:
        return []
    tmax = max(e.t for e in run.trace) or Fraction(1)
    rows = sorted({e.resource for e in run.trace})
    bad = {x.nid for x in run.violations}
    lines = [f"{'t(ns)':<10}0{' ' * (width - 12)}{float(tmax * dt_ns):g}"]
    for r in rows:
        cells = ["."] * (width + 1)
        for e in run.trace:
            if e.resource == r:
                cells[int(e.t / tmax * width)] = "!" if e.nid in bad else (e.op[:1] or "?")
        lines.append(f"{r[:9]:<10}{''.join(cells)}")
    for x in run.violations:
        lines.append(f"  ^ {x.kind} at {float(x.t * dt_ns):g} ns (node {x.nid}): {x.detail}")
    return lines


def render_text(v: Verdict, dt_ns: Fraction) -> str:
    def ns(x: Fraction | int) -> str:
        return f"{float(Fraction(x) * dt_ns):g} ns"

    sha = v.contract_sha256[:12]
    out = [f"{v.verdict}  (contract {v.contract}, policy {v.policy}, sha256 {sha})"]
    for r in v.reasons:
        out.append(f"  why: {r}")
    for r in v.results:
        if r.res.kind != "refuted":
            continue
        loc = v.locs.get(r.obl.nid)
        where = (f"{loc.file}:{loc.line}".replace("\\", "/") if loc and loc.line
                 else f"node {r.obl.nid}")
        short = "" if r.res.shortfall is None else f", short by {ns(r.res.shortfall)}"
        out.append(f"  {r.obl.code} failed at {where} (tier {r.res.tier}{short})")
    if v.assumptions:
        out.append(f"  assumptions (weakest class: {v.weakest_class}):")
        for a in v.assumptions:
            hi = "unbounded" if a.hi is None else ns(a.hi)
            cls = a.prov.cls.name.lower()
            out.append(f"    {a.key}: [{ns(a.lo)}, {hi}]  {cls}: {a.prov.source}")
    by_code: dict[str, list[str]] = {}
    for r in v.results:
        tier = "-" if r.res.tier is None else str(r.res.tier)
        margin = "" if r.res.margin is None else f", margin {ns(r.res.margin)}"
        by_code.setdefault(r.obl.code, []).append(f"{r.res.kind} (tier {tier}{margin})")
    for code in sorted(by_code):
        kinds = by_code[code]
        out.append(f"  {code}: {len(kinds)} obligation(s): {'; '.join(sorted(set(kinds)))}")
    for label, run in v.traces[:2]:
        lines = ascii_timeline(run, dt_ns)
        if lines and v.verdict == "REFUTED":
            out.append(f"  timeline ({label}):")
            out += [f"    {ln}" for ln in lines]
    for k, h in v.max_safe.items():
        out.append(f"  max safe {k}: {h}")
    for n in v.notes:
        out.append(f"  note: {n}")
    out.append(f"  not checked by this build: {', '.join(v.not_checked)}")
    return "\n".join(out)
