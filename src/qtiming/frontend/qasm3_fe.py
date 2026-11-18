"""OpenQASM 3 text -> TQ via the `openqasm3` parser: the fallback for programs Qiskit cannot import.

Mirrors `qiskit_fe` exactly on the shared fragment (same node-id order, same timing semantics
from `_shared`), so the two front ends yield equal ASTs modulo source locations. Gate durations
come only from the contract. Anything outside the fragment is refused with E-FE-UNSUPPORTED and
the line, never guessed.

Not supported yet (refused): register broadcast in gate operands, physical qubits (`$n`), gate
modifiers and gate durations, box durations and stretch, classical declarations with an
initialiser, assignments, subroutines, `defcal`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from openqasm3 import ast
from openqasm3.parser import QASM3ParsingError, parse

from qtiming.core.ast import (
    Barrier,
    BitRef,
    Box,
    Delay,
    For,
    Gate,
    If,
    Measure,
    Reset,
    Seq,
    SourceLoc,
    Stmt,
    Switch,
    While,
)
from qtiming.core.errors import QtError
from qtiming.core.ids import bit_prop
from qtiming.core.labels import EBin, EBit, EConst, EUn, Expr

from ._shared import (
    Env,
    Scope,
    State,
    box_scope,
    delay_dt,
    gate_dur,
    merge,
    read_bit,
    reg_value,
    while_cap,
)
from .program import ContractView, Program

TIMING_KINDS = frozenset(
    {"policy", "within", "cap", "pmin", "declared_idle", "call", "hard", "cut"}
)
_BIN = {
    "&": "bit_and", "|": "bit_or", "^": "bit_xor", "&&": "and", "||": "or",
    "==": "eq", "!=": "ne", "<": "lt", "<=": "le", ">": "gt", ">=": "ge",
    "+": "add", "-": "sub", "*": "mul",
}
_BOOL_OPS = {"and", "or", "eq", "ne", "lt", "le", "gt", "ge"}
_SKIP = (ast.Include, ast.QuantumGateDefinition)


def from_qasm3(text: str, *, filename: str = "<string>",
               contract: ContractView | None = None) -> Program:
    try:
        tree = parse(text)
    except QASM3ParsingError as e:
        raise QtError("E-FE-PARSE", f"OpenQASM 3 parse error: {e}",
                      loc=SourceLoc(filename)) from None
    w = _Walker(State(contract, file=filename))
    body = w.block(tree.statements, {}, Scope())
    return Program(body=body, qubits=tuple(range(w.nq)),
                   bits=tuple(BitRef(r, i) for r, n in w.cregs.items() for i in range(n)),
                   vars=(), notes=tuple(w.st.notes))


@dataclass
class _Walker:
    st: State
    qregs: dict[str, tuple[int, int]] = field(default_factory=dict)  # name -> (offset, size)
    cregs: dict[str, int] = field(default_factory=dict)  # name -> size
    nq: int = 0

    # ---- helpers -------------------------------------------------------------------------
    def loc(self, node: Any) -> SourceLoc:
        sp = node.span
        return SourceLoc(self.st.file) if sp is None else SourceLoc(
            self.st.file, sp.start_line, sp.start_column)

    def unsupported(self, what: str, node: Any) -> QtError:
        return QtError("E-FE-UNSUPPORTED", f"{what} is outside the supported OpenQASM 3 fragment",
                       loc=self.loc(node), hint="see qtiming.frontend.qasm3_fe for the fragment")

    def _index(self, node: Any) -> tuple[str, int | None]:
        """(name, index) of `x` or `x[i]`."""
        if isinstance(node, ast.Identifier):
            return node.name, None
        if isinstance(node, ast.IndexedIdentifier):
            idx = node.indices
            if len(idx) == 1 and isinstance(idx[0], list) and len(idx[0]) == 1 \
                    and isinstance(idx[0][0], ast.IntegerLiteral):
                return node.name.name, idx[0][0].value
        if isinstance(node, ast.IndexExpression) and isinstance(node.collection, ast.Identifier):
            idx = node.index
            if isinstance(idx, list) and len(idx) == 1 and isinstance(idx[0], ast.IntegerLiteral):
                return node.collection.name, idx[0].value
        raise self.unsupported("this operand form", node)

    def qubits(self, node: Any) -> list[int]:
        name, i = self._index(node)
        if name not in self.qregs:
            raise self.unsupported(f"qubit operand {name!r} (undeclared or physical)", node)
        off, size = self.qregs[name]
        if i is None:
            return list(range(off, off + size))
        if not 0 <= i < size:
            raise QtError("E-FE-INDEX", f"{name}[{i}] out of range", loc=self.loc(node))
        return [off + i]

    def qubit(self, node: Any) -> int:
        qs = self.qubits(node)
        if len(qs) != 1:
            raise self.unsupported("register broadcast", node)
        return qs[0]

    def bit(self, node: Any) -> BitRef:
        name, i = self._index(node)
        if name not in self.cregs:
            raise QtError("E-FE-ANNOT-BIT", f"{name!r} is not a declared bit register",
                          loc=self.loc(node))
        if i is None:
            if self.cregs[name] != 1:
                raise self.unsupported("measuring into a whole register", node)
            i = 0
        if not 0 <= i < self.cregs[name]:
            raise QtError("E-FE-INDEX", f"{name}[{i}] out of range", loc=self.loc(node))
        return BitRef(name, i)

    # ---- expressions: (Expr, width); a bare literal has width None until it meets a sibling --
    def expr(self, e: Any, env: Env) -> tuple[Expr, int | None]:
        loc = self.loc(e)
        if isinstance(e, ast.BooleanLiteral):
            return EConst(int(e.value), 1), 1
        if isinstance(e, ast.IntegerLiteral):
            return EConst(e.value, max(1, e.value.bit_length())), None
        if isinstance(e, ast.Identifier) and e.name in self.cregs:
            n = self.cregs[e.name]
            return reg_value([read_bit(BitRef(e.name, i), env, loc) for i in range(n)]), n
        if isinstance(e, ast.IndexExpression):
            return EBit(read_bit(self.bit(e), env, loc)), 1
        if isinstance(e, ast.UnaryExpression):
            a, w = self.expr(e.expression, env)
            op = e.op.name
            if op == "!":
                return EUn("not", a), 1
            if op == "~":
                return EUn("bit_not", a), w
            return EBin("sub", EConst(0, 1), a), w
        if isinstance(e, ast.BinaryExpression) and e.op.name in _BIN:
            (a, wa), (b, wb) = self.expr(e.lhs, env), self.expr(e.rhs, env)
            a, b = _fit(a, wb), _fit(b, wa)
            op = _BIN[e.op.name]
            return EBin(op, a, b), 1 if op in _BOOL_OPS else max(wa or 1, wb or 1)
        raise QtError("E-FE-EXPR-UNSUPPORTED", f"{type(e).__name__} is not supported in "
                      "conditions", loc=loc,
                      hint="rewrite the condition with bit/register comparisons, parity or "
                      "and/or/not")

    def cond(self, e: Any, env: Env) -> Expr:
        x, w = self.expr(e, env)
        return EBin("ne", x, EConst(0, w)) if w and w > 1 else x

    # ---- statements ------------------------------------------------------------------------
    def block(self, stmts: list[Any], env: Env, scope: Scope) -> Seq:
        nid = self.st.ids.next()
        out: list[Stmt] = []
        for x in stmts:
            if not isinstance(x, ast.Box) and any(
                    a.keyword.startswith("timing.") for a in getattr(x, "annotations", ())):
                raise QtError("E-FE-ANNOT-PLACEMENT", "timing.* annotations attach only to a box",
                              loc=self.loc(x), hint="wrap the statement in `box { ... }`")
            if isinstance(x, ast.DelayInstruction):  # one Delay per qubit, as Qiskit has it
                out.extend(self._delays(x))
            elif (s := self.stmt(x, env, scope)) is not None:
                out.append(s)
        return Seq(nid=nid, loc=SourceLoc(self.st.file), stmts=tuple(out))

    def _delays(self, s: Any) -> list[Stmt]:
        d, loc = s.duration, self.loc(s)
        if not isinstance(d, ast.DurationLiteral):
            raise self.unsupported("a non-literal delay duration", s)
        dur = delay_dt(d.value, d.unit.name, self.st, loc)
        return [Delay(nid=self.st.ids.next(), loc=loc, qubits=(q,), dur=dur)
                for q in self._all(s.qubits)]

    def _body(self, b: Any) -> list[Any]:
        return b.statements if isinstance(b, ast.CompoundStatement) else list(b)

    def stmt(self, s: Any, env: Env, scope: Scope) -> Stmt | None:
        loc, st = self.loc(s), self.st
        if isinstance(s, _SKIP):
            return None
        if isinstance(s, ast.QubitDeclaration):
            size = 1 if s.size is None else _int(s.size, self, s)
            self.qregs[s.qubit.name] = (self.nq, size)
            self.nq += size
            return None
        if isinstance(s, ast.ClassicalDeclaration):
            if not isinstance(s.type, ast.BitType) or s.init_expression is not None:
                raise self.unsupported("a classical declaration other than `bit[n] name;`", s)
            self.cregs[s.identifier.name] = 1 if s.type.size is None else _int(s.type.size,
                                                                                  self, s)
            return None
        if isinstance(s, ast.QuantumGate):
            if s.modifiers or s.duration is not None:
                raise self.unsupported("gate modifiers or durations", s)
            name = s.name.name
            return Gate(nid=st.ids.next(), loc=loc, name=name,
                        qubits=tuple(self.qubit(q) for q in s.qubits), dur=gate_dur(name, st))
        if isinstance(s, ast.QuantumMeasurementStatement):
            if s.target is None or not isinstance(s.measure, ast.QuantumMeasurement):
                raise self.unsupported("measure without a target bit", s)
            q, bit = self.qubit(s.measure.qubit), self.bit(s.target)
            nid = st.ids.next()
            env[bit] = bit_prop(bit.reg, bit.idx, nid)
            return Measure(nid=nid, loc=loc, qubit=q, cbit=bit)
        if isinstance(s, ast.QuantumReset):
            return Reset(nid=st.ids.next(), loc=loc, qubit=self.qubit(s.qubits))
        if isinstance(s, ast.QuantumBarrier):
            return Barrier(nid=st.ids.next(), loc=loc, qubits=self._all(s.qubits))
        if isinstance(s, ast.BranchingStatement):
            return self._if(s, loc, env, scope)
        if isinstance(s, ast.WhileLoop):
            cap = while_cap(scope, loc)
            nid = st.ids.next()
            cond = self.cond(s.while_condition, env)
            e = dict(env)
            body = self.block(self._body(s.block), e, scope)
            merge(env, [e, dict(env)])  # the loop may run zero times
            exhaust = Seq(nid=st.ids.next(), loc=loc, stmts=())
            return While(nid=nid, loc=loc, cond=cond, body=body, cap=cap, exhaust=exhaust,
                         policy=scope.policy)
        if isinstance(s, ast.ForInLoop):
            nid = st.ids.next()
            n = self._count(s.set_declaration, s)
            e = dict(env)
            body = self.block(self._body(s.block), e, scope)
            merge(env, [e, dict(env)])
            return For(nid=nid, loc=loc, var=s.identifier.name, n=n, body=body)
        if isinstance(s, ast.SwitchStatement):
            return self._switch(s, loc, env, scope)
        if isinstance(s, ast.Box):
            if s.duration is not None:
                raise QtError("E-FE-UNSUPPORTED", "box durations are not implemented yet",
                              loc=loc)
            nid = st.ids.next()
            anns = tuple(sorted(self._anns(s)))
            inner = box_scope(anns, scope, self._bits(), st, loc)
            body = self.block(self._body(s.body), env, inner)  # a box runs once: share env
            return Box(nid=nid, loc=loc, dur=None, body=body, annotations=anns)
        raise self.unsupported(type(s).__name__, s)

    def _all(self, operands: list[Any]) -> tuple[int, ...]:
        if not operands:
            return tuple(range(self.nq))
        return tuple(q for op in operands for q in self.qubits(op))

    def _bits(self) -> set[BitRef]:
        return {BitRef(r, i) for r, n in self.cregs.items() for i in range(n)}

    def _anns(self, s: Any) -> list[tuple[str, str]]:
        out = []
        for a in s.annotations:
            ns, _, kind = a.keyword.partition(".")
            if ns != "timing":
                continue  # other namespaces pass through untouched
            if kind not in TIMING_KINDS:
                raise QtError("E-FE-ANNOT-PAYLOAD", f"unknown timing annotation {a.keyword!r}",
                              loc=self.loc(a))
            out.append((kind, (a.command or "").strip()))
        return out

    def _if(self, s: Any, loc: SourceLoc, env: Env, scope: Scope) -> If:
        nid = self.st.ids.next()
        cond = self.cond(s.condition, env)
        e1 = dict(env)
        then_ = self.block(s.if_block, e1, scope)
        e2 = dict(env)
        # an empty else is indistinguishable from none in the parser's AST; both mean no else
        else_ = self.block(s.else_block, e2, scope) if s.else_block else None
        merge(env, [e1, e2])
        return If(nid=nid, loc=loc, cond=cond, then_=then_, else_=else_, policy=scope.policy)

    def _switch(self, s: Any, loc: SourceLoc, env: Env, scope: Scope) -> Switch:
        nid = self.st.ids.next()
        target = self.expr(s.target, env)[0]
        cases: list[tuple[int, Stmt]] = []
        envs: list[Env] = []
        for values, blk in s.cases:
            e = dict(env)
            seq = self.block(self._body(blk), e, scope)
            envs.append(e)
            cases.extend((_int(v, self, s), seq) for v in values)
        default = None
        if s.default is not None:
            e = dict(env)
            default = self.block(self._body(s.default), e, scope)
            envs.append(e)
        else:
            envs.append(dict(env))
        merge(env, envs)
        return Switch(nid=nid, loc=loc, target=target, cases=tuple(cases), default=default)

    def _count(self, sd: Any, s: Any) -> int:
        if isinstance(sd, ast.DiscreteSet):
            return len(sd.values)
        if isinstance(sd, ast.RangeDefinition) and sd.start is not None and sd.end is not None:
            a, b = _int(sd.start, self, s), _int(sd.end, self, s)
            step = 1 if sd.step is None else _int(sd.step, self, s)
            return len(range(a, b + (1 if step > 0 else -1), step))  # QASM3 ranges are inclusive
        raise self.unsupported("this loop index set", s)


def _int(e: Any, w: _Walker, s: Any) -> int:
    if isinstance(e, ast.IntegerLiteral):
        return int(e.value)
    if isinstance(e, ast.UnaryExpression) and e.op.name == "-" \
            and isinstance(e.expression, ast.IntegerLiteral):
        return -int(e.expression.value)
    raise w.unsupported("a non-literal integer", s)


def _fit(x: Expr, width: int | None) -> Expr:
    """Give an untyped integer literal the width of the operand it meets (Qiskit does)."""
    if isinstance(x, EConst) and width is not None and x.value.bit_length() <= width:
        return EConst(x.value, width)
    return x
