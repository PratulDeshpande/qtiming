"""Stretch resolution: exact linear algebra over Fractions (Section 6.6).

Each equation is  sum(coeff * stretch) = rhs  (rhs already has the fixed durations moved over).
shortcut: an under-determined system sets free stretches to 0 (the minimal point), and a negative
result is reported as inconsistent without an LP feasibility search; upgrade if a program needs a
free stretch to be positive.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from qtiming.core.errors import QtError


@dataclass(frozen=True, slots=True)
class Eq:
    terms: dict[str, Fraction]
    rhs: Fraction


@dataclass(frozen=True, slots=True)
class StretchSolution:
    values: dict[str, Fraction]
    ambiguous: tuple[str, ...]  # free variables resolved to 0 (warning W-FE-STRETCH-AMBIGUOUS)


def solve_stretch(eqs: list[Eq], *, strict: bool = False) -> StretchSolution:
    names: list[str] = []
    for e in eqs:
        for v in e.terms:
            if v not in names:
                names.append(v)
    n = len(names)
    rows = [[e.terms.get(v, Fraction(0)) for v in names] + [e.rhs] for e in eqs]

    pivots: list[int] = []  # pivot column of each reduced row
    r = 0
    for col in range(n):
        piv = next((i for i in range(r, len(rows)) if rows[i][col] != 0), None)
        if piv is None:
            continue
        rows[r], rows[piv] = rows[piv], rows[r]
        scale = rows[r][col]
        rows[r] = [x / scale for x in rows[r]]
        for i in range(len(rows)):
            if i != r and rows[i][col] != 0:
                f = rows[i][col]
                rows[i] = [a - f * b for a, b in zip(rows[i], rows[r], strict=True)]
        pivots.append(col)
        r += 1
    for row in rows[r:]:
        if row[n] != 0:
            raise QtError(
                "E-FE-STRETCH-INCONSISTENT", "the stretch equations contradict each other",
                hint="check the box durations that constrain these stretches")

    values = {v: Fraction(0) for v in names}
    for i, col in enumerate(pivots):
        values[names[col]] = rows[i][n]
    free = tuple(v for j, v in enumerate(names) if j not in pivots)
    for v, x in values.items():
        if x < 0:
            raise QtError("E-FE-STRETCH-INCONSISTENT",
                          f"stretch {v!r} would have to be negative ({x})",
                          hint="the enclosing box is shorter than its fixed content")
    if free and strict:
        raise QtError("E-FE-STRETCH-AMBIGUOUS", f"stretch variable(s) {list(free)} are not "
                      "determined by the program", hint="constrain them with a box duration")
    return StretchSolution(values, free)
