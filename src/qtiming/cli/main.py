"""`qtiming` command line. Only `contract validate` exists so far (phase P2)."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from qtiming.contract.loader import ContractLoadError, load_contract
from qtiming.core.errors import QtError


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


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="qtiming")
    sub = ap.add_subparsers(dest="cmd", required=True)
    contract = sub.add_parser("contract", help="contract tools").add_subparsers(
        dest="sub", required=True)
    v = contract.add_parser("validate", help="load and validate contract files")
    v.add_argument("files", nargs="+")
    v.add_argument("--assume", action="append", default=[], metavar="KEY=VALUE")
    args = ap.parse_args(argv)
    return _validate(args.files, args.assume)


if __name__ == "__main__":
    raise SystemExit(main())
