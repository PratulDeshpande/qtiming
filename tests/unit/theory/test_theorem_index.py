"""P15 gate: every theorem id cited in src/ is in Docs/theory/index.md with an allowed status,
and theorems.md carries the same `Status:` line for it."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parents[3]
THEORY = ROOT / "Docs" / "theory"
ALLOWED = {"proved", "proof-sketch", "conjecture", "tested-only", "reduced-statement"}


def _index() -> dict[str, str]:
    rows = {}
    for line in (THEORY / "index.md").read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 3 and re.fullmatch(r"T\d+", cells[0]):
            rows[cells[0]] = cells[2]
    return rows


def _sections() -> dict[str, str]:
    text = (THEORY / "theorems.md").read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r"^## (T\d+)\b(.*?)(?=^## |\Z)", text, re.S | re.M):
        s = re.search(r"^Status: (\S+)\s*$", m.group(2), re.M)
        out[m.group(1)] = s.group(1) if s else ""
    return out


def _cited() -> dict[str, list[str]]:
    cited: dict[str, list[str]] = {}
    for p in (ROOT / "src").rglob("*.py"):
        for tid in set(re.findall(r"\bT(?:10|[1-9])\b", p.read_text(encoding="utf-8"))):
            cited.setdefault(tid, []).append(p.relative_to(ROOT).as_posix())
    return cited


def test_index_statuses_are_allowed() -> None:
    idx = _index()
    assert idx, "no theorem rows found in Docs/theory/index.md"
    bad = {k: v for k, v in idx.items() if v not in ALLOWED}
    assert not bad, f"status not in {sorted(ALLOWED)}: {bad}"


def test_every_cited_theorem_is_indexed_with_a_status_line() -> None:
    idx, sec = _index(), _sections()
    for tid, files in sorted(_cited().items()):
        assert tid in idx, f"{tid} cited in {files} but missing from Docs/theory/index.md"
        assert sec.get(tid) in ALLOWED, f"{tid}: no valid `Status:` line in theorems.md"
        assert sec[tid] == idx[tid], f"{tid}: index says {idx[tid]}, theorems.md says {sec[tid]}"


def test_every_indexed_theorem_has_a_section() -> None:
    sec = _sections()
    for tid, status in _index().items():
        assert sec.get(tid) == status, f"{tid}: theorems.md section/status mismatch"
