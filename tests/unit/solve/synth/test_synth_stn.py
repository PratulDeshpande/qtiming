import random
from fractions import Fraction as F

from qtiming.solve.synth.stn import bellman_ford, consistent, floyd_warshall, solution


def _check_cycle(cyc):
    assert cyc
    for (_, v, _, _), (u2, _, _, _) in zip(cyc, cyc[1:] + cyc[:1], strict=True):
        assert v == u2
    assert sum(e[2] for e in cyc) < 0


def test_consistent_and_solution():
    edges = [(0, 1, F(5), "a"), (1, 0, F(-2), "b"), (1, 2, F(3), "c")]
    dist, cyc = bellman_ford(3, edges)
    assert cyc is None and dist is not None
    sol = solution(3, edges)
    assert min(sol) == 0
    assert all(sol[v] - sol[u] <= w for u, v, w, _ in edges)


def test_self_loop_and_parallel_cycles():
    _, cyc = bellman_ford(2, [(1, 1, F(-1), "loop")])
    assert [e[3] for e in cyc] == ["loop"]
    _, cyc = bellman_ford(2, [(0, 1, F(1), "p1"), (0, 1, F(5), "p2"), (1, 0, F(-2), "q")])
    _check_cycle(cyc)
    assert {e[3] for e in cyc} == {"p1", "q"}
    assert not consistent(2, [(0, 1, F(1), "x"), (1, 0, F(-2), "y")])
    assert bellman_ford(0, []) == ([], None)


def test_random_agreement():
    rng = random.Random(1)
    for _ in range(400):
        n = rng.randint(1, 6)
        edges = [(rng.randrange(n), rng.randrange(n), F(rng.randint(-4, 6)), f"e{i}")
                 for i in range(rng.randint(0, 10))]
        dist, cyc = bellman_ford(n, edges)
        fw = floyd_warshall(n, edges)
        assert (cyc is None) == (fw is not None) == consistent(n, edges)
        if cyc is not None:
            _check_cycle(cyc)
            continue
        sol = solution(n, edges)
        assert all(sol[v] - sol[u] <= w for u, v, w, _ in edges)
        for u, v, w, _ in edges:
            assert fw[u][v] <= w  # minimal network is at least as tight as every edge
