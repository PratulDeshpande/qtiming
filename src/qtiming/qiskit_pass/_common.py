"""Shared helpers for the Qiskit passes."""

from __future__ import annotations

from pathlib import Path

from qtiming.contract.loader import load_contract
from qtiming.contract.model import Contract

INSTANCES = Path(__file__).resolve().parents[1] / "contract" / "instances"


def as_contract(c: Contract | str | Path) -> Contract:
    """A loaded contract, a path, or the name of a shipped instance (`ibm_heron`, `q1`, ...)."""
    if isinstance(c, Contract):
        return c
    p = Path(c)
    for cand in (p, INSTANCES / f"{c}.toml", INSTANCES / f"{c}_heron.toml"):
        if cand.is_file():
            return load_contract(str(cand))
    raise FileNotFoundError(f"no contract file or shipped instance named {str(c)!r}")
