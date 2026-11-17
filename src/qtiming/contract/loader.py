"""TOML/JSON -> validated, frozen Contract (Section 7.5).

Never fills a default that silently weakens an obligation: absent required numbers are
recorded in `Contract.missing` and dependants become UNKNOWN downstream.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
from dataclasses import fields, is_dataclass, replace
from enum import Enum
from fractions import Fraction
from typing import Any

from pydantic import ValidationError

from qtiming.core.errors import QtError
from qtiming.core.provenance import Prov, ProvClass
from qtiming.core.time import Interval, Latency, ns_to_dt

from .model import BranchSpec, Contract, ContractLatency, IssueCost
from .schema import PROV, ContractIn, frac
from .target_import import snapshot_from_target

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover  (3.10 backport)
    import tomli as tomllib  # type: ignore[no-redef]

_REQUIRED_COMMIT_LEAD = {"artiq"}


class ContractLoadError(QtError):
    """All problems found in one contract, not just the first."""

    def __init__(self, errors: list[QtError]) -> None:
        code = errors[0].code if len({e.code for e in errors}) == 1 else "E-CT-SCHEMA"
        super().__init__(code, "; ".join(f"[{e.code}] {e.message}" for e in errors))
        self.errors = errors


def load_contract(path: str, *, target: Any = None, assume: tuple[str, ...] = ()) -> Contract:
    with open(path, "rb") as fh:
        data = fh.read()
    raw = json.loads(data) if path.endswith(".json") else tomllib.loads(data.decode("utf-8"))
    return load_contract_dict(
        raw, base_dir=os.path.dirname(os.path.abspath(path)), target=target, assume=assume
    )


def _freeze(v: Any) -> Any:
    if isinstance(v, dict):
        return tuple(sorted((str(k), _freeze(x)) for k, x in v.items()))
    if isinstance(v, list):
        return tuple(_freeze(x) for x in v)
    return v


def _canon(o: Any) -> Any:
    if is_dataclass(o) and not isinstance(o, type):
        return {f.name: _canon(getattr(o, f.name)) for f in fields(o)}
    if isinstance(o, Fraction):
        return str(o)
    if isinstance(o, Enum):
        return o.name
    if isinstance(o, (tuple, list)):
        return [_canon(x) for x in o]
    if isinstance(o, dict):
        return {str(k): _canon(v) for k, v in o.items()}
    return o


def _apply_assume(raw: dict[str, Any], assume: tuple[str, ...], errs: list[QtError]) -> None:
    for a in assume:
        key, sep, val = a.partition("=")
        if not sep or not key or not val:
            errs.append(QtError("E-CT-ASSUME", f"--assume {a!r}: expected key=value"))
            continue
        if key == "timeline.commit_lead":
            raw.setdefault("timeline", {})["commit_lead"] = val
            continue
        parts = val.split(":")
        cls = parts[2] if len(parts) > 2 else "vendor"
        if cls != "vendor":
            errs.append(QtError("E-CT-ASSUME", f"--assume {a!r}: only class 'vendor' is allowed"))
            continue
        new = {
            "lo_ns": parts[0],
            "hi_ns": parts[1] if len(parts) > 1 and parts[1] != "" else None,
            "prov": "vendor",
            "source": f"--assume {a}",
            "placeholder": True,
        }
        lats = raw.setdefault("latency", [])
        for i, old in enumerate(lats):
            if old.get("key") == key:
                keep = {k: v for k, v in old.items() if k not in ("n", "p", "load", "k_sigma")}
                lats[i] = {**keep, **new}
                break
        else:
            lats.append({"key": key, "src": "assume", "dst": "assume", **new})


def _read_snapshot(tgt: dict[str, Any], base_dir: str | None, target: Any) -> dict[str, Any] | None:
    src = str(tgt.get("source", "none"))
    if target is not None:
        if isinstance(target, dict):
            return target
        return snapshot_from_target(target, str(tgt.get("backend", "unknown")))
    if src.startswith("snapshot:"):
        path = os.path.join(base_dir or os.getcwd(), src[len("snapshot:"):])
        try:
            with open(path, encoding="utf-8") as fh:
                snap: dict[str, Any] = json.load(fh)
        except OSError as e:
            raise QtError("E-CT-TARGET", f"cannot read target snapshot {path!r}: {e}") from e
        return snap
    return None


def load_contract_dict(
    raw: dict[str, Any],
    *,
    base_dir: str | None = None,
    target: Any = None,
    assume: tuple[str, ...] = (),
) -> Contract:
    raw = copy.deepcopy(raw)
    errs: list[QtError] = []
    _apply_assume(raw, assume, errs)
    try:
        c = ContractIn.model_validate(raw)
    except ValidationError as ve:
        for e in ve.errors():
            path = ".".join(str(p) for p in e["loc"])
            errs.append(QtError("E-CT-SCHEMA", f"{path}: {e['msg']}"))
        raise ContractLoadError(errs) from None
    if errs:
        raise ContractLoadError(errs)

    warns: list[str] = []
    personality = c.meta.personality

    # -- target snapshot, dt ------------------------------------------------------------
    snapshot: dict[str, Any] | None = None
    if c.target is not None:
        try:
            snapshot = _read_snapshot(c.target, base_dir, target)
        except QtError as e:
            errs.append(e)
    imports = set(c.target.get("import", ["dt", "alignments", "durations"])) if c.target else set()

    dt: Fraction | None = None
    raw_dt = c.timebase.dt_ns
    if raw_dt == "from_target":
        if snapshot is None:
            errs.append(QtError("E-CT-TARGET", "dt_ns = 'from_target' but no Target was supplied",
                                hint="pass a Target, or set [target] source = 'snapshot:<file>'"))
        else:
            dt = Fraction(str(snapshot["dt_ns"]))
    else:
        try:
            dt = frac(raw_dt)
        except ValueError:
            errs.append(QtError("E-CT-SCHEMA", f"timebase.dt_ns: {raw_dt!r} is not a decimal"))
        if dt is not None and snapshot is not None and "dt" in imports:
            if dt != Fraction(str(snapshot["dt_ns"])):
                errs.append(QtError("E-CT-TARGET-CONFLICT",
                                    f"timebase.dt_ns = {raw_dt} disagrees with Target "
                                    f"dt = {snapshot['dt_ns']} ns"))
    if dt is not None and dt <= 0:
        errs.append(QtError("E-CT-SCHEMA", "timebase.dt_ns must be > 0"))
        dt = None
    if dt is None:
        raise ContractLoadError(errs)

    grid = dict(c.timebase.grid)
    if snapshot is not None and "alignments" in imports:
        for k, v in snapshot.get("alignments", {}).items():
            if k in grid and grid[k] != v:
                errs.append(QtError("E-CT-TARGET-CONFLICT",
                                    f"grid.{k} = {grid[k]} disagrees with Target ({v})"))
            grid[k] = int(v)

    # -- durations (role: exact) --------------------------------------------------------
    target_durs: dict[str, int] = {}
    if snapshot is not None and "durations" in imports:
        for name, ns in snapshot.get("durations_ns", {}).items():
            try:
                target_durs[name] = ns_to_dt(Fraction(str(ns)), dt, "exact",
                                             what=f"Target duration {name}")
            except QtError as e:
                errs.append(e)
    durs: dict[str, int] = dict(target_durs) if c.durations.get("import_from_target") else {}
    overrides: list[str] = []
    for name, v in c.durations.items():
        if name == "import_from_target":
            continue
        override, reason = False, None
        ns = v
        if isinstance(v, dict):
            ns, override, reason = v.get("ns"), bool(v.get("override", False)), v.get("reason")
        if isinstance(ns, bool) or not isinstance(ns, (str, int)):
            errs.append(QtError("E-CT-SCHEMA",
                                f"durations.{name}: must be a decimal string or int, got {ns!r}"))
            continue
        try:
            d = ns_to_dt(Fraction(str(ns)), dt, "exact", what=f"durations.{name}")
        except QtError as e:
            errs.append(e)
            continue
        except ValueError:
            errs.append(QtError("E-CT-SCHEMA", f"durations.{name}: {ns!r} is not a decimal"))
            continue
        if name in target_durs and d != target_durs[name]:
            if not override:
                errs.append(QtError("E-CT-TARGET-CONFLICT",
                                    f"durations.{name} = {ns} ns conflicts with Target "
                                    f"({target_durs[name]} dt)",
                                    hint="set override = true with a reason to use it"))
                continue
            if not reason:
                errs.append(QtError("E-CT-TARGET-CONFLICT",
                                    f"durations.{name}: override requires a reason"))
                continue
            overrides.append(f"durations.{name}")
        durs[name] = d

    # -- latencies (outward rounding) ---------------------------------------------------
    lats: list[ContractLatency] = []
    missing: list[str] = []
    seen: set[str] = set()
    for i, li in enumerate(c.latency):
        if li.key in seen:
            errs.append(QtError("E-CT-SCHEMA", f"latency.{i}.key: duplicate key {li.key!r}"))
            continue
        seen.add(li.key)
        lo_ns = frac(li.lo_ns)
        hi_ns = None if li.hi_ns is None else frac(li.hi_ns)
        lo = ns_to_dt(lo_ns, dt, "latency_lo")
        hi = None if hi_ns is None else ns_to_dt(hi_ns, dt, "latency_hi")
        if c.timebase.latency_resolution == "dt" and (
            lo_ns % dt != 0 or (hi_ns is not None and hi_ns % dt != 0)
        ):
            errs.append(QtError("E-CT-RESOLUTION",
                                f"latency {li.key}: endpoints must be whole dt "
                                "(latency_resolution = 'dt')"))
            continue
        if Fraction(lo) != lo_ns / dt or (hi is not None and hi_ns is not None
                                          and Fraction(hi) != hi_ns / dt):
            warns.append(f"W-CT-ROUND: latency {li.key} [{lo_ns}, {hi_ns}] ns -> "
                         f"[{lo}, {hi}] dt (rounded outward)")
        meta = tuple(sorted(li.meta.items())) + ((("placeholder", "true"),)
                                                 if li.placeholder else ())
        prov = Prov(
            ProvClass[li.prov.upper()], li.source, n=li.n,
            p=None if li.p is None else frac(li.p), load=li.load,
            k_sigma=None if li.k_sigma is None else frac(li.k_sigma), meta=meta,
        )
        if hi is None:
            missing.append(f"latency.{li.key}.hi")
        lats.append(ContractLatency(
            Latency(li.key, Interval(lo, hi), prov), li.src, li.dst, li.tier,
            lo_ns, hi_ns, li.data_dependent, li.placeholder))

    # -- timeline -----------------------------------------------------------------------
    cl = c.timeline.commit_lead
    cl_ns = cl.get("lo_ns") if isinstance(cl, dict) else cl
    commit_lead: int | None = None
    if cl_ns is None:
        if personality in _REQUIRED_COMMIT_LEAD:
            missing.append("timeline.commit_lead")
    elif isinstance(cl_ns, bool) or not isinstance(cl_ns, (str, int)):
        errs.append(QtError("E-CT-SCHEMA", f"timeline.commit_lead: bad number {cl_ns!r}"))
    else:
        try:
            commit_lead = ns_to_dt(frac(cl_ns), dt, "commit_lead")
        except ValueError:
            errs.append(QtError("E-CT-SCHEMA", f"timeline.commit_lead: {cl_ns!r} not a decimal"))

    # -- issue cost (upper bounds round up) ---------------------------------------------
    issue: list[IssueCost] = []
    for name, entry in sorted(c.issue_cost.items()):
        if not isinstance(entry, dict):
            errs.append(QtError("E-CT-SCHEMA", f"issue_cost.{name}: expected a table"))
            continue
        p = entry.get("prov")
        pcls, src = (p.get("prov"), p.get("source", "")) if isinstance(p, dict) else (
            p, entry.get("source", ""))
        if pcls not in PROV.__args__:
            errs.append(QtError("E-CT-SCHEMA", f"issue_cost.{name}: bad prov {pcls!r}"))
            continue
        flds = []
        for k, v in sorted(entry.items()):
            if k.endswith("ns"):
                role = "latency_lo" if k == "lo_ns" else "latency_hi"
                try:
                    flds.append((k, ns_to_dt(frac(v), dt, role)))
                except (ValueError, TypeError):
                    errs.append(QtError("E-CT-SCHEMA", f"issue_cost.{name}.{k}: bad number {v!r}"))
        issue.append(IssueCost(name, tuple(flds), str(pcls), str(src)))

    # -- idle, loop, feedback tiers -----------------------------------------------------
    gaps: list[tuple[str, int]] = []
    for name, v in sorted(dict(c.idle.get("max_gap_variation_ns", {})).items()):
        try:
            gaps.append((name, ns_to_dt(frac(v), dt, "gap_bound")))
        except (ValueError, TypeError):
            errs.append(QtError("E-CT-SCHEMA", f"idle.max_gap_variation_ns.{name}: bad number"))
    while_ok = bool(c.loop.get("while_supported", False))
    if while_ok and not c.branch.allow_loops:
        errs.append(QtError("E-CT-LOOP",
                            "loop.while_supported = true but branch.allow_loops = false"))
    for i, row in enumerate(c.feedback_tier):
        ref = row.get("latency")
        if ref not in seen:
            errs.append(
                QtError("E-CT-SCHEMA", f"feedback_tier.{i}.latency: unknown latency {ref!r}"))

    if errs:
        raise ContractLoadError(errs)

    b = c.branch
    extras = tuple(sorted(
        (k, _freeze(v)) for k, v in {
            "topology": c.topology, "feedback_tier": c.feedback_tier, "dep": c.dep,
            "domain_call": c.domain_call, "sync": c.sync, "evidence": c.evidence,
        }.items() if v))
    snap_id = None
    if snapshot is not None:
        h = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()[:12]
        snap_id = f"{snapshot.get('backend', 'unknown')}:{h}"
    contract = Contract(
        name=c.meta.name, version=c.meta.version, personality=personality, dt_ns=dt,
        grid=tuple(sorted(grid.items())), late_policy=c.timeline.late_policy,
        commit_lead=commit_lead, durations=tuple(sorted(durs.items())), latencies=tuple(lats),
        issue_cost=tuple(issue),
        branch=BranchSpec(b.klass, b.default_policy, b.allow_nested, b.allow_measure_in_branch,
                          b.allow_loops, b.max_cond_bits),
        capacity=_freeze(c.capacity), params=_freeze(c.personality_params),
        idle_variation=tuple(gaps),
        dd_inserted=str(c.idle.get("dd_inserted_by_backend", "unknown")),
        while_supported=while_ok, extras=extras, overrides=tuple(overrides),
        assumed=tuple(assume), missing=tuple(missing), warnings=tuple(warns),
        target_snapshot=snap_id, sha256="",
    )
    body = {k: v for k, v in _canon(contract).items() if k not in ("sha256", "warnings")}
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode())
    return replace(contract, sha256=digest.hexdigest())
