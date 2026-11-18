"""Tier 2: exact SMT with Z3 (plan 11.4). QF_LRA for time and latency, Booleans for outcomes.

The constraint set has a model iff `t` is the dispatch time function of some (omega, theta)
(theorem T2), so UNSAT proves the obligation and SAT yields a real violating execution, with
exact rational values. If the cone contains an unbounded latency, SAT is NOT a refutation: the
missing number could make the obligation hold, so the result is UNKNOWN naming the key.
Imported lazily: z3 is an optional extra (`pip install qtiming[z3]`).
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

import z3

from qtiming.core.errors import QtError
from qtiming.core.labels import EBit, EConst, EUn, EVar, Expr, Label
from qtiming.graph.invariants import bit_props
from qtiming.graph.lteg import LTEG, LatVar
from qtiming.oblig.generate import ancestors
from qtiming.oblig.model import Diff, Mod, Obligation, Variation

from .concrete import Result


def RV(x: Fraction | int) -> Any:
    f = Fraction(x)
    return z3.RealVal(f"{f.numerator}/{f.denominator}")


def _bv(n: int) -> Any:
    return z3.BitVecVal(n, 32)


class Encoder:
    """The dispatch semantics of one copy of the universe (omega, theta, t) over a cone."""

    def __init__(self, g: LTEG, cone: set[int], tag: str = "") -> None:
        self.g, self.cone, self.tag = g, cone, tag
        self.bit = {p: z3.Bool(f"b{tag}:{p}") for p in bit_props(g)}
        self.der = {p: z3.Bool(f"d{tag}:{p}") for p in g.derived}
        self.th = {v.id: z3.Real(f"th{tag}:{v.id}") for v in g.lats}
        self.t = {n.id: z3.Real(f"t{tag}:{n.id}") for n in g.nodes if n.id in cone}
        self.pre = {n.id: z3.Real(f"m{tag}:{n.id}") for n in g.nodes if n.id in cone}
        self.ex = {n.id: self.label(n.label) for n in g.nodes if n.id in cone}

    def prop(self, p: str) -> Any:
        return self.bit[p] if p in self.bit else self.der[p]

    def label(self, lab: Label) -> Any:
        lits = [self.prop(x.prop) if x.pos else z3.Not(self.prop(x.prop)) for x in lab]
        return z3.And(lits) if lits else z3.BoolVal(True)

    def wexpr(self, w: int | LatVar) -> Any:
        return RV(w) if isinstance(w, int) else self.th[w.id]

    def val(self, e: Expr) -> Any:
        """Integer value as a 32-bit vector (matches Python ints on the small domains used)."""
        if isinstance(e, EConst):
            return _bv(e.value)
        if isinstance(e, EBit):
            return z3.If(self.bit[e.prop], _bv(1), _bv(0))
        if isinstance(e, EVar):
            raise QtError("E-SMT-UNSUPPORTED", "real-time variables are not encoded yet")
        if isinstance(e, EUn):
            x = self.val(e.a)
            return z3.If(x == 0, _bv(1), _bv(0)) if e.op == "not" else ~x
        a, b = self.val(e.a), self.val(e.b)

        def flag(c: Any) -> Any:
            return z3.If(c, _bv(1), _bv(0))

        ops: dict[str, Any] = {
            "and": lambda: flag(z3.And(a != 0, b != 0)), "or": lambda: flag(z3.Or(a != 0, b != 0)),
            "xor": lambda: a ^ b, "bit_xor": lambda: a ^ b, "bit_and": lambda: a & b,
            "bit_or": lambda: a | b, "add": lambda: a + b, "sub": lambda: a - b,
            "mul": lambda: a * b, "eq": lambda: flag(a == b), "ne": lambda: flag(a != b),
            "lt": lambda: flag(a < b), "le": lambda: flag(a <= b),
            "gt": lambda: flag(a > b), "ge": lambda: flag(a >= b),
        }
        if e.op not in ops:
            raise QtError("E-SMT-UNSUPPORTED", f"operator {e.op!r}")
        return ops[e.op]()

    def constraints(self) -> list[Any]:
        g, cs = self.g, []
        for v in g.lats:
            cs.append(self.th[v.id] >= RV(v.lo))
            if v.hi is not None:
                cs.append(self.th[v.id] <= RV(v.hi))
        for p, d in g.derived.items():
            cs.append(self.der[p] == (self.val(d.expr) != 0))
        cs.append(self.t[g.origin] == 0)
        for n in g.nodes:
            if n.id == g.origin or n.id not in self.cone:
                continue
            terms = []
            for ei in g.in_edges[n.id]:
                e = g.edges[ei]
                act = z3.And(self.label(e.label), self.ex[e.src])
                terms.append((act, self.t[e.src] + self.wexpr(e.w)))
            pre = self.pre[n.id]
            cs += [z3.Implies(act, pre >= val) for act, val in terms]  # pre >= every active term
            cs.append(z3.Implies(self.ex[n.id], z3.Or([z3.And(a, pre == v) for a, v in terms])))
            if n.snap:  # t = g * ceil(pre / g), ceil(y) = -floor(-y)
                s = RV(n.snap)
                cs.append(self.t[n.id] == s * -z3.ToReal(z3.ToInt(-pre / s)))
            else:
                cs.append(self.t[n.id] == pre)
        return cs


def _violated(enc: Encoder, c: Diff | Mod, guard: Label) -> Any:
    base = enc.label(guard)
    if isinstance(c, Diff):
        gap = enc.t[c.x] - enc.t[c.y]
        bad = gap > RV(c.c) if c.op == "<=" else gap < RV(c.c)
        return z3.And(base, enc.ex[c.x], enc.ex[c.y], bad)
    return z3.And(base, enc.ex[c.x], z3.Not(z3.IsInt((enc.t[c.x] - RV(c.residue)) / RV(c.g))))


def _model_run(m: Any, e: Encoder) -> tuple[dict[str, int], dict[str, Fraction]]:
    omega = {p: int(z3.is_true(m.eval(b, model_completion=True))) for p, b in e.bit.items()}
    theta: dict[str, Fraction] = {}
    for v in e.g.lats:
        val = m.eval(e.th[v.id], model_completion=True)
        theta[v.occurrence] = Fraction(val.numerator_as_long(), val.denominator_as_long())
    return omega, theta


def tier2(g: LTEG, o: Obligation, timeout_ms: int = 10_000) -> Result:
    c = o.check
    if not isinstance(c, (Diff, Mod, Variation)):
        return Result("unknown", reason="Tier 2 does not encode Events (O5) yet")
    cone = ancestors(g, o.nodes())
    s = z3.Solver()
    s.set("timeout", timeout_ms)
    try:
        if isinstance(c, Variation):  # two independent copies of the universe (plan 11.5)
            a, b = Encoder(g, cone, "a"), Encoder(g, cone, "b")
            s.add(a.constraints() + b.constraints())
            for e in (a, b):
                s.add(z3.And(e.label(o.guard), e.ex[c.x], e.ex[c.y]))
            s.add((a.t[c.x] - a.t[c.y]) - (b.t[c.x] - b.t[c.y]) > RV(c.bound))
            encs = [a, b]
        else:
            enc = Encoder(g, cone)
            s.add(enc.constraints())
            s.add(_violated(enc, c, o.guard))
            encs = [enc]
    except QtError as e:
        return Result("unknown", reason=e.message)
    r = s.check()
    if r == z3.unsat:
        return Result("proved", 2)
    if r == z3.unknown:
        return Result("unknown", 2, reason=f"Z3: {s.reason_unknown()}")
    m = s.model()
    unbounded = sorted({v.key for v in g.lats if v.id in o.deps and v.hi is None})
    if unbounded:  # a missing number: this is not a refutation
        return Result("unknown", 2, reason=f"fails if {', '.join(unbounded)} is large enough")
    omega, theta = _model_run(m, encs[0])
    res = Result("refuted", 2, reason=o.message, omega=omega, theta=theta)
    if len(encs) == 2:
        res.second, res.second_theta = _model_run(m, encs[1])
    return res
