"""Executing each tutorial notebook is the test: its in-cell asserts must pass."""
from pathlib import Path

import pytest

pytest.importorskip("nbclient")
pytest.importorskip("qiskit")
pytest.importorskip("z3")

ROOT = Path(__file__).resolve().parents[2]
NBS = sorted((ROOT / "tutorials").glob("[0-9][0-9]-*/*.ipynb"))


def test_hide_markers_drop_code_from_the_page() -> None:
    import sys

    import nbformat

    sys.path.insert(0, str(ROOT / "tutorials"))
    import build

    out = nbformat.v4.new_output("stream", text="SHOWN-OUTPUT\n")
    nb = nbformat.v4.new_notebook(cells=[
        nbformat.v4.new_code_cell("# hide\nSETUP_CODE = 1"),
        nbformat.v4.new_code_cell("# hide-input\nDRAWING_CODE = 1", outputs=[out]),
        nbformat.v4.new_code_cell("VISIBLE_CODE = 1"),
    ])
    build.tag_hidden(nb)
    body, _ = build.exporter().from_notebook_node(nb)
    assert "SETUP_CODE" not in body and "DRAWING_CODE" not in body
    assert "SHOWN-OUTPUT" in body and "VISIBLE_CODE" in body


@pytest.mark.parametrize("nb", NBS, ids=lambda p: p.parent.name)
def test_notebook_executes(nb: Path) -> None:
    import sys

    sys.path.insert(0, str(ROOT / "tutorials"))
    import build

    build.execute(nb)
