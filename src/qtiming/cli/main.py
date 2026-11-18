"""`qtiming` command line: `contract validate` (P2) and `check` (P7).

Exit codes (plan 19.6): 0 PROVED or PROVED-UNDER (1 with --strict-proved for PROVED-UNDER),
1 REFUTED, 2 usage or lint error, 3 UNKNOWN, 4 internal error.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from qtiming.contract.loader import ContractLoadError, load_contract
from qtiming.core.errors import QtError

INSTANCES = Path(__file__).resolve().parents[1] / "contract" / "instances"


def _validate(files: Sequence[str], assume: Sequence[str]) -> int:
    bad = 0
    for path in files:
        try:
            c = load_contract(path, assume=tuple(assume))
        except ContractLoadError as e:
            bad += 1
            print(f"FAIL {path}", file=sys.stderr)
            for err in e.errors:
                print(f"  {err}", file=sys.stderr)
        except (OSError, QtError, ValueError) as e:
            bad += 1
            print(f"FAIL {path}: {e}", file=sys.stderr)
        else:
            n_ph = sum(cl.placeholder for cl in c.latencies)
            print(f"OK {c.name} sha256={c.sha256[:12]} placeholders={n_ph} "
                  f"missing={len(c.missing)} warnings={len(c.warnings)}")
            for m in c.missing:
                print(f"  missing: {m}")
    return 1 if bad else 0


def resolve_contract(name: str) -> str:
    """A path, or the name of a shipped instance (`ibm_heron`, `q1`, `artiq`, `qua`)."""
    if Path(name).is_file():
        return name
    for cand in (INSTANCES / name, INSTANCES / f"{name}.toml", INSTANCES / f"{name}_heron.toml"):
        if cand.is_file():
            return str(cand)
    names = ", ".join(sorted(p.stem for p in INSTANCES.glob("*.toml")))
    raise QtError("E-CLI-CONTRACT", f"no contract file or shipped instance named {name!r}",
                  hint=f"shipped instances: {names}")


def resolve_program(name: str) -> Path:
    p = Path(name)
    for cand in (p, Path(f"{name}.qasm"), p / "program.qasm"):
        if cand.is_file():
            return cand
    raise QtError("E-CLI-PROGRAM", f"no program found for {name!r}",
                  hint="pass an OpenQASM 3 file (.qasm); QPY files use .qpy")


def _check(args: argparse.Namespace) -> int:
    from qtiming.frontend import from_qasm3, from_qpy
    from qtiming.solve.dispatcher import SolveCfg
    from qtiming.verdict.model import PROVED_UNDER, to_dict
    from qtiming.verdict.render import render_text
    from qtiming.verdict.run import check_program, max_safe

    try:
        contract = load_contract(resolve_contract(args.contract), assume=tuple(args.assume))
        path = resolve_program(args.program)
        if path.suffix == ".qpy":
            prog = from_qpy(str(path), contract=contract)
        else:
            prog = from_qasm3(path.read_text(encoding="utf-8"), filename=str(path),
                              contract=contract)
        cfg = SolveCfg(use_tier1=not args.no_tier1)
        verdict = check_program(prog.body, contract, policy=args.policy, cfg=cfg)
        if args.max_safe:
            h = max_safe(prog.body, contract, args.max_safe, policy=args.policy)
            found = ("not safe at the current bound" if h is None
                     else f"{h} dt = {float(h * contract.dt_ns):g} ns")
            verdict = replace(verdict, max_safe={f"{args.max_safe}.hi": found})
    except ContractLoadError as e:
        for err in e.errors:
            print(f"error: {err}", file=sys.stderr)
        return 2
    except QtError as e:
        print(f"error: {e}" + (f"\n  hint: {e.hint}" if e.hint else ""), file=sys.stderr)
        return 2
    text = (json.dumps(to_dict(verdict, contract.dt_ns), indent=2) if args.format == "json"
            else render_text(verdict, contract.dt_ns))
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    if args.strict_proved and verdict.verdict == PROVED_UNDER:
        return 1
    return verdict.exit_code


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="qtiming")
    sub = ap.add_subparsers(dest="cmd", required=True)
    contract = sub.add_parser("contract", help="contract tools").add_subparsers(
        dest="sub", required=True)
    v = contract.add_parser("validate", help="load and validate contract files")
    v.add_argument("files", nargs="+")
    v.add_argument("--assume", action="append", default=[], metavar="KEY=VALUE")

    c = sub.add_parser("check", help="verify a program against a timing contract")
    c.add_argument("program", help="OpenQASM 3 file (.qasm) or QPY file (.qpy)")
    c.add_argument("--contract", required=True, help="contract file or shipped instance name")
    c.add_argument("--policy", choices=["eq", "sync", "exp"],
                   help="policy for branches that carry no annotation")
    c.add_argument("--format", choices=["text", "json"], default="text")
    c.add_argument("--out", metavar="FILE")
    c.add_argument("--assume", action="append", default=[], metavar="KEY=VALUE",
                   help="e.g. durations.x=32, timeline.commit_lead=100, ff.default=0:600")
    c.add_argument("--max-safe", metavar="KEY", help="bisect the largest safe hi of a latency")
    c.add_argument("--no-tier1", action="store_true")
    c.add_argument("--strict-proved", action="store_true",
                   help="treat PROVED-UNDER as failure (exit 1)")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "check":
            return _check(args)
        return _validate(args.files, args.assume)
    except KeyboardInterrupt:  # pragma: no cover
        return 130
    except Exception as e:  # noqa: BLE001  (exit 4 = internal error, per the CLI reference)
        print(f"internal error: {type(e).__name__}: {e}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
