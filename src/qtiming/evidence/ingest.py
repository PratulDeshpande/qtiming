"""Job schema `qtiming-evidence-job/1` (documented in experiments/ibm_dryrun/README.md).

Stdlib only. Output is byte-reproducible: sorted keys, no generation timestamp, the SHA-256 of
every input recorded. Values read from a schedule are provenance class `sched` (plan decision 15).
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

JOB_SCHEMA = "qtiming-evidence-job/1"
PATCH_SCHEMA = "qtiming-evidence-patch/1"
_REQ = ("schema", "job_id", "backend", "runtime_version", "qiskit_version", "circuit_qpy_sha256",
        "submitted_date", "dry_run", "family", "dt_ns", "scheduler_timing")
_INSTR = ("name", "qubits", "start_dt", "stop_dt", "block_id")


class EvidenceError(ValueError):
    pass


@dataclass(frozen=True)
class Job:
    path: str
    sha256: str
    d: dict[str, Any]

    @property
    def synthetic(self) -> bool:
        return self.d.get("synthetic") is True

    @property
    def dt(self) -> Decimal:
        return Decimal(self.d["dt_ns"])

    @property
    def instrs(self) -> list[dict[str, Any]]:
        return self.d["scheduler_timing"]["instructions"]


def load_job(path: str) -> Job:
    data = Path(path).read_bytes()
    try:
        d = json.loads(data)
    except ValueError as e:
        raise EvidenceError(f"{path}: not JSON ({e})") from e
    miss = [k for k in _REQ if k not in d] if isinstance(d, dict) else list(_REQ)
    if miss:
        raise EvidenceError(f"{path}: missing fields {miss}")
    if d["schema"] != JOB_SCHEMA:
        raise EvidenceError(f"{path}: schema {d['schema']!r}, expected {JOB_SCHEMA!r}")
    if d["dry_run"] is not True:
        raise EvidenceError(f"{path}: dry_run is not true; refusing non-dry-run evidence")
    try:
        if Decimal(d["dt_ns"]) <= 0:
            raise InvalidOperation
    except (InvalidOperation, TypeError) as e:
        raise EvidenceError(f"{path}: dt_ns must be a positive decimal string") from e
    st = d["scheduler_timing"]
    ins = st.get("instructions") if isinstance(st, dict) else None
    if not isinstance(ins, list) or any(
            not isinstance(i, dict) or any(k not in i for k in _INSTR) for i in ins):
        raise EvidenceError(f"{path}: scheduler_timing.instructions needs fields {list(_INSTR)}")
    return Job(path, hashlib.sha256(data).hexdigest(), d)


def _ns(x: Decimal) -> str:
    return format(x.normalize(), "f")


def _is_measure(i: dict[str, Any]) -> bool:
    return str(i["name"]).startswith("measure")


def _blocks(job: Job) -> dict[Any, list[dict[str, Any]]]:
    out: dict[Any, list[dict[str, Any]]] = {}
    for i in job.instrs:
        if i["block_id"] is not None:
            out.setdefault(i["block_id"], []).append(i)
    return out


def derive_ff(job: Job) -> list[Decimal]:
    """Per conditional block: first block start minus end of the latest earlier measure (ns)."""
    obs = []
    for bid, ins in _blocks(job).items():
        start = min(i["start_dt"] for i in ins)
        ends = [i["stop_dt"] for i in job.instrs if _is_measure(i) and i["stop_dt"] <= start]
        if not ends:
            raise EvidenceError(f"{job.path}: block {bid} has no preceding measure")
        obs.append((start - max(ends)) * job.dt)
    return obs


def derive_join(job: Job) -> str | None:
    """'pad' / 'restart' for an unequal-arm job; None if the job cannot tell them apart."""
    arms = job.d.get("arms")
    if not arms or arms["then_dt"] == arms["else_dt"]:
        return None
    longest, taken = max(arms["then_dt"], arms["else_dt"]), arms[f"{arms['taken']}_dt"]
    if taken == longest:
        return None  # both models predict the same block length
    (ins,) = _blocks(job).values()
    extent = max(i["stop_dt"] for i in ins) - min(i["start_dt"] for i in ins)
    return "pad" if extent == longest else "restart" if extent == taken else "other"


def build_patch(jobs: list[Job], *, allow_synthetic: bool = False) -> dict[str, Any]:
    if not jobs:
        raise EvidenceError("no job files given")
    synth = [j.path for j in jobs if j.synthetic]
    if synth and not allow_synthetic:
        raise EvidenceError(f"synthetic job(s) {synth}: pass allow_synthetic to ingest test data")
    ids = [j.d["job_id"] for j in jobs]
    if len(set(ids)) != len(ids):
        raise EvidenceError("duplicate job_id among inputs")
    jobs = sorted(jobs, key=lambda j: (j.d["job_id"], j.sha256))
    tag = "SYNTHETIC TEST DATA, not hardware; " if synth else ""
    who = (f"backends={sorted({j.d['backend'] for j in jobs})} "
           f"runtime={sorted({j.d['runtime_version'] for j in jobs})}")

    groups: dict[tuple[str, str], list[tuple[Job, Decimal]]] = {}
    for j in jobs:
        tier = j.d.get("tier", "default")
        key = j.d.get("latency_key") or f"ff.{tier}"
        for o in derive_ff(j):
            groups.setdefault((key, tier), []).append((j, o))
    lats = []
    for (key, tier), obs in sorted(groups.items()):
        vals = [o for _, o in obs]
        n = len({j.d["job_id"] for j, _ in obs})
        lats.append({"key": key, "src": "measure", "dst": "branch", "tier": tier,
                     "lo_ns": _ns(min(vals)), "hi_ns": _ns(max(vals)), "data_dependent": False,
                     "prov": "sched", "n": n,
                     "source": f"{tag}scheduler_timing dry_run jobs, n={n}; min/max; {who}"})

    votes = [v for v in (derive_join(j) for j in jobs) if v is not None]
    ibm: dict[str, Any] = {}
    if votes and len(set(votes)) == 1 and votes[0] in ("pad", "restart"):
        ibm["join_behavior"] = "pad_to_longest_block" if votes[0] == "pad" else "restart_at_join"
        ibm["join_behavior_prov"] = {
            "prov": "sched",
            "source": f"{tag}{len(votes)} unequal-arm job(s) all show {votes[0]}; {who}"}
    elif votes:  # conflicting or unrecognised: record the result, do not choose
        ibm["join_behavior_prov"] = {
            "prov": "vendor",
            "source": f"{tag}inconclusive: unequal-arm jobs gave {sorted(votes)}; "
                      f"join_behavior left unchanged; {who}"}

    patch: dict[str, Any] = {"patch": {"schema": PATCH_SCHEMA, "synthetic": bool(synth)}}
    if lats:
        patch["latency"] = lats
    if ibm:
        patch["personality_params"] = {"ibm": ibm}
    patch["evidence"] = [
        {"job_id": j.d["job_id"], "file": Path(j.path).name, "sha256": j.sha256,
         "backend": j.d["backend"], "family": j.d["family"],
         "runtime_version": j.d["runtime_version"], **({"synthetic": True} if j.synthetic else {})}
        for j in jobs]
    return patch


def _val(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, str):
        return json.dumps(v)
    raise EvidenceError(f"cannot emit {type(v).__name__} as TOML")


def emit_toml(d: dict[str, Any]) -> str:
    """Minimal deterministic TOML: scalars, nested tables, arrays of tables; sorted keys."""
    out: list[str] = []

    def table(t: dict[str, Any], path: tuple[str, ...], aot: bool) -> None:
        scal = [k for k in sorted(t) if not isinstance(t[k], (dict, list))]
        if path and (scal or not any(isinstance(v, (dict, list)) for v in t.values())):
            out.extend(["", f"[[{'.'.join(path)}]]" if aot else f"[{'.'.join(path)}]"])
        out.extend(f"{k} = {_val(t[k])}" for k in scal)
        for k in sorted(t):
            if isinstance(t[k], dict):
                table(t[k], (*path, k), False)
            elif isinstance(t[k], list):
                for item in t[k]:
                    table(item, (*path, k), True)

    table(d, (), False)
    return "\n".join(out).lstrip("\n") + "\n"


def ingest(files: list[str | Path], *, allow_synthetic: bool = False) -> str:
    jobs = [load_job(str(f)) for f in files]
    return emit_toml(build_patch(jobs, allow_synthetic=allow_synthetic))


def report(files: list[str | Path]) -> str:
    jobs = [load_job(str(f)) for f in files]
    lines = ["job_id  family  backend  observed_ff_ns  join"]
    for j in sorted(jobs, key=lambda j: j.d["job_id"]):
        ff = ",".join(_ns(o) for o in derive_ff(j))
        lines.append(f"{j.d['job_id']}  {j.d['family']}  {j.d['backend']}  {ff}  "
                     f"{derive_join(j) or '-'}{'  [SYNTHETIC]' if j.synthetic else ''}")
    return "\n".join(lines) + "\n"


def apply_patch(contract: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """New contract dict: latencies replaced by key (or appended), params merged, evidence added."""
    out = copy.deepcopy(contract)
    lats = out.setdefault("latency", [])
    for new in copy.deepcopy(patch.get("latency", [])):
        for i, old in enumerate(lats):
            if old.get("key") == new["key"]:
                lats[i] = new
                break
        else:
            lats.append(new)

    def merge(dst: dict[str, Any], src: dict[str, Any]) -> None:
        for k, v in src.items():
            if isinstance(v, dict) and isinstance(dst.get(k), dict):
                merge(dst[k], v)
            else:
                dst[k] = copy.deepcopy(v)

    merge(out.setdefault("personality_params", {}), patch.get("personality_params", {}))
    out.setdefault("evidence", []).extend(copy.deepcopy(patch.get("evidence", [])))
    return out
