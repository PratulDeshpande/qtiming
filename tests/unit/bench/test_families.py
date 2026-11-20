"""P13 benchmark suite: deterministic generation, no `error` cells, golden regression, H1 diff,
ground truth, report tables, the manifest and the per-cell timeout."""

from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import pytest

pytest.importorskip("openqasm3")
from qtiming.bench import main  # noqa: E402

ROOT = Path(__file__).parents[3]
SUITE = ROOT / "benchmarks" / "families"
COUNTS = {"teleportation": 6, "active_reset": 4, "long_range_cnot": 8, "rus": 8, "qec": 12,
          "magic_state": 6, "lattice_surgery": 6, "artiq": 6}


def _gen():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("gen_families", ROOT / "benchmarks"
                                                  / "gen_families.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_generation_is_deterministic_and_matches_disk() -> None:
    a, b = _gen().render(), _gen().render()
    assert {k: v.encode() for k, v in a.items()} == {k: v.encode() for k, v in b.items()}
    assert _gen().main(["--check"]) == 0  # the committed files are what the generator writes


def test_family_counts_and_metadata() -> None:
    for fam, n in COUNTS.items():
        files = sorted((SUITE / fam).glob("*.qasm"))
        meta = json.loads((SUITE / fam / "meta.json").read_text(encoding="utf-8"))
        assert len(files) == n, fam
        assert sorted(meta) == [f.stem for f in files], fam
        assert all(m["licence"] == "Apache-2.0" and m["provenance"] for m in meta.values())
    assert not list((SUITE / "dynamarq").glob("*.qasm"))  # external, unavailable: no fakes
    assert "intentionally empty" in (SUITE / "dynamarq" / "README.md").read_text(encoding="utf-8")
    for f in (SUITE / "artiq").glob("*.qasm"):
        assert "NOT external code" in f.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def full_run(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("run")
    assert main(["run", "--suite", str(SUITE), "--contracts", "all", "--policies", "eq,sync,exp",
                 "--repeat", "1", "--out", str(out)]) == 0  # exit 1 would mean an `error` cell
    return out


def test_no_error_cells_and_manifest(full_run: Path) -> None:
    rows = [json.loads(x) for x in (full_run / "results.jsonl").read_text("utf-8").splitlines()]
    assert len(rows) == 56 * 4 * 3
    assert {r["status"] for r in rows} <= {"PROVED", "PROVED-UNDER", "REFUTED", "UNKNOWN",
                                           "unsupported"}
    man = json.loads((full_run / "manifest.json").read_text(encoding="utf-8"))
    assert man["python"] and len(man["contracts_sha256"]) == 4
    assert all(len(h) == 64 for h in man["contracts_sha256"].values())
    assert "git_commit" in man and man["unroll_limit"] == 16


def test_golden_expectations_match(full_run: Path) -> None:
    # benchmarks/expected.json is a regression snapshot of the checker, not independent truth
    golden = ROOT / "benchmarks" / "expected.json"
    assert main(["check", str(full_run), "--golden", str(golden)]) == 0


def test_report_tables(full_run: Path, tmp_path: Path) -> None:
    assert main(["report", str(full_run), "--tables", str(tmp_path),
                 "--truth", str(SUITE / "ground_truth.json")]) == 0
    md = (tmp_path / "verdicts_per_contract.md").read_text(encoding="utf-8")
    assert "ibm_heron" in md and "PROVED-UNDER" in md
    for name in ("tier_mix", "assumption_census", "portability", "headline_provenance",
                 "h2_precision"):
        assert (tmp_path / f"{name}.csv").is_file()


def test_diff_h1_zero_violations(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["diff", "--runs", "200", "--seed", "1", "--programs", "3",
                 "--out", str(tmp_path)]) == 0
    d = json.loads((tmp_path / "diff.json").read_text(encoding="utf-8"))
    assert d["violating_runs_total"] == 0 and d["failures"] == []
    assert sum(s["proved_cells"] for s in d["per_personality"].values()) > 0  # not vacuous
    assert "H1: 0 violating runs" in capsys.readouterr().out


def test_truth_is_stable_and_matches_committed(tmp_path: Path) -> None:
    sub = tmp_path / "suite" / "active_reset"
    sub.mkdir(parents=True)
    for n in ("reset_basic", "reset_parallel"):
        shutil.copy(SUITE / "active_reset" / f"{n}.qasm", sub)
    outs = []
    for i in (1, 2):
        out = tmp_path / f"gt{i}.json"
        assert main(["truth", "--suite", str(tmp_path / "suite"), "--contracts", "ibm_heron",
                     "--out", str(out)]) == 0
        outs.append(out.read_bytes())
    assert outs[0] == outs[1]
    got = json.loads(outs[0])["truth"]
    want = json.loads((SUITE / "ground_truth.json").read_text(encoding="utf-8"))["truth"]
    assert got and all(want[k] == v for k, v in got.items())


def test_timeout_marks_cell_not_error(tmp_path: Path) -> None:
    assert main(["run", "--suite", str(SUITE / "active_reset"), "--contracts", "ibm_heron",
                 "--policies", "eq", "--timeout", "0.01", "--out", str(tmp_path)]) == 0
    rows = [json.loads(x) for x in (tmp_path / "results.jsonl").read_text("utf-8").splitlines()]
    assert rows and {r["status"] for r in rows} == {"timeout"}
