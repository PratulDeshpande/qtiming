"""Windowing (plan 9.7, 8.6): cut a long `for` loop into the program around it plus ONE iteration.

A loop over the unroll limit is summarised only if its body is a legal window, i.e. the cut rules
hold (anything else raises `E-GRAPH-CUT` naming the failed rule, and the verdict is UNKNOWN):

1. full join: the body opens and closes with a barrier over every qubit of the program;
3. no obligation crosses the cut: classical bits are read only inside the body that wrote them
   (conditions and `within` anchors), and nothing outside reads a bit the body writes;
4. canonical personality state: only `ibm` qualifies (its barrier is exact, so `t(J)` is the whole
   state). ARTIQ's SED lanes and Q1's RT queue are not summarised by `t(J)`, and QUA's align has
   a latency of its own, which puts the O4 idle gap between two joins across the cut (found by
   `tests/differential/test_window_vs_whole.py`); those cuts are refused;
5. grid residue: refused if the contract has any grid coarser than 1 dt (O8 is not generated).

Rule 2 (dominator cut) follows from rule 1 in this AST: a full barrier is the only edge source
for every later node. Soundness of the composition is theorem target T4 (plan 15), tested by
`tests/unit/graph/test_window.py` against the fully unrolled program.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from qtiming.contract.model import Contract
from qtiming.core.ast import Barrier, Box, For, Measure, Seq, Stmt, Within
from qtiming.core.errors import QtError
from qtiming.core.ids import bit_prop
from qtiming.elab import _props, qubits_of
from qtiming.frontend.payload import parse_within

_CHILDREN = ("stmts", "body", "then_", "else_", "default", "exhaust")
_CANONICAL = ("ibm",)  # qua: align has its own latency, so the gap between two joins (O4) crosses


@dataclass(frozen=True, slots=True)
class Windows:
    rest: Stmt  # the program with each summarised loop replaced by its opening join
    bodies: tuple[Stmt, ...]  # one iteration window per summarised loop, origin = its first join
    notes: tuple[str, ...] = ()


def _walk(s: Any) -> Any:
    """Pre-order over statements (source order)."""
    yield s
    for name in _CHILDREN:
        v = getattr(s, name, None)
        for c in (v if isinstance(v, tuple) else (v,)):
            if c is not None and hasattr(c, "nid"):
                yield from _walk(c)


def _reads_writes(s: Stmt) -> tuple[list[tuple[str, Any]], set[str], set[tuple[str, int]]]:
    """(reads, props written, bits written); a read is ("prop", p) or ("bit", (reg, idx))."""
    reads: list[tuple[str, Any]] = []
    props: set[str] = set()
    bits: set[tuple[str, int]] = set()
    for x in _walk(s):
        if isinstance(x, Measure):
            props.add(bit_prop(x.cbit.reg, x.cbit.idx, x.nid))
            bits.add((x.cbit.reg, x.cbit.idx))
        cond = getattr(x, "cond", None)
        if cond is not None:
            reads += [("prop", p) for p in _props(cond)]
        if isinstance(x, Within):
            reads.append(("bit", (x.anchor.reg, x.anchor.idx)))
        elif isinstance(x, Box) and any(k == "within" for k, _ in x.annotations):
            a = parse_within(dict(x.annotations)["within"])[1]
            reads.append(("bit", (a.reg, a.idx)))
    return reads, props, bits


def _check_loop(loop: For, pre: tuple[Stmt, ...], post: tuple[Stmt, ...], all_q: set[int],
                contract: Contract) -> None:
    def refuse(msg: str) -> QtError:
        return QtError("E-GRAPH-CUT", f"loop at {loop.loc}: {msg}", loop.loc)

    if contract.personality not in _CANONICAL:  # rule 4
        raise refuse(f"personality state of {contract.personality} is not canonical at a cut "
                     "(rule 4)")
    if any(v > 1 for _, v in contract.grid):  # rule 5
        raise refuse("grid residue t(J) mod g is not tracked (rule 5)")
    items = loop.body.stmts if isinstance(loop.body, Seq) else (loop.body,)
    ends = (items[0], items[-1]) if len(items) >= 2 else ()
    if not ends or not all(isinstance(b, Barrier) and set(b.qubits) == all_q for b in ends):
        raise refuse("the body must open and close with a barrier over every qubit "
                     f"{sorted(all_q)}: no full join (rule 1)")
    reads, wprops, wbits = _reads_writes(loop.body)
    for kind, what in reads:  # a read inside must name a bit this body writes
        if (kind == "prop" and what not in wprops) or (kind == "bit" and what not in wbits):
            raise refuse(f"the body reads {what} measured outside it: cross-cut dependency "
                         "(rule 3)")
    for s in (*pre, *post):
        for kind, what in _reads_writes(s)[0]:
            if (kind == "prop" and what in wprops) or (kind == "bit" and what in wbits):
                raise refuse(f"code outside reads {what} written by the body: cross-cut "
                             "dependency (rule 3)")


def split_loops(prog: Stmt, contract: Contract, limit: int) -> Windows:
    """Summarise every top-level `for` with n > limit; loops within the limit are untouched."""
    if not isinstance(prog, Seq):
        return Windows(prog, ())
    all_q = qubits_of(prog)
    stmts: list[Stmt] = []
    bodies: list[Stmt] = []
    notes: list[str] = []
    for i, s in enumerate(prog.stmts):
        if not (isinstance(s, For) and s.n > limit):
            stmts.append(s)
            continue
        _check_loop(s, prog.stmts[:i], prog.stmts[i + 1:], all_q, contract)
        assert isinstance(s.body, Seq)
        stmts.append(s.body.stmts[0])  # the opening join stands in for the whole loop
        bodies.append(s.body)
        notes.append(f"window: loop of {s.n} iterations summarised by one iteration window "
                     "(cut rules 1, 3, 4, 5 hold)")
    if not bodies:
        return Windows(prog, ())
    return Windows(replace(prog, stmts=tuple(stmts)), tuple(bodies), tuple(notes))
