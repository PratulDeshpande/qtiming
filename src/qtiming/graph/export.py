"""Graphviz DOT export of an LTEG (`qtiming explain --graph dot`)."""

from __future__ import annotations

from qtiming.core.labels import Label

from .lteg import LTEG, LatVar


def _lab(label: Label) -> str:
    return " & ".join(("" if x.pos else "!") + x.prop for x in sorted(label, key=lambda x: x.prop))


def to_dot(g: LTEG) -> str:
    out = ["digraph lteg {", "  rankdir=LR; node [shape=box, fontsize=10];"]
    for n in g.nodes:
        lab = f"{n.kind}/{n.tag}@{n.nid}" + (f"\\n[{_lab(n.label)}]" if n.label else "")
        out.append(f'  n{n.id} [label="{lab}"];')
    for e in g.edges:
        w = f"{e.w.key} in [{e.w.lo}, {e.w.hi}]" if isinstance(e.w, LatVar) else str(e.w)
        lab = w + (f" if {_lab(e.label)}" if e.label else "")
        style = ", style=dashed" if isinstance(e.w, LatVar) else ""
        out.append(f'  n{e.src} -> n{e.dst} [label="{lab}", fontsize=9{style}];')
    out.append("}")
    return "\n".join(out)
