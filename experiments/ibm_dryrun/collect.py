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


class IbmRuntime:
    """Real submission. UNVERIFIED against current qiskit-ibm-runtime (plan 18.1 [verify])."""

    def submit(self, job_spec: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
        import qiskit_ibm_runtime  # noqa: F401, PLC0415

        raise NotImplementedError(
            "capture the real dry_run option name and scheduler_timing schema from the runtime "
            "docs first (plan 18.1 [verify]), then normalise it to qtiming-evidence-job/1")


def main(argv: list[str] | None = None, *, runtime: Runtime | None = None,
         env: Mapping[str, str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--submit", action="store_true", help="submit with dry_run=True (needs creds)")
    ap.add_argument("--out", help="output dir (default: specs/ for local, jobs/ for --submit)")
    args = ap.parse_args(argv)
    env = os.environ if env is None else env
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
    rt = runtime or IbmRuntime()
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
