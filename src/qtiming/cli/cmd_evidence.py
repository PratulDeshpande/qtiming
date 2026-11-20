"""`qtiming evidence ingest|report JOBS...` (plan 7.7, 18.3)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from qtiming.evidence import EvidenceError, ingest, report


def add_parser(sub: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    p = sub.add_parser("evidence", help="IBM scheduler_timing jobs -> contract patch")
    p.add_argument("action", choices=["ingest", "report"])
    p.add_argument("jobs", nargs="+", metavar="JOBS")
    p.add_argument("--out", help="ingest: write the patch here (default: stdout)")
    p.add_argument("--allow-synthetic", action="store_true",
                   help="accept jobs flagged synthetic (test data only; the patch says so)")
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    try:
        if args.action == "report":
            sys.stdout.write(report(args.jobs))
            return 0
        text = ingest(args.jobs, allow_synthetic=args.allow_synthetic)
    except (EvidenceError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if args.out:
        Path(args.out).write_bytes(text.encode("utf-8"))  # bytes: no newline translation
    else:
        sys.stdout.write(text)
    return 0
