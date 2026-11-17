from fractions import Fraction as F

import pytest

from qtiming.core.errors import QtError
from qtiming.frontend.stretch import Eq, solve_stretch


def test_unique_solution() -> None:
    # box[100] { delay(s1) ; delay(30) }  ->  s1 = 70 ;  2*s2 + s1 = 200 -> s2 = 65
    sol = solve_stretch([Eq({"s1": F(1)}, F(70)), Eq({"s2": F(2), "s1": F(1)}, F(200))])
    assert sol.values == {"s1": F(70), "s2": F(65)} and sol.ambiguous == ()


def test_underdetermined_resolves_to_minimal_and_flags() -> None:
    # s1 + s2 = 10 : free variable set to 0, reported as ambiguous
    sol = solve_stretch([Eq({"s1": F(1), "s2": F(1)}, F(10))])
    assert sol.values["s1"] + sol.values["s2"] == 10
    assert sol.values["s2"] == 0 and sol.ambiguous == ("s2",)


def test_strict_makes_ambiguity_an_error() -> None:
    with pytest.raises(QtError) as ei:
        solve_stretch([Eq({"a": F(1), "b": F(1)}, F(10))], strict=True)
    assert ei.value.code == "E-FE-STRETCH-AMBIGUOUS"


def test_inconsistent_system() -> None:
    with pytest.raises(QtError) as ei:
        solve_stretch([Eq({"s": F(1)}, F(5)), Eq({"s": F(1)}, F(6))])
    assert ei.value.code == "E-FE-STRETCH-INCONSISTENT"


def test_negative_stretch_is_rejected() -> None:
    with pytest.raises(QtError) as ei:
        solve_stretch([Eq({"s": F(1)}, F(-3))])
    assert ei.value.code == "E-FE-STRETCH-INCONSISTENT"


def test_fractional_coefficients_stay_exact() -> None:
    sol = solve_stretch([Eq({"s": F(3)}, F(1))])
    assert sol.values["s"] == F(1, 3)


def test_empty_system() -> None:
    assert solve_stretch([]).values == {}
