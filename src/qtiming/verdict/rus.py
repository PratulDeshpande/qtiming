"""Repeat-until-success verdict (plan 13.5, finding F23). All arithmetic is exact (`Fraction`).

Capped loop: body duration `T`, cap `N`, exhaust handler `T_exh`, declared lower bound on the
per-iteration success probability `p_min`, `q = 1 - p_min`:

    WCET = N*T + T_exh,   E[T] <= T*(1 - q^N)/p_min + q^N*T_exh,   Pr[exhaust] <= q^N

Deadline `D` enclosing the loop with `T_post` of work after it: `m = floor((D - T_post)/T)`
iterations fit, and `Pr[miss] <= q^min(m, N)` (1 if m < 0). `p_min` is a declared parameter; it
belongs in the verdict's assumption list.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any


def rus_verdict(
    T: Fraction | int,
    N: int,
    T_exh: Fraction | int,
    p_min: Fraction,
    D: Fraction | int | None = None,
    T_post: Fraction | int = 0,
    eps: Fraction | None = None,
) -> dict[str, Any]:
    T, T_exh, T_post = Fraction(T), Fraction(T_exh), Fraction(T_post)
    if not 0 < p_min <= 1 or N < 1 or T <= 0:
        raise ValueError("need 0 < p_min <= 1, N >= 1 and T > 0")
    q = 1 - p_min
    out: dict[str, Any] = {
        "wcet": N * T + T_exh,
        "expected_ub": T * (1 - q**N) / p_min + q**N * T_exh,
        "p_exhaust_ub": q**N,
    }
    if D is not None:
        D = Fraction(D)
        m = (D - T_post) // T  # floor division of Fractions
        out["m"] = m
        if m < 0:
            out["p_miss_ub"] = Fraction(1)
        elif m >= N:
            out["p_miss_ub"] = q**N if N * T + T_exh + T_post > D else Fraction(0)
        else:
            out["p_miss_ub"] = q**m
        out["hard_fits"] = out["wcet"] + T_post <= D  # the worst case fits in D
    if eps is not None:  # smallest n with q^n <= eps
        n = 0
        while q**n > eps:
            n += 1
        out["n_star"] = n
    return out
