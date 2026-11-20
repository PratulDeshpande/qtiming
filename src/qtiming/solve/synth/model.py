"""STNU data model (convention E: edge (u, v, w, tag) means t_v - t_u <= w)."""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

Edge = tuple[int, int, Fraction, str]


@dataclass(frozen=True)
class Contingent:
    """Contingent link: ``c = a + theta`` with ``theta`` in ``[lo, hi]``; ``a`` is executable."""

    a: int
    c: int
    lo: Fraction
    hi: Fraction
    tag: str = ""


@dataclass
class STNU:
    n_points: int
    requirements: list[Edge] = field(default_factory=list)
    contingent: list[Contingent] = field(default_factory=list)

    def validate(self) -> None:
        """Raise ValueError unless every activation is executable and every end is unique."""
        ends = [k.c for k in self.contingent]
        if len(set(ends)) != len(ends):
            raise ValueError("a contingent end is shared by two links")
        for k in self.contingent:
            if not (0 <= k.a < self.n_points and 0 <= k.c < self.n_points) or k.a == k.c:
                raise ValueError(f"bad link points {k}")
            if k.a in ends:
                raise ValueError(f"activation {k.a} is a contingent end: call normalise()")
            if k.lo > k.hi:
                raise ValueError(f"empty contingent range {k}")
        for u, v, _, _ in self.requirements:
            if not (0 <= u < self.n_points and 0 <= v < self.n_points):
                raise ValueError(f"requirement point out of range: {(u, v)}")


def normalise(stnu: STNU) -> STNU:
    """Add a support node (two zero edges) for every link activated by a contingent end."""
    ends = {k.c for k in stnu.contingent}
    n = stnu.n_points
    reqs = list(stnu.requirements)
    links = []
    for k in stnu.contingent:
        if k.a in ends:
            s = n
            n += 1
            reqs.append((k.a, s, Fraction(0), f"support:{k.tag}"))
            reqs.append((s, k.a, Fraction(0), f"support:{k.tag}"))
            k = Contingent(s, k.c, k.lo, k.hi, k.tag)
        links.append(k)
    return STNU(n, reqs, links)
