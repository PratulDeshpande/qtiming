"""Walker semantics shared by the Qiskit and OpenQASM 3 front ends. Pure: no Qiskit.

Both walkers only translate syntax; every timing rule (bit-writer tracking, annotation scoping,
duration rounding, the while-cap rule) lives here so the two cannot drift apart.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from fractions import Fraction

from qtiming.core.ast import BitRef, Policy, SourceLoc
from qtiming.core.errors import QtError
from qtiming.core.ids import IdGen
from qtiming.core.labels import EBin, EBit, EConst, Expr
from qtiming.core.time import ns_to_dt

from .payload import parse_call, parse_cap, parse_pmin, parse_policy, parse_within, to_dt
from .program import ContractView

UNRESOLVED_DUR = -1  # gate duration not known yet; elaboration repeats the lookup
AMBIGUOUS = "\0ambiguous"  # a bit whose latest writer depends on the path taken
UNIT_NS = {"s": Fraction(10**9), "ms": Fraction(10**6), "us": Fraction(10**3),
           "ns": Fraction(1), "ps": Fraction(1, 1000)}

Env = dict[BitRef, str]  # bit -> proposition of its latest writer on the current path


@dataclass
class State:
    contract: ContractView | None
    ids: IdGen = field(default_factory=IdGen)
    notes: list[QtError] = field(default_factory=list)
    file: str = "<circuit>"
    noted: set[str] = field(default_factory=set)

    @property
    def dt(self) -> Fraction | None:
        return None if self.contract is None else self.contract.dt_ns


@dataclass(frozen=True)
class Scope:
    policy: Policy | None = None
    cap: tuple[int, str | None] | None = None


def merge(env: Env, branches: list[Env]) -> None:
    for k in set(env).union(*branches):
        vals = {b.get(k) for b in branches}
        if len(vals) == 1:
            v = vals.pop()
            if v is not None:
                env[k] = v
        else:
            env[k] = AMBIGUOUS


def read_bit(ref: BitRef, env: Env, loc: SourceLoc) -> str:
    prop = env.get(ref)
    if prop is None:
        raise QtError("E-FE-BIT-UNWRITTEN", f"{ref.reg}[{ref.idx}] is read before any "
                      "measurement writes it", loc=loc,
                      hint="measure into the bit before the condition that reads it")
    if prop == AMBIGUOUS:
        raise QtError("E-FE-UNSUPPORTED",
                      f"{ref.reg}[{ref.idx}] is written in only some branches before this "
                      "read (merge of writers not supported yet)", loc=loc,
                      hint="measure into the bit again after the branch")
    return prop


def reg_value(props: list[str]) -> Expr:
    """A register's unsigned value from its bit propositions, LSB first."""
    acc: Expr = EBit(props[0])
    for i, p in enumerate(props[1:], start=1):
        acc = EBin("add", acc, EBin("mul", EConst(1 << i, len(props)), EBit(p)))
    return acc


def gate_dur(name: str, st: State) -> int:
    if st.contract is None:
        if name not in st.noted:
            st.noted.add(name)
            st.notes.append(QtError("N-FE-DUR-UNRESOLVED",
                                    f"duration of gate {name!r} not resolved (no contract)",
                                    severity="note"))
        return UNRESOLVED_DUR
    return st.contract.duration(name)


def delay_dt(value: float | int | Fraction, unit: str, st: State, loc: SourceLoc) -> int:
    if unit == "dt":
        return int(value)
    if st.dt is None:
        raise QtError("E-FE-NO-DT", f"delay of {value}{unit} needs a contract for dt",
                      loc=loc, hint="pass contract=... or write the delay in dt")
    if unit not in UNIT_NS:
        raise QtError("E-FE-UNSUPPORTED", f"delay unit {unit!r}", loc=loc)
    return ns_to_dt(Fraction(str(value)) * UNIT_NS[unit], st.dt, "exact", what="delay")


def _core_policy(text: str, st: State, loc: SourceLoc) -> Policy:
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


def box_scope(anns: Iterable[tuple[str, str]], scope: Scope, bits: set[BitRef], st: State,
              loc: SourceLoc) -> Scope:
    """Validate a box's timing annotations; return the scope its body runs under."""
    policy, cap = scope.policy, scope.cap
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
    return Scope(policy, cap)


def while_cap(scope: Scope, loc: SourceLoc) -> int:
    if scope.cap is None:
        raise QtError("E-FE-UNBOUNDED-WHILE", "while loop without an iteration cap", loc=loc,
                      hint="wrap it in a box annotated timing.cap, e.g. Cap('8')")
    cap, label = scope.cap
    if label is not None:
        raise QtError("E-FE-UNSUPPORTED", "timing.cap exhaust labels are not implemented yet",
                      loc=loc, hint="omit exhaust=<label> for an empty exhaust handler")
    return cap
