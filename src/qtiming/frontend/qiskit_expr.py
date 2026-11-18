"""Qiskit conditions / `expr.Expr` trees -> core Expr (requires qiskit).

Only operators the core evaluator understands are accepted; anything else is refused with
E-FE-EXPR-UNSUPPORTED instead of being guessed. Operands are bit PROPOSITIONS (occurrence keys),
resolved through `ExprCtx` by the walker, so the result never mentions a Clbit object.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from qiskit.circuit import ClassicalRegister, Clbit
from qiskit.circuit.classical import expr, types

from qtiming.core.errors import QtError
from qtiming.core.labels import EBin, EBit, EConst, EUn, Expr

from ._shared import reg_value as _reg_value


@dataclass(frozen=True, slots=True)
class ExprCtx:
    bit: Callable[[Clbit], str]  # clbit -> proposition of its latest writer
    reg: Callable[[ClassicalRegister], list[str]]  # register -> propositions, LSB first


_UN = {"LOGIC_NOT": "not", "BIT_NOT": "bit_not"}
_BIN = {
    "BIT_AND": "bit_and", "BIT_OR": "bit_or", "BIT_XOR": "bit_xor",
    "LOGIC_AND": "and", "LOGIC_OR": "or",
    "EQUAL": "eq", "NOT_EQUAL": "ne", "LESS": "lt", "LESS_EQUAL": "le",
    "GREATER": "gt", "GREATER_EQUAL": "ge", "ADD": "add", "SUB": "sub", "MUL": "mul",
}


def _unsupported(what: str) -> QtError:
    return QtError("E-FE-EXPR-UNSUPPORTED", f"{what} is not supported in conditions",
                   hint="rewrite the condition with bit/register comparisons, parity or and/or/not")


def to_expr(cond: Any, ctx: ExprCtx) -> Expr:
    """A `(Clbit|ClassicalRegister, int)` tuple or an `expr.Expr`."""
    if isinstance(cond, tuple):
        target, val = cond
        if isinstance(target, ClassicalRegister):
            props = ctx.reg(target)
            return EBin("eq", _reg_value(props), EConst(int(val), len(props)))
        bit: Expr = EBit(ctx.bit(target))
        if val == 1:
            return bit
        if val == 0:
            return EUn("not", bit)
        raise _unsupported(f"comparing a single bit with {val}")
    return to_value(cond, ctx)


def to_value(e: Any, ctx: ExprCtx) -> Expr:
    """A switch target or condition operand: Clbit, ClassicalRegister or expr.Expr."""
    if isinstance(e, Clbit):
        return EBit(ctx.bit(e))
    if isinstance(e, ClassicalRegister):
        return _reg_value(ctx.reg(e))
    if isinstance(e, expr.Value):
        t = e.type
        return EConst(int(e.value), 1 if isinstance(t, types.Bool) else t.width)
    if isinstance(e, expr.Var):
        if isinstance(e.var, (Clbit, ClassicalRegister)):
            return to_value(e.var, ctx)
        raise _unsupported("standalone real-time variables")
    if isinstance(e, expr.Unary):
        name = e.op.name
        if name == "NEGATE":
            return EBin("sub", EConst(0, 1), to_value(e.operand, ctx))
        if name in _UN:
            return EUn(_UN[name], to_value(e.operand, ctx))
        raise _unsupported(f"operator {name}")
    if isinstance(e, expr.Binary):
        name = e.op.name
        if name not in _BIN:
            raise _unsupported(f"operator {name}")
        return EBin(_BIN[name], to_value(e.left, ctx), to_value(e.right, ctx))
    if isinstance(e, expr.Cast):
        inner = to_value(e.operand, ctx)
        if isinstance(e.type, types.Bool) and isinstance(e.operand.type, types.Uint):
            return EBin("ne", inner, EConst(0, e.operand.type.width))
        return inner
    raise _unsupported(type(e).__name__)
