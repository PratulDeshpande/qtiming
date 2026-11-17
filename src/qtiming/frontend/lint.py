"""Static per-backend front-end lint (Section 6.6). Needs no solver.

Implemented: the IBM structural rules. Deferred (need contract budgets / Q1ASM docs):
E-LINT-IBM-BROADCAST, E-LINT-IBM-INSTR-BUDGET, E-LINT-Q1-COND, E-LINT-QUA-STRICT.
"""

from __future__ import annotations

from qtiming.core.ast import (
    Box,
    For,
    If,
    Measure,
    Node,
    Reset,
    Seq,
    Stmt,
    Switch,
    While,
    Within,
)
from qtiming.core.errors import QtError
from qtiming.core.labels import EBin, EBit, EUn, Expr

_ARITH = {"add", "sub", "mul", "div", "mod", "shl", "shr"}
_MAX_BITS = 32


def _err(code: str, msg: str, node: Node, hint: str, sev: str = "error") -> QtError:
    return QtError(code, msg, loc=node.loc, hint=hint, severity=sev)  # type: ignore[arg-type]


def _ops_and_bits(e: Expr, ops: set[str], bits: set[str]) -> None:
    if isinstance(e, EBit):
        bits.add(e.prop)
    elif isinstance(e, EUn):
        ops.add(e.op)
        _ops_and_bits(e.a, ops, bits)
    elif isinstance(e, EBin):
        ops.add(e.op)
        _ops_and_bits(e.a, ops, bits)
        _ops_and_bits(e.b, ops, bits)


def _is_elseif(s: Stmt | None) -> bool:
    if isinstance(s, If):
        return True
    return isinstance(s, Seq) and len(s.stmts) == 1 and isinstance(s.stmts[0], If)


def _unwrap_if(s: Stmt) -> If:
    if isinstance(s, Seq):
        s = s.stmts[0]
    assert isinstance(s, If)
    return s


def lint(body: Stmt, personality: str) -> list[QtError]:
    if personality != "ibm":
        return []
    out: list[QtError] = []
    _walk(body, False, out)
    return out


def _walk(s: Stmt | None, in_if: bool, out: list[QtError]) -> None:
    if s is None:
        return
    if isinstance(s, Seq):
        for c in s.stmts:
            _walk(c, in_if, out)
    elif isinstance(s, If):
        if in_if:
            out.append(_err("E-LINT-IBM-NESTED-IF", "nested if", s,
                            "IBM supports a single, non-nested if/else per block"))
        ops: set[str] = set()
        bits: set[str] = set()
        _ops_and_bits(s.cond, ops, bits)
        if ops & _ARITH:
            out.append(_err("E-LINT-IBM-ARITH-COND", "arithmetic or shift in a condition", s,
                            "use bit/register equality or parity conditions only"))
        if len(bits) > _MAX_BITS:
            out.append(_err("E-LINT-IBM-OPERAND-WIDTH",
                            f"condition reads {len(bits)} bits (limit {_MAX_BITS})", s,
                            "split the condition or reduce the register width"))
        _walk(s.then_, True, out)
        if _is_elseif(s.else_):
            assert s.else_ is not None
            out.append(_err("E-LINT-IBM-ELSEIF", "else-if chain", s.else_,
                            "IBM supports only if and else; restructure the chain"))
            _walk(_unwrap_if(s.else_), in_if, out)
        else:
            _walk(s.else_, True, out)
    elif isinstance(s, (Measure, Reset)):
        if in_if:
            out.append(_err("E-LINT-IBM-MEAS-IN-IF", "measure or reset inside a conditional", s,
                            "move the measurement/reset outside the if block"))
    elif isinstance(s, (For, While, Switch)):
        out.append(_err("E-LINT-IBM-LOOP", f"{type(s).__name__.lower()} control flow", s,
                        "IBM supports neither for, while nor switch on this path"))
        if isinstance(s, For):
            _walk(s.body, in_if, out)
        elif isinstance(s, While):
            _walk(s.body, in_if, out)
            _walk(s.exhaust, in_if, out)
        else:
            for _, c in s.cases:
                _walk(c, in_if, out)
            _walk(s.default, in_if, out)
    elif isinstance(s, Box):
        out.append(_err("E-LINT-IBM-BOX", "box present", s,
                        "strip timing annotations before submission (StripTimingAnnotations)",
                        "warning"))
        _walk(s.body, in_if, out)
    elif isinstance(s, Within):
        _walk(s.body, in_if, out)
