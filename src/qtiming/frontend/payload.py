"""Parsers for `timing.*` annotation payload strings. Pure: no Qiskit. Errors are QtErrors.

Durations keep their unit here; conversion to dt happens with role-aware rounding in `to_dt`
once the contract's dt is known.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction

from qtiming.core.ast import BitRef
from qtiming.core.errors import QtError
from qtiming.core.time import Role, ns_to_dt

_UNIT_NS = {"ns": 1, "us": 1000, "ms": 10**6, "s": 10**9}
_DUR = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(ns|us|ms|s|dt)\s*$")
_BIT = re.compile(r"^([A-Za-z_]\w*)\[(\d+)\]$")


def _bad(msg: str, code: str = "E-FE-ANNOT-PAYLOAD") -> QtError:
    return QtError(code, msg, hint="see the timing.* annotation table in the plan, Section 6.4")


@dataclass(frozen=True, slots=True)
class Dur:
    value: Fraction
    unit: str


@dataclass(frozen=True, slots=True)
class PolicyP:
    kind: str
    delta: Dur | None = None
    gap: Dur | None = None


def parse_duration(text: str) -> Dur:
    m = _DUR.match(text)
    if not m:
        raise _bad(f"bad duration {text!r}: expected e.g. 3000ns, 3us, 750dt")
    return Dur(Fraction(m.group(1)), m.group(2))


def to_dt(d: Dur, dt_ns: Fraction, role: Role) -> int:
    if d.unit == "dt":
        if d.value.denominator != 1:
            raise QtError("E-TIME-EXACT", f"{d.value} dt is not a whole number of dt")
        return d.value.numerator
    return ns_to_dt(d.value * _UNIT_NS[d.unit], dt_ns, role, what="annotation duration")


def parse_policy(text: str) -> PolicyP:
    t = text.strip()
    if t in ("eq", "exp"):
        return PolicyP(t)
    m = re.match(r"^sync(?:\((.*)\))?$", t)
    if not m:
        raise _bad(f"bad policy {text!r}: expected eq | exp | sync(delta=<dur>,gap=<dur>)")
    kw: dict[str, Dur] = {}
    if m.group(1):
        for part in m.group(1).split(","):
            k, sep, v = part.partition("=")
            k = k.strip()
            if not sep or k not in ("delta", "gap"):
                raise _bad(f"bad sync argument {part!r}: expected delta=<dur> or gap=<dur>")
            kw[k] = parse_duration(v)
    return PolicyP("sync", kw.get("delta"), kw.get("gap"))


def parse_bit(name: str) -> BitRef:
    m = _BIT.match(name.strip())
    if not m:
        raise _bad(f"bad bit name {name!r}: expected <register>[<index>]", "E-FE-ANNOT-BIT")
    return BitRef(m.group(1), int(m.group(2)))


def parse_within(text: str) -> tuple[Dur, BitRef]:
    parts = text.strip().rsplit(None, 1)
    if len(parts) != 2:
        raise _bad(f"bad within {text!r}: expected '<dur> <register>[<index>]'")
    return parse_duration(parts[0]), parse_bit(parts[1])


def parse_cap(text: str) -> tuple[int, str | None]:
    toks = text.split()
    if not toks or not re.fullmatch(r"\d+", toks[0]) or int(toks[0]) < 1 or len(toks) > 2:
        raise _bad(f"bad cap {text!r}: expected '<N> [exhaust=<label>]' with N >= 1")
    label = None
    if len(toks) == 2:
        k, _, v = toks[1].partition("=")
        if k != "exhaust" or not v:
            raise _bad(f"bad cap argument {toks[1]!r}: expected exhaust=<label>")
        label = v
    return int(toks[0]), label


def parse_call(text: str) -> tuple[str, str]:
    toks = text.split()
    if len(toks) != 2 or not toks[1].startswith("latency=") or len(toks[1]) <= len("latency="):
        raise _bad(f"bad call {text!r}: expected '<fn> latency=<key>'", "E-FE-CALL-UNBOUND")
    return toks[0], toks[1][len("latency="):]


def parse_pmin(text: str) -> Fraction:
    try:
        p = Fraction(text.strip())
    except (ValueError, ZeroDivisionError):
        raise _bad(f"bad pmin {text!r}: expected a rational in (0, 1]") from None
    if not 0 < p <= 1:
        raise _bad(f"pmin {text!r} must be in (0, 1]")
    return p
