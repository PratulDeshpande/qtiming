"""Oracle (bruteforce_dc) and Morris DC checker: hierarchy SC => DC => WC, and exact agreement."""

import random
from fractions import Fraction as F

from qtiming.solve.synth.bruteforce_dc import dc, sc_bruteforce, wc_bruteforce
from qtiming.solve.synth.model import STNU, Contingent
from qtiming.solve.synth.sc import strongly_controllable


def make(n, reqs, links):
    return STNU(n, [(u, v, F(w), f"r{i}") for i, (u, v, w) in enumerate(reqs)],
                [Contingent(a, c, F(lo), F(hi), f"L{i}") for i, (a, c, lo, hi) in enumerate(links)])


def random_stnu(rng, max_points=6):
    n = rng.randint(3, max_points)
    pts = list(range(n))
    rng.shuffle(pts)
    nl = rng.randint(1, min(3, n // 2))
    links = []
    for i in range(nl):
        lo = rng.randint(1, 3)
        links.append((pts[2 * i], pts[2 * i + 1], lo, lo + rng.randint(1, 3)))
    reqs = []
    for _ in range(rng.randint(2, 6)):
        u, v = rng.sample(range(n), 2)
        reqs.append((u, v, rng.randint(-5, 6)))
    return make(n, reqs, links)


H = 14


def test_oracle_known_cases():
    link = [(0, 1, 2, 5)]
    # X = C reactive: C - X <= 0 and X - C <= 0 -> DC but not SC
    s = make(3, [(2, 1, 0), (1, 2, 0)], link)
    assert dc(s, H) and not sc_bruteforce(s, H) and wc_bruteforce(s)
    # X - C <= -1 (X strictly before C) -> not DC
    s = make(3, [(1, 2, -1), (2, 0, -3)], link)  # A+3 <= X <= C-1, C may be A+2
    assert not dc(s, H)
    # X in [C, C+3]: hi - lo = 3 <= 3 -> SC and DC
    s = make(3, [(2, 1, 0), (1, 2, 3)], link)
    assert sc_bruteforce(s, H) and dc(s, H)
    # impossible requirement among executables
    s = make(4, [(0, 2, 1), (2, 0, -3)], link)
    assert not dc(s, H) and not wc_bruteforce(s)


def test_hierarchy_sc_dc_wc():
    rng = random.Random(11)
    seen = {"sc": 0, "dc_only": 0, "wc_only": 0, "none": 0}
    for _ in range(250):
        s = random_stnu(rng, 5)
        sc, d, w = sc_bruteforce(s, 9), dc(s, 9), wc_bruteforce(s)
        assert (not sc or d) and (not d or w), (s, sc, d, w)
        if sc:  # fast Vidal-Fargier agrees with brute-force SC (integer schedules in [0, 9])
            assert strongly_controllable(s).strongly_controllable, s
        seen["sc" if sc else "dc_only" if d else "wc_only" if w else "none"] += 1
    assert min(seen.values()) > 0, seen


def test_morris_agrees_with_bruteforce():
    from qtiming.solve.synth import stnu_dc

    assert stnu_dc.UNVERIFIED is True
    rng = random.Random(2024)
    stats = {True: 0, False: 0}
    bad = []
    for _ in range(1500):
        s = random_stnu(rng, 6)
        want = dc(s, 24)  # horizon must exceed the longest chain (seed 2024 needs > 16)
        got = stnu_dc.dynamically_controllable(s)
        stats[want] += 1
        if got.dc != want:
            bad.append((s, want, got))
        assert (got.reason is None) == got.dc
    print(stats, len(bad))
    assert not bad, bad[:3]
    assert min(stats.values()) > 200, stats
