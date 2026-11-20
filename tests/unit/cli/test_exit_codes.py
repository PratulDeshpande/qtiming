"""User-facing failure modes found while documenting 0.1.0: a missing extra and internal errors."""

from __future__ import annotations

import argparse
import sys

import pytest

from qtiming.cli.main import _guard
from qtiming.core.errors import QtError


def test_internal_errors_exit_4_not_2() -> None:
    """I-* codes (for example I-REPLAY-MISMATCH) are internal errors: exit 4, as documented."""

    @_guard
    def boom(args: argparse.Namespace) -> int:
        raise QtError("I-REPLAY-MISMATCH", "graph and executor disagree")

    assert boom(argparse.Namespace()) == 4


def test_usage_errors_still_exit_2() -> None:
    @_guard
    def bad(args: argparse.Namespace) -> int:
        raise QtError("E-CLI-PROGRAM", "no program found")

    assert bad(argparse.Namespace()) == 2


def test_reading_qasm_without_the_extra_names_the_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    """A base install has no openqasm3: say which extra to install instead of crashing."""
    for name in [m for m in sys.modules if m == "openqasm3" or m.startswith("openqasm3.")
                 or m == "qtiming.frontend.qasm3_fe"]:
        monkeypatch.delitem(sys.modules, name)
    monkeypatch.setitem(sys.modules, "openqasm3", None)  # `import openqasm3` now raises ImportError
    from qtiming.frontend import from_qasm3

    with pytest.raises(QtError) as e:
        from_qasm3("OPENQASM 3.0;")
    assert e.value.code == "E-FE-MISSING-EXTRA"
    assert "qtiming[qiskit]" in (e.value.hint or "")
