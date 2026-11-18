"""Personality dispatch rules: each builder subclasses the common LTEG builder."""

from __future__ import annotations

from qtiming.contract.model import Contract
from qtiming.core.ast import Stmt
from qtiming.graph.builder import GraphBuilder
from qtiming.graph.lteg import LTEG

from .artiq import ArtiqBuilder
from .ibm import IbmBuilder
from .q1 import Q1Builder
from .qua import QuaBuilder

BUILDERS: dict[str, type[GraphBuilder]] = {
    "ibm": IbmBuilder, "q1": Q1Builder, "artiq": ArtiqBuilder, "qua": QuaBuilder,
}


def build_graph(prog: Stmt, contract: Contract) -> LTEG:
    """The LTEG of an ELABORATED program under the contract's personality."""
    return BUILDERS[contract.personality](contract).build(prog)
