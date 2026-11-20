"""Simple temporal networks, convention E: edge (u, v, w, tag) means t_v - t_u <= w."""

from __future__ import annotations

from fractions import Fraction

from qtiming.solve.synth.model import Edge


def bellman_ford(n: int, edges: list[Edge]):
    """Virtual 0-weight source. Returns ``(dist, None)`` or ``(None, cycle_edges)``.

    ``cycle_edges`` is a negative cycle as consecutive edges ``(u, v, w, tag)``.
    """
    dist = [Fraction(0)] * n
    pred: list[tuple[int, Fraction, str] | None] = [None] * n
    last = -1
    if n == 0:
        return dist, None
    for _ in range(n):
        last = -1
        for u, v, w, tag in edges:
            if dist[u] + w < dist[v]:
                dist[v] = dist[u] + w
                pred[v] = (u, w, tag)
                last = v
        if last == -1:
            return dist, None
    v = last
    for _ in range(n):  # n steps back lands on the cycle
        v = pred[v][0]  # type: ignore[index]
    cyc: list[Edge] = []
    x = v
    while True:
        u, w, tag = pred[x]  # type: ignore[misc]
        cyc.append((u, x, w, tag))
        x = u
        if x == v:
            break
    cyc.reverse()
    return None, cyc


def consistent(n: int, edges: list[Edge]) -> bool:
    return bellman_ford(n, edges)[1] is None


def floyd_warshall(n: int, edges: list[Edge]) -> list[list[Fraction | None]] | None:
    """Minimal network (``None`` entry = unbounded), or ``None`` if inconsistent."""
    d: list[list[Fraction | None]] = [[None] * n for _ in range(n)]
    for i in range(n):
        d[i][i] = Fraction(0)
    for u, v, w, _ in edges:
        if d[u][v] is None or w < d[u][v]:  # type: ignore[operator]
            d[u][v] = w
    for k in range(n):
        for i in range(n):
            dik = d[i][k]
            if dik is None:
                continue
            for j in range(n):
                dkj = d[k][j]
                if dkj is not None and (d[i][j] is None or dik + dkj < d[i][j]):  # type: ignore[operator]
                    d[i][j] = dik + dkj
    return None if any(d[i][i] < 0 for i in range(n)) else d  # type: ignore[operator]


def solution(n: int, edges: list[Edge]) -> list[Fraction] | None:
    """A feasible schedule with minimum time 0, or ``None`` if inconsistent."""
    dist, cyc = bellman_ford(n, edges)
    if cyc is not None or not dist:
        return None if cyc is not None else []
    m = min(dist)
    return [t - m for t in dist]
