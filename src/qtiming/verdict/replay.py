"""Replay every REFUTED in the reference executor (plan 13, principle 9).

The checker reports REFUTED only if the independent executor reproduces the failure. A mismatch
is `I-REPLAY-MISMATCH` (an internal error, exit code 4): the counterexample is withheld.
"""

from __future__ import annotations

from fractions import Fraction

from qtiming.contract.model import Contract
from qtiming.core.ast import Stmt
from qtiming.core.errors import QtError
from qtiming.exec.engine import ExecResult, execute
from qtiming.exec.oracle import Fixed
from qtiming.graph.lteg import LTEG
from qtiming.oblig.model import Diff, Events, Mod, Obligation, Variation
from qtiming.solve.concrete import Result

_HW = {"O1": {"underflow", "underflow-halt"}, "O2a": {"stale-read"}}


def _times_of(g: LTEG, res: ExecResult, node: int) -> Fraction | None:
    n = g.nodes[node]
    if n.kind == "origin":  # the program start: time 0, not an executor event
        return Fraction(0)
    return res.times.get((n.nid, n.tag))


def _single_fails(g: LTEG, o: Obligation, res: ExecResult) -> bool:
    c = o.check
    kinds = _HW.get(o.code, ())
    if any(v.nid == o.nid and v.kind in kinds for v in res.violations):
        return True
    # the run may halt on an EARLIER violation of the same kind (RTIOUnderflow raises, the Q1
    # sequencer halts): the program still fails under this witness, just before the named event
    if res.halted and any(v.kind in kinds for v in res.violations):
        return True
    if isinstance(c, Diff):
        x, y = _times_of(g, res, c.x), _times_of(g, res, c.y)
        if x is None or y is None:
            return False
        return (x - y > c.c) if c.op == "<=" else (x - y < c.c)
    if isinstance(c, Mod):
        x = _times_of(g, res, c.x)
        return x is not None and (x - c.residue) % c.g != 0
    if isinstance(c, Events):
        return bool(res.drops)
    return False


def replay(g: LTEG, o: Obligation, r: Result, body: Stmt, contract: Contract) -> bool:
    """True iff the executor reproduces the obligation's failure for the counterexample."""
    first = execute(body, contract, Fixed(r.omega, r.theta))
    if isinstance(o.check, Variation):
        if r.second is None:
            return False
        second = execute(body, contract, Fixed(r.second, r.second_theta or {}))
        c = o.check
        vals = []
        for run in (first, second):
            x, y = _times_of(g, run, c.x), _times_of(g, run, c.y)
            if x is None or y is None:
                return False
            vals.append(x - y)
        return abs(vals[0] - vals[1]) > c.bound
    return _single_fails(g, o, first)


def require_replay(g: LTEG, o: Obligation, r: Result, body: Stmt, contract: Contract) -> None:
    if not replay(g, o, r, body, contract):
        raise QtError(
            "I-REPLAY-MISMATCH",
            f"{o.code} at node {o.nid}: the executor did not reproduce the solver's "
            "counterexample; it is withheld",
            hint="this is a bug in the checker or the executor, please report it",
        )
