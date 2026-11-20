import itertools
import random
from fractions import Fraction as F

import pytest

from qtiming.solve.synth.model import STNU, Contingent, normalise
from qtiming.solve.synth.sc import strongly_controllable


def _mini(d):
    # points: 0=A, 1=C (contingent), 2=X.  (a) C - X <= 0 ; (b) X - C <= D
    return STNU(3, [(2, 1, F(0), "a"), (1, 2, F(d), "b")], [Contingent(0, 1, F(20), F(50), "L")])


def test_worked_example():
    assert not strongly_controllable(_mini(10)).strongly_controllable
    r = strongly_controllable(_mini(30))
    assert r.strongly_controllable and r.schedule[2] - r.schedule[0] == 50
    bad = strongly_controllable(_mini(10))
    assert bad.schedule is None and any(t.startswith("a") for t in bad.witness)


def test_same_link_and_activation_constants():
    link = Contingent(0, 1, F(2), F(5), "L")
    # C - A <= 5 holds, C - A <= 4 does not; A - C <= -2 holds, A - C <= -3 does not
    assert strongly_controllable(STNU(2, [(0, 1, F(5), "r")], [link])).strongly_controllable
    assert not strongly_controllable(STNU(2, [(0, 1, F(4), "r")], [link])).strongly_controllable
    assert strongly_controllable(STNU(2, [(1, 0, F(-2), "r")], [link])).strongly_controllable
    assert not strongly_controllable(STNU(2, [(1, 0, F(-3), "r")], [link])).strongly_controllable
    assert not strongly_controllable(STNU(2, [(1, 1, F(-1), "r")], [link])).strongly_controllable


def test_two_links_row():
    # C1 - C2 <= w needs w >= hi1 - lo2 (A1 - A2 free to shift): choose both links from A1,A2
    links = [Contingent(0, 2, F(1), F(4), "L1"), Contingent(1, 3, F(2), F(3), "L2")]
    ok = STNU(4, [(3, 2, F(2), "r")], links)  # C1 - C2 <= 2
    assert strongly_controllable(ok).strongly_controllable  # shift A1 = A2 - 2
    both = STNU(4, [(3, 2, F(2), "r"), (2, 3, F(-1), "s")], links)  # also C2 - C1 <= -1
    assert not strongly_controllable(both).strongly_controllable


def test_chain_rejected_and_normalised():
    chain = STNU(3, [], [Contingent(0, 1, F(1), F(2), "L1"), Contingent(1, 2, F(1), F(2), "L2")])
    with pytest.raises(ValueError):
        strongly_controllable(chain)
    nrm = normalise(chain)
    assert nrm.n_points == 4 and len(nrm.requirements) == 2
    nrm.validate()
    assert not strongly_controllable(nrm).strongly_controllable  # S = A + theta is not fixed


def _random_sc_case(rng):
    n = rng.randint(2, 6)
    pts = list(range(n))
    rng.shuffle(pts)
    nl = rng.randint(0, min(3, n // 2))
    links = [Contingent(pts[2 * i], pts[2 * i + 1], F(lo := rng.randint(1, 3)),
                        F(lo + rng.randint(0, 3)), f"L{i}") for i in range(nl)]
    reqs = [(rng.randrange(n), rng.randrange(n), F(rng.randint(-6, 8)), f"r{i}")
            for i in range(rng.randint(1, 6))]
    return STNU(n, reqs, links)


def _holds(stnu, times):
    return all(times[v] - times[u] <= w for u, v, w, _ in stnu.requirements)


def test_sc_matches_schedule_for_all_thetas():
    rng = random.Random(7)
    n_sc = 0
    for _ in range(600):
        s = _random_sc_case(rng)
        r = strongly_controllable(s)
        if not r.strongly_controllable:
            assert r.witness
            continue
        n_sc += 1
        for thetas in itertools.product(*[(k.lo, k.hi, (k.lo + k.hi) / 2) for k in s.contingent]):
            times = dict(r.schedule)
            for k, th in zip(s.contingent, thetas, strict=True):
                times[k.c] = times[k.a] + th
            assert _holds(s, times), (s, r.schedule, thetas)
    assert n_sc > 50
