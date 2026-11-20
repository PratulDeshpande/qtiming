"""`qtiming-bench` (plan P13, 17.4): run a suite over contracts and policies, compare to golden
verdicts, exhaustive ground truth, the H1 differential and the report tables.

    qtiming-bench run --suite benchmarks/families --contracts all --policies eq,sync,exp \
        --repeat 5 --timeout 60 --out results/<run-id>/
    qtiming-bench check results/<run-id>/ --golden benchmarks/expected.json [--update]
    qtiming-bench truth --suite benchmarks/families --out benchmarks/families/
    qtiming-bench diff --runs 10000 --seed 1 --out results/<run-id>/diff/
    qtiming-bench report results/<run-id>/ --tables paper/tables/

A cell is one (program, contract, policy). Its status is the verdict, or `unsupported` when the
contract lacks data the program needs (E-CT-MISSING, E-GRAPH-UNSUPPORTED, ...), `timeout` when
it ran past `--timeout`, or `error` for anything else, so a gap is reported and never silently
skipped. `ms` is the median over `--repeat` runs. `--out` is a directory (results.jsonl,
manifest.json, and results.parquet when pyarrow is installed) or a `.jsonl` file path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import platform
import queue
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from qtiming.contract.loader import ContractLoadError, load_contract
from qtiming.core.errors import QtError

INSTANCES = Path(__file__).resolve().parents[1] / "contract" / "instances"
_UNSUPPORTED = ("E-CT-MISSING", "E-GRAPH-UNSUPPORTED", "E-ELAB-UNSUPPORTED", "E-GRAPH-CUT",
                "E-ELAB-LOOP-LIMIT", "E-ELAB-Q1-NOT-EQUALISABLE", "E-ELAB-EQ-VARIABLE-ARM")


def programs(suite: Path) -> list[Path]:
    return sorted(suite.rglob("*.qasm"))


def contracts(names: str) -> list[str]:
    if names == "all":
        return sorted(p.stem for p in INSTANCES.glob("*.toml"))
    return [n for n in names.split(",") if n]


def load_cell(prog: Path, contract: str, assume: tuple[str, ...] = ()) -> Any:
    """(contract, program) for one cell; the program is parsed under that contract's dt."""
    from qtiming.frontend import from_qasm3

    c = load_contract(str(INSTANCES / f"{contract}.toml"), assume=assume)
    return c, from_qasm3(prog.read_text(encoding="utf-8"), filename=str(prog), contract=c)


def _tier_mix(v: Any) -> dict[str, int]:
    mix: dict[str, int] = {}
    for r in v.results:
        k = "none" if r.res.tier is None else f"tier{r.res.tier}"
        mix[k] = mix.get(k, 0) + 1
    return mix


def _provenance_counts(v: Any, c: Any) -> tuple[int, int]:
    """(assumptions weaker than cycle-counted, of which rest on a placeholder number)."""
    from qtiming.core.provenance import ProvClass

    weak = [a for a in v.assumptions if a.prov.cls < ProvClass.CYC]
    ph = 0
    for a in weak:
        try:
            ph += bool(c.latency(a.key).placeholder)
        except (KeyError, QtError):
            pass
    return len(weak), ph


UNROLL_LIMIT = 16  # below the 20-round QEC programs, so those are windowed (plan 17.1)


def run_cell(prog: Path, contract: str, policy: str, repeat: int,
             assume: tuple[str, ...] = (), unroll_limit: int = UNROLL_LIMIT) -> dict[str, Any]:
    from qtiming.verdict.run import check_program

    rec: dict[str, Any] = {"program": prog.stem, "family": prog.parent.name,
                           "contract": contract, "policy": policy}
    times: list[float] = []
    try:
        c, p = load_cell(prog, contract, assume)
        for _ in range(max(1, repeat)):
            t0 = time.perf_counter()
            v = check_program(p.body, c, policy=policy, unroll_limit=unroll_limit)
            times.append((time.perf_counter() - t0) * 1000)
        weak, ph = _provenance_counts(v, c)
        rec |= {"status": v.verdict, "obligations": len(v.results), "tiers": _tier_mix(v),
                "weakest_class": v.weakest_class,
                "assumptions": [a.key for a in v.assumptions], "uncertified": weak,
                "placeholders": ph, "reasons": list(v.reasons)[:3]}
    except ContractLoadError as e:  # a QtError subclass: must come first
        rec |= {"status": "error", "reasons": [str(x) for x in e.errors][:3]}
    except QtError as e:
        rec |= {"status": "unsupported" if e.code in _UNSUPPORTED else "error",
                "reasons": [f"{e.code}: {e.message}"]}
    except Exception as e:  # a checker crash (an assert, ...) is an `error` cell, not a dead run
        rec |= {"status": "error", "reasons": [f"internal {type(e).__name__}: {e}"]}
    rec["ms"] = round(statistics.median(times), 3) if times else None
    return rec


def key(r: dict[str, Any]) -> str:
    return f"{r['family']}/{r['program']}|{r['contract']}|{r['policy']}"


# ---------------------------------------------------------------- isolated workers (--timeout)
def _serve(conn: Any) -> None:
    while True:
        job = conn.recv()
        if job is None:
            return
        try:
            conn.send(run_cell(*job))
        except Exception as e:  # reported as an error cell, never a crash of the worker
            conn.send({"program": job[0].stem, "family": job[0].parent.name, "contract": job[1],
                       "policy": job[2], "status": "error",
                       "reasons": [f"{type(e).__name__}: {e}"], "ms": None})


class _Worker:
    def __init__(self) -> None:
        ctx = mp.get_context("spawn")
        self.conn, child = ctx.Pipe()
        self.proc = ctx.Process(target=_serve, args=(child,), daemon=True)
        self.proc.start()

    def run(self, job: tuple[Any, ...], timeout: float) -> dict[str, Any] | None:
        self.conn.send(job)
        return self.conn.recv() if self.conn.poll(timeout) else None  # type: ignore[no-any-return]

    def kill(self) -> None:
        self.proc.kill()
        self.proc.join()

    def close(self) -> None:
        try:
            self.conn.send(None)
        except OSError:
            pass
        self.proc.join(5)


def run_cells(jobs: list[tuple[Any, ...]], timeout: float, workers: int) -> list[dict[str, Any]]:
    """Cells in order. timeout <= 0: inline, no isolation. Else a worker process per thread,
    killed and replaced when a cell passes `timeout` seconds (status `timeout`)."""
    if timeout <= 0:
        return [run_cell(*j) for j in jobs]
    todo: queue.Queue[int] = queue.Queue()
    for i in range(len(jobs)):
        todo.put(i)
    out: list[dict[str, Any] | None] = [None] * len(jobs)

    def loop() -> None:
        w = _Worker()
        try:
            while True:
                try:
                    i = todo.get_nowait()
                except queue.Empty:
                    return
                prog, contract, policy = jobs[i][:3]
                got = w.run(jobs[i], timeout)
                if got is None:
                    w.kill()
                    w = _Worker()
                    got = {"program": prog.stem, "family": prog.parent.name, "contract": contract,
                           "policy": policy, "status": "timeout",
                           "reasons": [f"no verdict within {timeout:g} s"], "ms": None}
                out[i] = got
        finally:
            w.close()

    threads = [threading.Thread(target=loop) for _ in range(max(1, workers))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return [r for r in out if r is not None]


# ---------------------------------------------------------------- manifest, outputs
def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str | None:
    try:
        r = subprocess.run(["git", *args], capture_output=True, text=True, timeout=20,
                           cwd=Path(__file__).parent, check=False)
        return r.stdout.strip() if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def _version(pkg: str) -> str | None:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version(pkg)
    except PackageNotFoundError:
        return None


def manifest(argv: list[str], names: list[str]) -> dict[str, Any]:
    return {
        "git_commit": _git("rev-parse", "HEAD"),
        "git_dirty": bool(_git("status", "--porcelain")),
        "python": sys.version.split()[0],
        "platform": platform.platform(), "cpu": platform.processor(),
        "versions": {p: _version(p) for p in ("qiskit", "z3-solver", "openqasm3", "pyarrow",
                                              "qtiming")},
        "contracts_sha256": {n: _sha(INSTANCES / f"{n}.toml") for n in names},
        "fixtures_sha256": {p.name: _sha(p) for p in sorted(INSTANCES.glob("*.json"))},
        "argv": argv,
    }


def out_paths(out: str) -> tuple[Path, Path]:
    """(results file, directory) for `--out`: a directory, or a .jsonl file path."""
    p = Path(out)
    if p.suffix == ".jsonl":
        return p, p.parent
    return p / "results.jsonl", p


def write_rows(rows: list[dict[str, Any]], out: str) -> Path:
    f, d = out_paths(out)
    d.mkdir(parents=True, exist_ok=True)
    f.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    try:  # Parquet only when pyarrow is installed (the `bench` extra); JSONL is always written
        import pyarrow as pa  # type: ignore[import-not-found,unused-ignore]
        import pyarrow.parquet as pq  # type: ignore[import-not-found,unused-ignore]

        pq.write_table(pa.Table.from_pylist(rows), f.with_suffix(".parquet"))
    except ImportError:
        pass
    return d


def read_rows(path: str) -> list[dict[str, Any]]:
    p = Path(path)
    p = p / "results.jsonl" if p.is_dir() else p
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


# ---------------------------------------------------------------- commands
def _run(a: argparse.Namespace) -> int:
    assume = tuple(a.assume or ())
    names = contracts(a.contracts)
    jobs = [(p, c, pol, a.repeat, assume, a.unroll_limit)
            for p in programs(Path(a.suite)) for c in names
            for pol in a.policies.split(",")]
    cells = run_cells(jobs, a.timeout, a.jobs)
    if a.out:
        d = write_rows(cells, a.out)
        m = manifest(sys.argv[1:] if a.argv is None else a.argv, names)
        m["assume"] = list(assume)
        m["unroll_limit"] = a.unroll_limit
        (d / "manifest.json").write_text(json.dumps(m, indent=1) + "\n", encoding="utf-8")
    counts: dict[str, int] = {}
    for r in cells:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print(f"{len(cells)} cells: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    return 1 if counts.get("error") else 0


def _check(a: argparse.Namespace) -> int:
    got = {key(r): r["status"] for r in read_rows(a.results)}
    golden = Path(a.golden)
    if a.update:
        golden.write_text(json.dumps(dict(sorted(got.items())), indent=1) + "\n", encoding="utf-8")
        print(f"wrote {len(got)} expectations to {golden}")
        return 0
    want: dict[str, str] = json.loads(golden.read_text(encoding="utf-8"))
    bad = [(k, want.get(k), got.get(k)) for k in sorted(set(want) | set(got))
           if want.get(k) != got.get(k)]
    for k, w, g in bad:
        print(f"MISMATCH {k}: expected {w}, got {g}")
    print(f"{len(got) - len(bad)} of {len(got)} cells match the golden file")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    from . import diff, report, truth

    ap = argparse.ArgumentParser(prog="qtiming-bench")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="verdict for every (program, contract, policy) cell")
    r.add_argument("--suite", default="benchmarks/families")
    r.add_argument("--contracts", default="all")
    r.add_argument("--policies", default="eq,sync,exp")
    r.add_argument("--repeat", type=int, default=1)
    r.add_argument("--timeout", type=float, default=0,
                   help="seconds per cell, enforced in a worker process (0: inline, no limit)")
    r.add_argument("--jobs", type=int, default=1, help="worker processes (with --timeout)")
    r.add_argument("--assume", action="append", metavar="KEY=VALUE",
                   help="contract override, as `qtiming check --assume`; recorded in the manifest")
    r.add_argument("--unroll-limit", type=int, default=UNROLL_LIMIT,
                   help="loops longer than this are windowed (IBM) or refused, not unrolled")
    r.add_argument("--out", help="results directory (or a .jsonl path)")
    r.set_defaults(fn=_run, argv=argv)
    c = sub.add_parser("check", help="compare a run with the golden regression snapshot")
    c.add_argument("results")
    c.add_argument("--golden", default="benchmarks/expected.json")
    c.add_argument("--update", action="store_true")
    c.set_defaults(fn=_check)
    truth.add_parser(sub)
    diff.add_parser(sub)
    report.add_parser(sub)
    a = ap.parse_args(argv)
    return int(a.fn(a))


if __name__ == "__main__":
    sys.exit(main())
