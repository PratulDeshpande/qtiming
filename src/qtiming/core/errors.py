"""Structured errors shared by every stage. Stdlib only."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from .ast import SourceLoc

Severity = Literal["error", "warning", "note"]


class QtError(Exception):
    """A diagnostic with a stable `code` (also the SARIF ruleId).

    Not a frozen dataclass: frozen Exception subclasses break when Python sets
    `__traceback__` / `__context__` on them.
    """

    def __init__(
        self,
        code: str,
        message: str,
        loc: SourceLoc | None = None,
        hint: str | None = None,
        severity: Severity = "error",
    ) -> None:
        super().__init__(code, message)
        self.code = code
        self.message = message
        self.loc = loc
        self.hint = hint
        self.severity = severity

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"
