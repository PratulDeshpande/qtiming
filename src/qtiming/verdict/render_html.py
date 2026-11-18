"""Static HTML report with an inline SVG timeline (plan 13.6).

Generated from the executor trace of the replayed counterexample (or a typical run), so it shows
exactly what the independent executor did. One row per resource; both executions for Variation.
"""

from __future__ import annotations

import html
from fractions import Fraction

from qtiming.exec.engine import ExecResult

from .model import Verdict

W, ROW, PAD = 760, 26, 80


def svg_timeline(label: str, run: ExecResult, dt_ns: Fraction) -> str:
    tr = run.trace
    if not tr:
        return f"<p><em>{html.escape(label)}: no timed events.</em></p>"
    res = sorted({e.resource for e in tr})
    tmax = max(e.t for e in tr) or Fraction(1)
    h = ROW * (len(res) + 1)
    out = [f'<svg viewBox="0 0 {W + PAD} {h}" role="img" aria-label="{html.escape(label)}" '
           f'width="100%">']
    out.append(f'<text x="2" y="14" font-size="11">{html.escape(label)}</text>')
    for i, r in enumerate(res):
        y = ROW * (i + 1)
        out.append(f'<text x="2" y="{y + 15}" font-size="11">{html.escape(r)}</text>')
        out.append(f'<line x1="{PAD}" x2="{PAD + W}" y1="{y + 18}" y2="{y + 18}" '
                   'stroke="#bbb" stroke-width="1"/>')
    bad = {v.nid for v in run.violations}
    for e in tr:
        x = PAD + float(e.t / tmax) * (W - 10)
        y = ROW * (res.index(e.resource) + 1)
        colour = "#c0392b" if e.nid in bad else "#2c6fbb"
        tip = f"{e.op} (node {e.nid}) at {float(e.t * dt_ns):g} ns"
        out.append(f'<g><title>{html.escape(tip)}</title>'
                   f'<rect x="{x:.1f}" y="{y + 6}" width="6" height="14" fill="{colour}"/></g>')
    out.append(f'<text x="{PAD}" y="{h - 2}" font-size="10">0</text>'
               f'<text x="{PAD + W - 60}" y="{h - 2}" font-size="10">'
               f'{float(tmax * dt_ns):g} ns</text></svg>')
    return "\n".join(out)


def render_html(v: Verdict, dt_ns: Fraction) -> str:
    colour = {"PROVED": "#1e8449", "PROVED-UNDER": "#b9770e", "REFUTED": "#c0392b",
              "UNKNOWN": "#555"}[v.verdict]
    rows = []
    for r in v.results:
        loc = v.locs.get(r.obl.nid)
        where = (f"{loc.file}:{loc.line}".replace("\\", "/") if loc and loc.line
                 else f"node {r.obl.nid}")
        m = "" if r.res.margin is None else f"{float(r.res.margin * dt_ns):g} ns"
        rows.append(f"<tr><td>{r.obl.code}</td><td>{html.escape(where)}</td>"
                    f"<td>{r.res.kind}</td><td>{r.res.tier if r.res.tier is not None else ''}</td>"
                    f"<td>{m}</td><td>{html.escape(r.res.reason or r.obl.message)}</td></tr>")
    ass = "".join(f"<li>{html.escape(a.key)}: {a.prov.cls.name.lower()}, "
                  f"{html.escape(a.prov.source)}</li>" for a in v.assumptions)
    svgs = "\n".join(svg_timeline(lbl, run, dt_ns) for lbl, run in v.traces)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>qtiming report: {v.verdict}</title>
<style>body{{font-family:system-ui,sans-serif;margin:1.5rem;max-width:60rem}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccc;padding:.25rem .5rem;
text-align:left;font-size:.9rem}}</style></head><body>
<h1 style="color:{colour}">{v.verdict}</h1>
<p>contract <b>{html.escape(v.contract)}</b>, policy {html.escape(v.policy)},
sha256 {v.contract_sha256[:12]}</p>
{"".join(f"<p>why: {html.escape(x)}</p>" for x in v.reasons)}
<h2>Assumptions</h2><ul>{ass or "<li>none</li>"}</ul>
<h2>Obligations</h2>
<table><tr><th>code</th><th>where</th><th>result</th><th>tier</th><th>margin</th><th>note</th></tr>
{"".join(rows)}</table>
<h2>Timeline</h2>{svgs or "<p>no trace</p>"}
<p><small>Not checked by this build: {html.escape(", ".join(v.not_checked))}</small></p>
</body></html>
"""
