"""Exhaustive oracle: every outcome assignment times every vertex of the latency box.

Discovery is lazy: run with a strict `Fixed`; each time the run asks for a value it was not given,
branch on it (bit: 0/1, latency: lo/hi). Exact ground truth for small programs (hypothesis H2).
"""

from __future__ import annotations

from collections.abc import Iterator
from fractions import Fraction

from qtiming.contract.model import Contract
from qtiming.core.ast import Stmt
from qtiming.core.errors import QtError

from .engine import ExecResult, execute
from .oracle import Fixed, NeedChoice


def exhaustive(
    prog: Stmt, contract: Contract, *, k_max: int = 12, K_max: int = 10
) -> Iterator[tuple[dict[str, int], dict[str, Fraction], ExecResult]]:
    stack: list[tuple[dict[str, int], dict[str, Fraction]]] = [({}, {})]
    while stack:
        omega, theta = stack.pop()
        try:
            res = execute(prog, contract, Fixed(omega, theta, strict=True))
        except NeedChoice as need:
            if need.kind == "bit":
                if len(omega) >= k_max:
                    raise QtError("E-EXEC-EXHAUSTIVE", f"more than {k_max} outcome bits") from None
                stack += [({**omega, need.key: 0}, theta), ({**omega, need.key: 1}, theta)]
            else:
                iv = need.iv
                assert iv is not None
                if iv.hi is None:
                    raise QtError("E-EXEC-UNBOUNDED", f"{need.key}: unbounded latency") from None
                if len(theta) >= K_max:
                    raise QtError("E-EXEC-EXHAUSTIVE", f"more than {K_max} latencies") from None
                for v in sorted({iv.lo, iv.hi}):
                    stack.append((omega, {**theta, need.key: Fraction(v)}))
            continue
        yield omega, theta, res
