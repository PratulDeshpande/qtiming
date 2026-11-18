"""Qiskit QuantumCircuit -> TQ (requires qiskit). Read-only: never mutates the circuit.

Walks `circuit.data` in program order, recursing into control-flow blocks and mapping block
qubits/clbits to the outer circuit through the instruction operands (never by position in the
block). Scheduling is the graph builder's job; nothing here keeps per-qubit cursors.
Timing semantics shared with the OpenQASM 3 walker live in `_shared`.

Deferred (refused with E-FE-UNSUPPORTED, never guessed): bits written in only some arms of a
branch/loop and read afterwards (phi merge); `timing.cap` exhaust labels; box durations;
`Var`/`Store`; stretch.
"""

from __future__ import annotations

from typing import Any

from qiskit import QuantumCircuit
from qiskit.circuit import CASE_DEFAULT, Clbit
from qiskit.circuit import Gate as QGate

from qtiming.core.ast import (
    Barrier,
    BitRef,
    Box,
    Delay,
    For,
    Gate,
    If,
    Measure,
    Node,
    Reset,
    Seq,
    SourceLoc,
    Stmt,
    Switch,
    While,
)
from qtiming.core.errors import QtError
from qtiming.core.ids import bit_prop

from ._shared import (
    UNRESOLVED_DUR,
    Env,
    Scope,
    State,
    box_scope,
    delay_dt,
    gate_dur,
    merge,
    read_bit,
    while_cap,
)
from .annotations import timing_annotations
from .program import ContractView, Program
from .qiskit_expr import ExprCtx, to_expr, to_value


def from_circuit(qc: QuantumCircuit, *, contract: ContractView | None = None) -> Program:
    st = State(contract, file=qc.name or "<circuit>")
    cmap = {cb: _bitref(qc, cb) for cb in qc.clbits}
    qmap = {q: i for i, q in enumerate(qc.qubits)}
    body = _block(qc, qmap, cmap, {}, Scope(), st)
    return Program(
        body=body,
        qubits=tuple(range(len(qc.qubits))),
        bits=tuple(cmap.values()),
        vars=(),
        notes=tuple(st.notes),
    )


def _bitref(qc: QuantumCircuit, cb: Clbit) -> BitRef:
    loc = qc.find_bit(cb)
    if loc.registers:
        reg, idx = loc.registers[0]
        return BitRef(reg.name, idx)
    return BitRef("_", loc.index)


def _block(circ: QuantumCircuit, qmap: dict[Any, int], cmap: dict[Any, BitRef],
           env: Env, scope: Scope, st: State) -> Seq:
    nid = st.ids.next()
    stmts = tuple(_inst(circ, i, inst, qmap, cmap, env, scope, st)
                  for i, inst in enumerate(circ.data))
    return Seq(nid=nid, loc=SourceLoc(st.file), stmts=stmts)


def _sub(block: QuantumCircuit, inst: Any, qmap: dict[Any, int], cmap: dict[Any, BitRef]
         ) -> tuple[dict[Any, int], dict[Any, BitRef]]:
    return (
        {bq: qmap[oq] for bq, oq in zip(block.qubits, inst.qubits, strict=True)},
        {bc: cmap[oc] for bc, oc in zip(block.clbits, inst.clbits, strict=True)},
    )


def _expr_ctx(cmap: dict[Any, BitRef], env: Env, loc: SourceLoc) -> ExprCtx:
    def bit(cb: Clbit) -> str:
        return read_bit(cmap[cb], env, loc)

    return ExprCtx(bit=bit, reg=lambda reg: [bit(b) for b in reg])


def _inst(circ: QuantumCircuit, idx: int, inst: Any, qmap: dict[Any, int],
          cmap: dict[Any, BitRef], env: Env, scope: Scope, st: State) -> Stmt:
    op = inst.operation
    name = op.name
    loc = SourceLoc(st.file, instr=idx)
    qs = tuple(qmap[q] for q in inst.qubits)

    if name in ("measure", "measure_2"):
        nid = st.ids.next()
        bit = cmap[inst.clbits[0]]
        env[bit] = bit_prop(bit.reg, bit.idx, nid)
        return Measure(nid=nid, loc=loc, qubit=qs[0], cbit=bit,
                       variant="mid" if name == "measure_2" else "std")
    if name == "reset":
        return Reset(nid=st.ids.next(), loc=loc, qubit=qs[0])
    if name == "barrier":
        return Barrier(nid=st.ids.next(), loc=loc, qubits=qs)
    if name == "delay":
        return Delay(nid=st.ids.next(), loc=loc, qubits=qs,
                     dur=delay_dt(op.duration, op.unit, st, loc))
    if name == "if_else":
        return _if(inst, op, loc, qmap, cmap, env, scope, st)
    if name == "while_loop":
        return _while(inst, op, loc, qmap, cmap, env, scope, st)
    if name == "for_loop":
        return _for(inst, op, loc, qmap, cmap, env, scope, st)
    if name == "switch_case":
        return _switch(inst, op, loc, qmap, cmap, env, scope, st)
    if name == "box":
        return _box(inst, op, loc, qmap, cmap, env, scope, st)
    if isinstance(op, QGate):
        return Gate(nid=st.ids.next(), loc=loc, name=name, qubits=qs, dur=gate_dur(name, st))
    raise QtError("E-FE-UNKNOWN-OP", f"instruction {name!r} is not a gate or a supported "
                  "operation", loc=loc, hint="no silent default durations: map it explicitly")


def _if(inst: Any, op: Any, loc: SourceLoc, qmap: dict[Any, int], cmap: dict[Any, BitRef],
        env: Env, scope: Scope, st: State) -> If:
    nid = st.ids.next()
    cond = to_expr(op.condition, _expr_ctx(cmap, env, loc))
    arms: list[Seq | None] = []
    envs: list[Env] = []
    for blk in op.blocks:
        qm, cm = _sub(blk, inst, qmap, cmap)
        e = dict(env)
        arms.append(_block(blk, qm, cm, e, scope, st))
        envs.append(e)
    if len(arms) == 1:
        arms.append(None)
        envs.append(dict(env))
    merge(env, envs)
    return If(nid=nid, loc=loc, cond=cond, then_=arms[0], else_=arms[1], policy=scope.policy)  # type: ignore[arg-type]


def _while(inst: Any, op: Any, loc: SourceLoc, qmap: dict[Any, int], cmap: dict[Any, BitRef],
           env: Env, scope: Scope, st: State) -> While:
    cap = while_cap(scope, loc)
    nid = st.ids.next()
    cond = to_expr(op.condition, _expr_ctx(cmap, env, loc))
    blk = op.blocks[0]
    qm, cm = _sub(blk, inst, qmap, cmap)
    e = dict(env)
    body = _block(blk, qm, cm, e, scope, st)
    merge(env, [e, dict(env)])  # the loop may run zero times
    exhaust = Seq(nid=st.ids.next(), loc=loc, stmts=())
    return While(nid=nid, loc=loc, cond=cond, body=body, cap=cap, exhaust=exhaust,
                 policy=scope.policy)


def _for(inst: Any, op: Any, loc: SourceLoc, qmap: dict[Any, int], cmap: dict[Any, BitRef],
         env: Env, scope: Scope, st: State) -> For:
    nid = st.ids.next()
    indexset, param = op.params[0], op.params[1]
    blk = op.blocks[0]
    qm, cm = _sub(blk, inst, qmap, cmap)
    e = dict(env)
    body = _block(blk, qm, cm, e, scope, st)
    merge(env, [e, dict(env)])
    return For(nid=nid, loc=loc, var=getattr(param, "name", "_i"), n=len(indexset), body=body)


def _switch(inst: Any, op: Any, loc: SourceLoc, qmap: dict[Any, int], cmap: dict[Any, BitRef],
            env: Env, scope: Scope, st: State) -> Switch:
    nid = st.ids.next()
    target = to_value(op.target, _expr_ctx(cmap, env, loc))
    cases: list[tuple[int, Stmt]] = []
    default: Stmt | None = None
    envs: list[Env] = []
    for values, blk in op.cases_specifier():
        qm, cm = _sub(blk, inst, qmap, cmap)
        e = dict(env)
        seq = _block(blk, qm, cm, e, scope, st)
        envs.append(e)
        for v in values:
            if v is CASE_DEFAULT:
                default = seq
            else:
                cases.append((int(v), seq))
    if default is None:
        envs.append(dict(env))
    merge(env, envs)
    return Switch(nid=nid, loc=loc, target=target, cases=tuple(cases), default=default)


def _box(inst: Any, op: Any, loc: SourceLoc, qmap: dict[Any, int], cmap: dict[Any, BitRef],
         env: Env, scope: Scope, st: State) -> Box:
    if op.duration is not None:
        raise QtError("E-FE-UNSUPPORTED", "box durations are not implemented yet", loc=loc)
    nid = st.ids.next()
    anns = tuple(sorted(timing_annotations(op.annotations)))
    inner = box_scope(anns, scope, set(cmap.values()), st, loc)
    blk = op.blocks[0]
    qm, cm = _sub(blk, inst, qmap, cmap)
    body = _block(blk, qm, cm, env, inner, st)  # a box runs once: share env
    return Box(nid=nid, loc=loc, dur=None, body=body, annotations=anns)


__all__ = ["UNRESOLVED_DUR", "Node", "from_circuit"]
