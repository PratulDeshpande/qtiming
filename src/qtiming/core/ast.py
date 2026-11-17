"""TQ: the timed-OpenQASM-3 core syntax tree. Frozen, hashable, stdlib only."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Union

from .labels import Expr


@dataclass(frozen=True, slots=True)
class SourceLoc:
    file: str
    line: int = 0
    col: int = 0
    instr: int | None = None  # Qiskit instruction index when no text position exists


@dataclass(frozen=True, slots=True)
class BitRef:
    reg: str  # register NAME, not a Clbit object (finding F14)
    idx: int


PolicyKind = Literal["eq", "sync", "exp"]


@dataclass(frozen=True, slots=True)
class Policy:
    kind: PolicyKind
    delta: int | None = None  # SYNC spread bound (dt, rounded DOWN by the loader)
    gap: int | None = None  # SYNC per-resource gap bound G (dt)


@dataclass(frozen=True, slots=True, kw_only=True)
class Node:
    nid: int
    loc: SourceLoc
    origin_nid: int | None = None  # set by elaboration for synthesised nodes


@dataclass(frozen=True, slots=True, kw_only=True)
class Gate(Node):
    name: str
    qubits: tuple[int, ...]
    dur: int


@dataclass(frozen=True, slots=True, kw_only=True)
class Delay(Node):
    qubits: tuple[int, ...]
    dur: int
    declared: bool = True  # declared delays are intentional idle (O4a exempt)


@dataclass(frozen=True, slots=True, kw_only=True)
class Barrier(Node):
    qubits: tuple[int, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class Measure(Node):
    qubit: int
    cbit: BitRef
    variant: Literal["std", "mid"] = "std"
    tier: str = "default"


@dataclass(frozen=True, slots=True, kw_only=True)
class Reset(Node):
    qubit: int


@dataclass(frozen=True, slots=True, kw_only=True)
class Assign(Node):
    var: str
    expr: Expr


@dataclass(frozen=True, slots=True, kw_only=True)
class Seq(Node):
    stmts: tuple[Stmt, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class Box(Node):
    dur: int | None  # None: duration is the body's (stretch already resolved by the front end)
    body: Stmt
    annotations: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class If(Node):
    cond: Expr
    then_: Stmt
    else_: Stmt | None = None
    policy: Policy | None = None  # None = contract default until elaboration


@dataclass(frozen=True, slots=True, kw_only=True)
class Switch(Node):
    target: Expr
    cases: tuple[tuple[int, Stmt], ...]
    default: Stmt | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class For(Node):
    var: str
    n: int  # static
    body: Stmt


@dataclass(frozen=True, slots=True, kw_only=True)
class While(Node):
    cond: Expr
    body: Stmt
    cap: int  # mandatory
    exhaust: Stmt  # mandatory handler
    policy: Policy | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Call(Node):
    fn: str
    args: tuple[str, ...]
    latency_key: str
    blocking: bool = True


@dataclass(frozen=True, slots=True, kw_only=True)
class Within(Node):
    deadline: int  # dt
    anchor: BitRef
    body: Stmt


Stmt = Union[  # noqa: UP007
    Gate, Delay, Barrier, Measure, Reset, Assign, Seq, Box, If, Switch, For, While, Call, Within
]
