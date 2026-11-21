"""Helpers shared by the tutorial notebooks. Run notebooks with the repo venv."""
from __future__ import annotations

import html as _html
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAMILIES = ROOT / "benchmarks" / "families"


def run(*args: str | Path, show: bool = True) -> tuple[int, str]:
    """Run `qtiming <args>`; print the output and exit code; return (code, stdout)."""
    p = subprocess.run(
        [sys.executable, "-m", "qtiming.cli.main", *map(str, args)],
        capture_output=True, text=True, cwd=ROOT,
    )
    # repo-relative POSIX paths keep the rendered pages machine-independent
    out = (p.stdout + p.stderr).replace(str(ROOT) + "\\", "").replace("\\", "/")
    if show:
        # one write: nbclient can split separate prints into extra stream messages
        print(out.rstrip() + f"\n[exit {p.returncode}]")
    return p.returncode, out


def source(path: str | Path) -> None:
    """Print a program's source, relative to the repo root or the families folder."""
    p = Path(path)
    if not p.is_absolute():
        p = FAMILIES / p if (FAMILIES / p).exists() else ROOT / p
    print(p.read_text(encoding="utf-8").rstrip())


def report_svg(program: str | Path, contract: str, *assume: str) -> None:
    """Show the SVG timeline of a `check --format html` report inline."""
    from IPython.display import HTML, display

    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "r.html"
        args = ["check", program, "--contract", contract, "--format", "html", "--out", out]
        for a in assume:
            args += ["--assume", a]
        run(*args, show=False)
        text = out.read_text(encoding="utf-8") if out.exists() else ""
    i, j = text.find("<svg"), text.rfind("</svg>")
    display(HTML(text[i : j + 6] if i >= 0 and j >= 0 else "<em>no timeline in this report</em>"))


def dot(text: str, height: int = 420) -> None:
    """Render DOT client-side with viz.js (no Graphviz install needed)."""
    from IPython.display import HTML, display

    src = _html.escape(text)
    display(HTML(
        f'<div class="qt-dot" style="min-height:{height}px"><pre class="qt-dot-src" hidden>{src}</pre>'
        '<script src="https://cdn.jsdelivr.net/npm/@viz-js/viz@3.2.4/lib/viz-standalone.js"></script>'
        "<script>(async()=>{for(const e of document.querySelectorAll('.qt-dot-src:not([data-done])')){"
        "e.dataset.done=1;const v=await Viz.instance();e.parentElement.appendChild("
        "v.renderSVGElement(e.textContent));}})()</script></div>"
    ))
