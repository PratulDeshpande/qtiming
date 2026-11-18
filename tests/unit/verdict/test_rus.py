"""The RUS table of plan Section 13.5, reproduced exactly."""

from __future__ import annotations

from fractions import Fraction

import pytest

from qtiming.verdict.rus import rus_verdict

HALF = Fraction(1, 2)


def test_table_values_exactly() -> None:
    r = rus_verdict(T=2, N=20, T_exh=0, p_min=HALF, D=10, T_post=2, eps=Fraction(1, 10**6))
    assert r["n_star"] == 20  # 2^-20 = 9.54e-7 <= 1e-6 and 2^-19 is not
    assert r["wcet"] == 40  # 40 us + T_exh
    assert r["p_exhaust_ub"] == Fraction(1, 2**20)
    assert r["m"] == 4 and r["p_miss_ub"] == Fraction(1, 16)  # 6.25%
    assert r["hard_fits"] is False  # 40 us > 10 us
    assert r["expected_ub"] == 4 * (1 - Fraction(1, 2**20))  # about 4 us


def test_without_post_loop_work_the_v1_formula() -> None:
    r = rus_verdict(T=2, N=20, T_exh=0, p_min=HALF, D=10, T_post=0)
    assert r["m"] == 5 and r["p_miss_ub"] == Fraction(1, 32)  # 3.125%


def test_expected_time_includes_the_exhaust_term() -> None:
    r = rus_verdict(T=2, N=3, T_exh=10, p_min=HALF)
    q = Fraction(1, 2)
    assert r["expected_ub"] == 2 * (1 - q**3) / HALF + q**3 * 10


@pytest.mark.parametrize("D,post,want", [
    (3, 0, Fraction(1, 2)),  # m = 1
    (1, 0, Fraction(1)),  # m = 0 -> q^0 = 1
    (1, 5, Fraction(1)),  # m < 0
    (100, 0, Fraction(0)),  # everything fits, exhaust path too
])
def test_deadline_miss_cases(D: int, post: int, want: Fraction) -> None:
    assert rus_verdict(T=2, N=4, T_exh=1, p_min=HALF, D=D, T_post=post)["p_miss_ub"] == want


def test_exhaust_path_misses_when_cap_work_exceeds_deadline() -> None:
    r = rus_verdict(T=2, N=3, T_exh=50, p_min=HALF, D=20)  # m = 10 >= N but exhaust is too long
    assert r["p_miss_ub"] == Fraction(1, 8)


def test_bad_parameters_are_rejected() -> None:
    with pytest.raises(ValueError):
        rus_verdict(T=2, N=3, T_exh=0, p_min=Fraction(0))
