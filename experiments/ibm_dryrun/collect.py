"""IBM dry-run collector (plan 18.2). Safe by construction:

* default: writes local job SPECS only; no network, no IBM import, nothing submitted;
* `--submit` is the only way to submit, needs credentials in the environment, and ALWAYS passes
  `dry_run=True` (no QPU time). If the returned metadata does not say `dry_run: true`, abort.
There is deliberately no flag to run for real. qiskit / qiskit-ibm-runtime are imported lazily.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

SCHEMA = "qtiming-evidence-job/1"
HERE = Path(__file__).parent


class Runtime(Protocol):
    def submit(self, job_spec: dict[str, Any], *, dry_run: bool) -> dict[str, Any]: ...


def specs() -> list[dict[str, Any]]:
    """Circuit families of plan 18.2 as parametric specs (a, b = arm lengths in dt)."""
    out = [{"id": "ff_base", "family": "ff_base"}]
    for a, b in [(100, 100), (100, 40), (40, 100), (200, 20)]:
        out.append({"id": f"arms_{a}_{b}", "family": "arms_equal" if a == b else "arms_unequal",
                    "arms": {"then_dt": a, "else_dt": b}})
    out.append({"id": "meas_variant_2", "family": "meas_variant", "measure": "measure_2"})
    out.append({"id": "placement_far", "family": "placement", "qubits": [0, 40]})
    out.append({"id": "two_branches", "family": "two_branches"})
    return out


def build_circuit(spec: dict[str, Any]) -> Any:
    """Build the qiskit circuit for a spec (qiskit imported here only, i.e. on --submit)."""
    from qiskit import QuantumCircuit  # noqa: PLC0415

    qc = QuantumCircuit(2, 1)
    qc.measure(0, 0)
    a, b = spec.get("arms", {"then_dt": 50, "else_dt": 0}).values()
    with qc.if_test((qc.clbits[0], 1)) as els:
        qc.delay(a, 1, unit="dt")
        qc.x(1)
    with els:
        qc.delay(b, 1, unit="dt")
    return qc


def load_dotenv(path: Path, env: Any) -> None:
    """Minimal KEY=VALUE reader: fills only unset keys, skips blanks/comments, never logs values."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        k, sep, v = line.strip().partition("=")
        v = v.strip().strip("'\"")
        if sep and v and not k.startswith("#") and k.strip() not in env:
            env[k.strip()] = v


def require_runtime(version: str) -> None:
    """`dry_run` on run() exists from qiskit-ibm-runtime 0.51.0 (IBM dry-run docs)."""
    if tuple(int(p) for p in version.split(".")[:2]) < (0, 51):
        sys.exit(f"qiskit-ibm-runtime {version} is too old: dry-run jobs need >= 0.51.0")


def _rows(timing: str | list[str]) -> list[str]:
    lines = timing.splitlines() if isinstance(timing, str) else timing
    return [ln.strip() for ln in lines if ln.strip()]


def branches_seen(timing: str | list[str]) -> set[str]:
    return {r.split(",")[0] for r in _rows(timing)} & {"then", "else"}


def parse_timing(timing: str | list[str]) -> list[dict[str, Any]]:
    """IBM `scheduler_timing.timing` rows `branch,instr,channel,t0,duration,pulse` -> job schema.

    Keeps measurements (drive `play` start .. readout `capture` end, paired in order per name)
    and every instruction inside a then/else block. shortcut: one conditional block id ("b1")
    for all then/else rows (the dry-run circuits have a single if_test), and unseen row kinds
    are dropped; revisit when the first real job shows whether delays appear as rows.
    """
    out: list[dict[str, Any]] = []
    plays: dict[str, list[tuple[int, int]]] = {}
    caps: dict[str, list[int]] = {}
    for r in _rows(timing):
        f = r.split(",")
        if len(f) != 6 or not (f[3].lstrip("-").isdigit() and f[4].lstrip("-").isdigit()):
            raise ValueError(f"unparseable scheduler_timing row: {r!r}")
        branch, name, t0, dur, pulse = f[0], f[1], int(f[3]), int(f[4]), f[5]
        suffix = name.rsplit("_", 1)[-1]
        qubits = [int(suffix)] if suffix.isdigit() else []
        if name.startswith("measure"):
            if pulse == "play":
                plays.setdefault(name, []).append((t0, t0 + dur))
            elif pulse == "capture":
                caps.setdefault(name, []).append(t0 + dur)
        elif branch in ("then", "else") and pulse not in ("barrier", "shift_phase"):
            out.append({"name": name, "qubits": qubits, "start_dt": t0, "stop_dt": t0 + dur,
                        "block_id": "b1"})
    for name, ps in plays.items():
        for n, (start, stop) in enumerate(ps):
            end = caps.get(name, [])[n:n + 1]
            out.append({"name": name, "qubits": [int(name.rsplit("_", 1)[1])], "start_dt": start,
                        "stop_dt": end[0] if end else stop, "block_id": None})
    return sorted(out, key=lambda i: (i["start_dt"], i["name"]))


class IbmRuntime:
    """Real dry-run submission (qiskit-ibm-runtime >= 0.51, IBM Flex/Premium/On-Prem plan).

    Credentials come from the environment only: QISKIT_IBM_TOKEN, QISKIT_IBM_INSTANCE (CRN),
    optional QISKIT_IBM_BACKEND (default: least busy). `dry_run=True` goes to Sampler.run();
    timing is requested via options.experimental (IBM "Visualize circuit timing" docs).
    """

    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        self.env = os.environ if env is None else env
        self._backend: Any = None

    def _connect(self) -> Any:
        if self._backend is None:
            from qiskit_ibm_runtime import QiskitRuntimeService  # noqa: PLC0415

            svc = QiskitRuntimeService()  # reads QISKIT_IBM_TOKEN / _INSTANCE itself
            name = self.env.get("QISKIT_IBM_BACKEND")
            self._backend = (svc.backend(name) if name
                             else svc.least_busy(operational=True, simulator=False))
        return self._backend

    def submit(self, job_spec: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
        if dry_run is not True:
            raise ValueError("IbmRuntime only submits dry-run jobs")
        import io  # noqa: PLC0415
        from datetime import date  # noqa: PLC0415
        from decimal import Decimal  # noqa: PLC0415
        from hashlib import sha256  # noqa: PLC0415

        import qiskit  # noqa: PLC0415
        from qiskit import qpy  # noqa: PLC0415
        from qiskit.transpiler import generate_preset_pass_manager  # noqa: PLC0415
        from qiskit_ibm_runtime import __version__ as rt_version  # noqa: PLC0415
        from qiskit_ibm_runtime.executor_sampler import Sampler  # noqa: PLC0415

        require_runtime(rt_version)
        backend = self._connect()
        isa = generate_preset_pass_manager(backend=backend, optimization_level=1).run(
            build_circuit(job_spec))
        buf = io.BytesIO()
        qpy.dump(isa, buf)
        sampler = Sampler(backend)
        sampler.options.experimental = {"execution": {"scheduler_timing": True}}
        job = sampler.run([isa], dry_run=True)
        res = job.result()
        timing = res[0].metadata["compilation"]["scheduler_timing"]["timing"]
        if not isinstance(timing, str):
            timing = "\n".join(timing)
        # Evidence that the service really ran it as a dry run: mock device (IBM dry-run docs).
        ran_mock = bool(getattr(job.backend(), "is_mock", False))
        meta: dict[str, Any] = {
            "job_id": job.job_id(), "backend": backend.name, "runtime_version": rt_version,
            "qiskit_version": qiskit.__version__,
            "circuit_qpy_sha256": sha256(buf.getvalue()).hexdigest(),
            "submitted_date": date.today().isoformat(), "dry_run": ran_mock,
            # dt is seconds as a float; Decimal(repr()) avoids binary-float arithmetic.
            "dt_ns": format(Decimal(repr(backend.dt)) * 10**9, "f"),
            "transpiler_options": {"optimization_level": 1},
            "scheduler_timing": {"instructions": parse_timing(timing)},
            "raw_scheduler_timing": timing,
        }
        arms, seen = job_spec.get("arms"), branches_seen(timing)
        # The mock device returns random bits, so `taken` is only known if the schedule shows
        # exactly one arm; otherwise omit `arms` and let join evidence stay UNKNOWN.
        if arms and len(seen) == 1:
            meta["arms"] = {**arms, "taken": next(iter(seen))}
        return meta


def main(argv: list[str] | None = None, *, runtime: Runtime | None = None,
         env: Mapping[str, str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--submit", action="store_true", help="submit with dry_run=True (needs creds)")
    ap.add_argument("--out", help="output dir (default: specs/ for local, jobs/ for --submit)")
    args = ap.parse_args(argv)
    if env is None:  # real run: pick up a gitignored repo-root .env, never overriding the shell
        load_dotenv(HERE.parents[1] / ".env", os.environ)
        env = os.environ
    out = Path(args.out) if args.out else HERE / ("jobs" if args.submit else "specs")

    if not args.submit:
        out.mkdir(parents=True, exist_ok=True)
        for s in specs():
            doc = {"schema": "qtiming-evidence-spec/1", "dry_run": True, "spec": s}
            (out / f"spec_{s['id']}.json").write_text(
                json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote {len(specs())} local specs to {out}; nothing submitted")
        return 0

    if not env.get("QISKIT_IBM_TOKEN"):
        sys.exit("refusing --submit: QISKIT_IBM_TOKEN is not set (no credentials are ever stored)")
    rt = runtime or IbmRuntime(env)
    out.mkdir(parents=True, exist_ok=True)
    for s in specs():
        meta = rt.submit(s, dry_run=True)  # dry_run is hard-wired
        if meta.get("dry_run") is not True:
            sys.exit(f"aborting: backend did not honour dry_run for {s['id']}; nothing saved")
        rec = {"schema": SCHEMA, "family": s["family"], **meta, "dry_run": True}
        (out / f"job_{meta['job_id']}.json").write_text(
            json.dumps(rec, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
