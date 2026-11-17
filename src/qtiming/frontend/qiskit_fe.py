"""Qiskit QuantumCircuit -> TQ (requires qiskit). Read-only: never mutates the circuit.

Walks `circuit.data` in program order, recursing into control-flow blocks and mapping block
qubits/clbits to the outer circuit through the instruction operands (never by position in the
block). Scheduling is the graph builder's job; nothing here keeps per-qubit cursors.

Deferred (refused with E-FE-UNSUPPORTED, never guessed): bits written in only some arms of a
branch/loop and read afterwards (phi merge); `timing.cap` exhaust labels; box durations;
`Var`/`Store`; stretch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
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
    Policy,
    Reset,
    Seq,
    SourceLoc,
    Stmt,
    Switch,
    While,
)
from qtiming.core.errors import QtError
from qtiming.core.ids import IdGen, bit_prop
from qtiming.core.time import ns_to_dt

from .annotations import timing_annotations
from .payload import parse_call, parse_cap, parse_pmin, parse_policy, parse_within, to_dt
from .program import ContractView, Program
from .qiskit_expr import ExprCtx, to_expr, to_value

UNRESOLVED_DUR = -1  # gate duration not known yet; elaboration repeats the lookup
_AMBIGUOUS = "\0ambiguous"  # a bit whose latest writer depends on the path taken
_UNIT_NS = {"s": Fraction(10**9), "ms": Fraction(10**6), "us": Fraction(10**3),
            "ns": Fraction(1), "ps": Fraction(1, 1000)}


@dataclass
class _State:
    contract: ContractView | None
    ids: IdGen = field(default_factory=IdGen)
    notes: list[QtError] = field(default_factory=list)
    file: str = "<circuit>"
    noted: set[str] = field(default_factory=set)

    @property
    def dt(self) -> Fraction | None:
        return None if self.contract is None else self.contract.dt_ns


@dataclass(frozen=True)
class _Scope:
    policy: Policy | None = None
    cap: tuple[int, str | None] | None = None


def from_circuit(qc: QuantumCircuit, *, contract: ContractView | None = None) -> Program:
    st = _State(contract, file=qc.name or "<circuit>")
    cmap = {cb: _bitref(qc, cb) for cb in qc.clbits}
    qmap = {q: i for i, q in enumerate(qc.qubits)}
    body = _block(qc, qmap, cmap, {}, _Scope(), st)
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
           env: dict[BitRef, str], scope: _Scope, st: _State) -> Seq:
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


def _merge(env: dict[BitRef, str], branches: list[dict[BitRef, str]]) -> None:
    keys = set(env).union(*branches)
    for k in keys:
        vals = {b.get(k) for b in branches}
        if len(vals) == 1:
            v = vals.pop()
            if v is not None:
                env[k] = v
        else:
            env[k] = _AMBIGUOUS


def _expr_ctx(cmap: dict[Any, BitRef], env: dict[BitRef, str], loc: SourceLoc) -> ExprCtx:
    def bit(cb: Clbit) -> str:
        ref = cmap[cb]
        prop = env.get(ref)
        if prop is None:
            raise QtError("E-FE-BIT-UNWRITTEN", f"{ref.reg}[{ref.idx}] is read before any "
                          "measurement writes it", loc=loc,
                          hint="measure into the bit before the condition that reads it")
        if prop == _AMBIGUOUS:
            raise QtError("E-FE-UNSUPPORTED",
                          f"{ref.reg}[{ref.idx}] is written in only some branches before this "
                          "read (merge of writers not supported yet)", loc=loc,
                          hint="measure into the bit again after the branch")
        return prop

    return ExprCtx(bit=bit, reg=lambda reg: [bit(b) for b in reg])


def _core_policy(text: str, st: _State, loc: SourceLoc) -> Policy:
    pp = parse_policy(text)
    if pp.kind != "sync":
        return Policy(pp.kind)  # type: ignore[arg-type]
    out: list[int | None] = []
    for d, role in ((pp.delta, "spread_bound"), (pp.gap, "gap_bound")):
        if d is None:
            out.append(None)
        elif d.unit != "dt" and st.dt is None:
            raise QtError("E-FE-NO-DT", "a sync policy in time units needs a contract for dt",
                          loc=loc, hint="pass contract=... or write the duration in dt")
        else:
            out.append(to_dt(d, st.dt or Fraction(1), role))  # type: ignore[arg-type]
    return Policy("sync", delta=out[0], gap=out[1])


def _inst(circ: QuantumCircuit, idx: int, inst: Any, qmap: dict[Any, int],
          cmap: dict[Any, BitRef], env: dict[BitRef, str], scope: _Scope, st: _State) -> Stmt:
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
        return Delay(nid=st.ids.next(), loc=loc, qubits=qs, dur=_delay_dt(op, st, loc))
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
        return Gate(nid=st.ids.next(), loc=loc, name=name, qubits=qs, dur=_gate_dur(name, st))
    raise QtError("E-FE-UNKNOWN-OP", f"instruction {name!r} is not a gate or a supported "
                  "operation", loc=loc, hint="no silent default durations: map it explicitly")


def _gate_dur(name: str, st: _State) -> int:
    if st.contract is None:
        if name not in st.noted:
            st.noted.add(name)
            st.notes.append(QtError("N-FE-DUR-UNRESOLVED",
                                    f"duration of gate {name!r} not resolved (no contract)",
                                    severity="note"))
        return UNRESOLVED_DUR
    return st.contract.duration(name)


def _delay_dt(op: Any, st: _State, loc: SourceLoc) -> int:
    if op.unit == "dt":
        return int(op.duration)
    if st.dt is None:
        raise QtError("E-FE-NO-DT", f"delay of {op.duration}{op.unit} needs a contract for dt",
                      loc=loc, hint="pass contract=... or write the delay in dt")
    ns = Fraction(str(op.duration)) * _UNIT_NS[op.unit]
    return ns_to_dt(ns, st.dt, "exact", what="delay")


def _if(inst: Any, op: Any, loc: SourceLoc, qmap: dict[Any, int], cmap: dict[Any, BitRef],
        env: dict[BitRef, str], scope: _Scope, st: _State) -> If:
    nid = st.ids.next()
    cond = to_expr(op.condition, _expr_ctx(cmap, env, loc))
    arms: list[Seq | None] = []
    envs: list[dict[BitRef, str]] = []
    for blk in op.blocks:
        qm, cm = _sub(blk, inst, qmap, cmap)
        e = dict(env)
        arms.append(_block(blk, qm, cm, e, scope, st))
        envs.append(e)
    if len(arms) == 1:
        arms.append(None)
        envs.append(dict(env))
    _merge(env, envs)
    return If(nid=nid, loc=loc, cond=cond, then_=arms[0], else_=arms[1], policy=scope.policy)  # type: ignore[arg-type]


def _while(inst: Any, op: Any, loc: SourceLoc, qmap: dict[Any, int], cmap: dict[Any, BitRef],
           env: dict[BitRef, str], scope: _Scope, st: _State) -> While:
    if scope.cap is None:
        raise QtError("E-FE-UNBOUNDED-WHILE", "while loop without an iteration cap", loc=loc,
                      hint="wrap it in a box annotated timing.cap, e.g. Cap('8')")
    cap, label = scope.cap
    if label is not None:
        raise QtError("E-FE-UNSUPPORTED", "timing.cap exhaust labels are not implemented yet",
                      loc=loc, hint="omit exhaust=<label> for an empty exhaust handler")
    nid = st.ids.next()
    cond = to_expr(op.condition, _expr_ctx(cmap, env, loc))
    blk = op.blocks[0]
    qm, cm = _sub(blk, inst, qmap, cmap)
    e = dict(env)
    body = _block(blk, qm, cm, e, scope, st)
    _merge(env, [e, dict(env)])  # the loop may run zero times
    exhaust = Seq(nid=st.ids.next(), loc=loc, stmts=())
    return While(nid=nid, loc=loc, cond=cond, body=body, cap=cap, exhaust=exhaust,
                 policy=scope.policy)


def _for(inst: Any, op: Any, loc: SourceLoc, qmap: dict[Any, int], cmap: dict[Any, BitRef],
         env: dict[BitRef, str], scope: _Scope, st: _State) -> For:
    nid = st.ids.next()
    indexset, param = op.params[0], op.params[1]
    blk = op.blocks[0]
    qm, cm = _sub(blk, inst, qmap, cmap)
    e = dict(env)
    body = _block(blk, qm, cm, e, scope, st)
    _merge(env, [e, dict(env)])
    return For(nid=nid, loc=loc, var=getattr(param, "name", "_i"), n=len(indexset), body=body)


def _switch(inst: Any, op: Any, loc: SourceLoc, qmap: dict[Any, int], cmap: dict[Any, BitRef],
            env: dict[BitRef, str], scope: _Scope, st: _State) -> Switch:
    nid = st.ids.next()
    target = to_value(op.target, _expr_ctx(cmap, env, loc))
    cases: list[tuple[int, Stmt]] = []
    default: Stmt | None = None
    envs: list[dict[BitRef, str]] = []
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
    _merge(env, envs)
    return Switch(nid=nid, loc=loc, target=target, cases=tuple(cases), default=default)


def _box(inst: Any, op: Any, loc: SourceLoc, qmap: dict[Any, int], cmap: dict[Any, BitRef],
         env: dict[BitRef, str], scope: _Scope, st: _State) -> Box:
    if op.duration is not None:
        raise QtError("E-FE-UNSUPPORTED", "box durations are not implemented yet", loc=loc)
    nid = st.ids.next()
    anns = tuple(sorted(timing_annotations(op.annotations)))
    policy, cap = scope.policy, scope.cap
    bits = set(cmap.values())
    for kind, payload in anns:
        if kind == "policy":
            policy = _core_policy(payload, st, loc)
        elif kind == "within":
            _, anchor = parse_within(payload)
            if anchor not in bits:
                raise QtError("E-FE-ANNOT-BIT", f"within anchor {anchor.reg}[{anchor.idx}] is "
                              "not a bit of this circuit", loc=loc)
        elif kind == "cap":
            cap = parse_cap(payload)
        elif kind == "pmin":
            parse_pmin(payload)
        elif kind == "call":
            parse_call(payload)
    blk = op.blocks[0]
    qm, cm = _sub(blk, inst, qmap, cmap)
    body = _block(blk, qm, cm, env, _Scope(policy, cap), st)  # a box runs once: share env
    return Box(nid=nid, loc=loc, dur=None, body=body, annotations=anns)


__all__ = ["UNRESOLVED_DUR", "Node", "from_circuit"]
