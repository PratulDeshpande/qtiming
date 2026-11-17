"""Propositions, labels (conjunctions of literals) and the classical expression language."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Union

from .errors import QtError

Prop = str  # "c[0]@m17#i3" (bit) or "cond@n42#i3" (derived)


@dataclass(frozen=True, slots=True)
class Lit:
    prop: Prop
    pos: bool = True


Label = frozenset[Lit]  # conjunction of literals; empty = always true
TOP: Label = frozenset()


def consistent(a: Label, b: Label) -> bool:
    return not any(Lit(lit.prop, not lit.pos) in b for lit in a)


def conj(a: Label, b: Label) -> Label | None:
    return None if not consistent(a, b) else a | b


def implies(a: Label, b: Label) -> bool:
    """Every literal of b appears in a."""
    return b <= a


@dataclass(frozen=True, slots=True)
class EBit:
    prop: Prop


@dataclass(frozen=True, slots=True)
class EConst:
    value: int
    width: int = 1


@dataclass(frozen=True, slots=True)
class EVar:
    name: str
    width: int


@dataclass(frozen=True, slots=True)
class EUn:
    op: str  # "not", "bit_not"
    a: Expr


@dataclass(frozen=True, slots=True)
class EBin:
    op: str
    a: Expr
    b: Expr


Expr = Union[EBit, EConst, EVar, EUn, EBin]  # noqa: UP007  (runtime alias, py3.10-safe)


@dataclass(frozen=True, slots=True)
class Derived:
    prop: Prop  # "cond@n42#i3"
    expr: Expr  # exact definition over bit propositions / variables
    operands: tuple[Prop, ...]  # bit propositions the expression reads


_BIN: dict[str, Callable[[int, int], int]] = {
    "and": lambda x, y: int(bool(x) and bool(y)),
    "or": lambda x, y: int(bool(x) or bool(y)),
    "xor": lambda x, y: x ^ y,
    "bit_xor": lambda x, y: x ^ y,
    "bit_and": lambda x, y: x & y,
    "bit_or": lambda x, y: x | y,
    "eq": lambda x, y: int(x == y),
    "ne": lambda x, y: int(x != y),
    "lt": lambda x, y: int(x < y),
    "le": lambda x, y: int(x <= y),
    "gt": lambda x, y: int(x > y),
    "ge": lambda x, y: int(x >= y),
    "add": lambda x, y: x + y,
    "sub": lambda x, y: x - y,
    "mul": lambda x, y: x * y,
}


def evaluate(e: Expr, env: Mapping[str, int]) -> int:
    """Exact evaluation over bit/variable values in `env` (the executor's source of truth)."""
    if isinstance(e, EConst):
        return e.value
    if isinstance(e, EBit):
        return _lookup(env, e.prop)
    if isinstance(e, EVar):
        return _lookup(env, e.name)
    if isinstance(e, EUn):
        v = evaluate(e.a, env)
        if e.op == "not":
            return int(not v)
        if e.op == "bit_not":
            return ~v
        raise QtError("E-LABEL-OP", f"unknown unary operator {e.op!r}")
    fn = _BIN.get(e.op)
    if fn is None:
        raise QtError("E-LABEL-OP", f"unknown binary operator {e.op!r}")
    return fn(evaluate(e.a, env), evaluate(e.b, env))


def _lookup(env: Mapping[str, int], key: str) -> int:
    try:
        return env[key]
    except KeyError:
        raise QtError("E-LABEL-UNBOUND", f"no value for {key!r}") from None
