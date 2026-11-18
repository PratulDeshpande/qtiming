"""The free-time-point STN encoding of an ARTIQ-like program: a FALSE PROOF (plan A.7 to A.9).

If event times are free variables constrained only by differences, the scheduler may pick any
commit time that satisfies `commit - issue >= lead`, so the network is always consistent. The
fixed-dispatch semantics stamps the commit at the cursor, which does NOT move when the CPU is
late, and so can underflow. Kept as a fixture to show why the checker verifies a fixed dispatch.
"""

from __future__ import annotations

from fractions import Fraction


def stn_consistent(n: int, constraints: list[tuple[int, int, Fraction]]) -> bool:
    """Difference constraints x_j - x_i <= w, as (i, j, w). Consistent iff no negative cycle."""
    dist = [Fraction(0)] * n
    for _ in range(n):
        changed = False
        for i, j, w in constraints:
            if dist[i] + w < dist[j]:
                dist[j] = dist[i] + w
                changed = True
        if not changed:
            return True
    return False


def artiq_free_stn(cursor_stamp: int, cpu_issue_lo: int, cpu_issue_hi: int, lead: int) -> bool:
    """Variables: 0 origin, 1 issue, 2 commit. Free commit: only `commit - issue >= lead`."""
    c: list[tuple[int, int, Fraction]] = [
        (0, 1, Fraction(cpu_issue_hi)),  # issue - origin <= hi
        (1, 0, Fraction(-cpu_issue_lo)),  # origin - issue <= -lo
        (2, 1, Fraction(-lead)),  # issue - commit <= -lead
    ]
    del cursor_stamp  # a FREE commit time ignores the stamp: that is the unsoundness
    return stn_consistent(3, c)
