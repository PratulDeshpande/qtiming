"""Golden-case loader shared by the executor tests and (from P6) the graph tests.

A case is JSON: a tiny program DSL, a contract sketch, the oracle choices and HAND-COMPUTED
expected times. Names (`"id"` fields) map to node ids in preorder.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

from qtiming.contract.loader import load_contract_dict
from qtiming.contract.model import Contract
from qtiming.core.ast import Barrier, BitRef, Delay, For, Gate, If, Measure, Seq, SourceLoc, Stmt
from qtiming.core.ids import bit_prop, lat_occurrence
from qtiming.core.labels import EBin, EBit, EUn, Expr

ROOT = Path(__file__).parent
KLASS = {"ibm": "restricted", "q1": "predicated", "qua": "resync", "artiq": "exposed"}
POLICY = {"ibm": "sync", "q1": "eq", "qua": "sync", "artiq": "exp"}
LOC = SourceLoc("golden")


@dataclass
class Case:
    name: str
    path: Path
    prog: Stmt
    contract: Contract
    omega: dict[str, int]
    theta: dict[str, Fraction]
    expect: dict[str, Any]
    ids: dict[str, int]


def cases(personality: str) -> list[Path]:
    return sorted((ROOT / personality / "golden").glob("*.json"))


def make_contract(personality: str, spec: dict[str, Any]) -> Contract:
    raw: dict[str, Any] = {
        "meta": {"name": f"golden_{personality}", "version": "0", "schema": "qtiming-contract/0.2",
                 "personality": personality},
        "timebase": {"dt_ns": "1"},
        "timeline": {"late_policy": {"ibm": "compile_error", "q1": "halt", "artiq": "mixed",
                                     "qua": "compile_error"}[personality]},
        "durations": spec.get("durations", {}),
        "issue_cost": {k: {"ns": v, "prov": "cyc", "source": "golden"}
                       for k, v in spec.get("issue_cost", {}).items()},
        "capacity": spec.get("capacity", {}),
        "latency": [
            {"key": x["key"], "src": x["src"], "dst": x["dst"], "tier": x.get("tier", "default"),
             "lo_ns": x["lo"], **({} if x.get("hi") is None else {"hi_ns": x["hi"]}),
             "prov": "vendor", "source": "golden"}
            for x in spec["latencies"]
        ],
        "branch": {"class": KLASS[personality], "default_policy": POLICY[personality],
                   "allow_nested": False, **spec.get("branch", {})},
        "personality_params": {personality: spec.get("params", {})},
    }
    if spec.get("commit_lead") is not None:
        raw["timeline"]["commit_lead"] = spec["commit_lead"]
    return load_contract_dict(raw)


class _Builder:
    def __init__(self) -> None:
        self.n = 0
        self.ids: dict[str, int] = {}
        self.bit_of: dict[int, int] = {}

    def seq(self, ops: list[dict[str, Any]]) -> Stmt:
        nid = self.n
        self.n += 1
        return Seq(nid=nid, loc=LOC, stmts=tuple(self.stmt(o) for o in ops))

    def stmt(self, op: dict[str, Any]) -> Stmt:
        kind, nid = op["op"], self.n
        self.n += 1
        if "id" in op:
            self.ids[op["id"]] = nid
        if kind == "gate":
            return Gate(nid=nid, loc=LOC, name=op.get("name", "g"), qubits=tuple(op["q"]),
                        dur=op["dur"])
        if kind == "delay":
            return Delay(nid=nid, loc=LOC, qubits=tuple(op["q"]), dur=op["dur"])
        if kind == "for":
            return For(nid=nid, loc=LOC, var="i", n=op["n"], body=self.seq(op["body"]))
        if kind == "barrier":
            return Barrier(nid=nid, loc=LOC, qubits=tuple(op["q"]))
        if kind == "measure":
            self.bit_of[nid] = op.get("bit", 0)
            return Measure(nid=nid, loc=LOC, qubit=op["q"], cbit=BitRef("c", op.get("bit", 0)),
                           variant=op.get("variant", "std"), tier=op.get("tier", "default"))
        if kind == "if":
            name = op["cond"]
            parts = [self.ids[x] for x in name.lstrip("!").split("^")]
            cond: Expr = EBit(bit_prop("c", self.bit_of[parts[0]], parts[0]))
            for extra in parts[1:]:  # "m0^m1": xor of two bits (a derived condition)
                cond = EBin("xor", cond, EBit(bit_prop("c", self.bit_of[extra], extra)))
            if name.startswith("!"):
                cond = EUn("not", cond)
            then_ = self.seq(op["then"])
            else_ = self.seq(op["else"]) if op.get("else") is not None else None
            return If(nid=nid, loc=LOC, cond=cond, then_=then_, else_=else_)
        raise ValueError(f"unknown op {kind}")


def build(ops: list[dict[str, Any]]) -> tuple[Stmt, dict[str, int]]:
    b = _Builder()
    return b.seq(ops), b.ids


def load_case(path: Path) -> Case:
    d = json.loads(path.read_text(encoding="utf-8"))
    contract = make_contract(d["personality"], d["contract"])
    b = _Builder()
    prog = b.seq(d["program"])
    omega = {bit_prop("c", b.bit_of[b.ids[k]], b.ids[k]): v for k, v in d.get("omega", {}).items()}
    theta = {}
    for k, v in d.get("theta", {}).items():
        key, _, who = k.partition("@")
        theta[lat_occurrence(key, b.ids[who])] = Fraction(v)
    return Case(d["name"], path, prog, contract, omega, theta, d["expect"], b.ids)


def expected_times(c: Case) -> dict[tuple[int, str], Fraction]:
    out = {}
    for k, v in c.expect.get("times", {}).items():
        who, _, tag = k.partition(".")
        out[(c.ids[who], tag)] = Fraction(v)
    return out
