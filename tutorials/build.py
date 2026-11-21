"""Execute every tutorial notebook and render it to Docs/tutorials/NN-*.md.

    python tutorials/build.py [NN ...]      # all notebooks, or just those numbers
In-cell asserts are the tests: a failing assert fails the build.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient
from nbconvert import MarkdownExporter

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "Docs" / "tutorials"


def notebooks(only: list[str] | None = None) -> list[Path]:
    nbs = sorted(HERE.glob("[0-9][0-9]-*/*.ipynb"))
    return [p for p in nbs if not only or p.parent.name[:2] in only]


def execute(path: Path) -> nbformat.NotebookNode:
    nb = nbformat.read(path, as_version=4)
    NotebookClient(nb, timeout=600, kernel_name="python3", resources={"metadata": {"path": str(path.parent)}}).execute()
    return nb


def render(nb: nbformat.NotebookNode, name: str) -> None:
    body, _ = MarkdownExporter().from_notebook_node(nb)
    # Markdown pages must be deterministic: drop raw timing/paths that vary per run.
    body = body.replace(str(HERE.parent), "<repo>").replace("\r\n", "\n")
    body = re.sub(r"\n{3,}", "\n\n", body)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.md").write_text(body.rstrip() + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    for p in notebooks(argv or None):
        render(execute(p), p.parent.name)
        print("built", p.parent.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
