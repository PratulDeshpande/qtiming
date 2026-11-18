"""Plain-text rendering of a verdict (the JSON form lives in `verdict.model.to_dict`)."""

from __future__ import annotations

from fractions import Fraction

from .model import Verdict


def render_text(v: Verdict, dt_ns: Fraction) -> str:
    def ns(x: Fraction | int) -> str:
        return f"{float(Fraction(x) * dt_ns):g} ns"

    sha = v.contract_sha256[:12]
    out = [f"{v.verdict}  (contract {v.contract}, policy {v.policy}, sha256 {sha})"]
    for r in v.reasons:
        out.append(f"  why: {r}")
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
    for k, h in v.max_safe.items():
        out.append(f"  max safe {k}: {h}")
    for n in v.notes:
        out.append(f"  note: {n}")
    out.append(f"  not checked by this build: {', '.join(v.not_checked)}")
    return "\n".join(out)
