"""Executing each tutorial notebook is the test: its in-cell asserts must pass."""
from pathlib import Path

import pytest

pytest.importorskip("nbclient")
pytest.importorskip("qiskit")
pytest.importorskip("z3")

ROOT = Path(__file__).resolve().parents[2]
NBS = sorted((ROOT / "tutorials").glob("[0-9][0-9]-*/*.ipynb"))


@pytest.mark.parametrize("nb", NBS, ids=lambda p: p.parent.name)
def test_notebook_executes(nb: Path) -> None:
    import sys

    sys.path.insert(0, str(ROOT / "tutorials"))
    import build

    build.execute(nb)
