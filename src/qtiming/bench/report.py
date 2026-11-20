"""`qtiming-bench report RESULTS_DIR --tables DIR`: tables (markdown and CSV) from a run's rows.

Reads only `results.jsonl` (and, optionally, `diff.json` / a ground-truth file); nothing is typed
in by hand. Tables: verdict distribution per contract (17.5), tier mix, assumption census (cells
by weakest provenance class), portability (verdict per program across contracts, H4), the
non-certified-number count behind the headline, and H1 / H2 summaries when their inputs exist.
Figures need matplotlib and are skipped, with a message, when it is not installed.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

VERDICTS = ("PROVED", "PROVED-UNDER", "REFUTED", "UNKNOWN", "unsupported", "timeout", "error")


def _write(d: Path, name: str, header: list[str], rows: list[list[Any]], title: str) -> None:
    with open(d / f"{name}.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)
    md = [f"### {title}", "", "| " + " | ".join(header) + " |",
          "| " + " | ".join("---" for _ in header) + " |"]
    md += ["| " + " | ".join(str(x) for x in r) + " |" for r in rows]
    (d / f"{name}.md").write_text("\n".join(md) + "\n", encoding="utf-8")


def tables(rows: list[dict[str, Any]], truth: dict[str, Any] | None,
           diff: dict[str, Any] | None) -> dict[str, tuple[str, list[str], list[list[Any]]]]:
    t: dict[str, tuple[str, list[str], list[list[Any]]]] = {}
    contracts = sorted({r["contract"] for r in rows})

    by_c = {c: Counter(r["status"] for r in rows if r["contract"] == c) for c in contracts}
    t["verdicts_per_contract"] = (
        "Verdict distribution per contract (cells = program x policy)", ["contract", *VERDICTS],
        [[c, *(by_c[c].get(v, 0) for v in VERDICTS)] for c in contracts])

    by_p = {p: Counter(r["status"] for r in rows if r["policy"] == p)
            for p in sorted({r["policy"] for r in rows})}
    t["verdicts_per_policy"] = (
        "Verdict distribution per policy", ["policy", *VERDICTS],
        [[p, *(by_p[p].get(v, 0) for v in VERDICTS)] for p in by_p])

    tiers: Counter[str] = Counter()
    for r in rows:
        tiers.update(r.get("tiers") or {})
    t["tier_mix"] = ("Obligations by the tier that resolved them (cells with a verdict)",
                     ["tier", "obligations"], [[k, v] for k, v in sorted(tiers.items())])

    census: Counter[str] = Counter(r.get("weakest_class") or "none" for r in rows
                                   if r["status"] in ("PROVED", "PROVED-UNDER", "REFUTED",
                                                      "UNKNOWN"))
    t["assumption_census"] = ("Assumption census: cells by weakest provenance class of the "
                              "latency bounds they rest on", ["weakest class", "cells"],
                              [[k, v] for k, v in sorted(census.items())])

    uncert = sum(r.get("uncertified", 0) for r in rows)
    ph = sum(r.get("placeholders", 0) for r in rows)
    rest = sum(1 for r in rows if r.get("uncertified"))
    t["headline_provenance"] = (
        "Headline: verdicts resting on non-certified numbers",
        ["cells with a verdict", "cells resting on a non-certified number",
         "non-certified assumptions (total)", "of which placeholders"],
        [[sum(1 for r in rows if r["status"] in VERDICTS[:4]), rest, uncert, ph]])

    progs = sorted({(r["family"], r["program"]) for r in rows})
    cells = {(r["family"], r["program"], r["contract"], r["policy"]): r["status"] for r in rows}
    pols = sorted({r["policy"] for r in rows})
    port = []
    differing = 0
    for f, p in progs:
        vs = [cells.get((f, p, c, pol), "-") for pol in pols for c in contracts]
        decided = {v for v in vs if v in VERDICTS[:4]}
        differing += len(decided) > 1
        port.append([f"{f}/{p}", *(cells.get((f, p, c, pols[0]), "-") for c in contracts),
                     "yes" if len(decided) > 1 else "no"])
    t["portability"] = (
        f"Portability (H4): verdict at policy {pols[0] if pols else '-'}; last column: verdicts "
        f"differ across contracts/policies ({differing} of {len(progs)} programs)",
        ["program", *contracts, "differs"], port)

    if diff is not None:
        t["h1_differential"] = (
            f"H1: executor violations on proved programs (runs per cell {diff['runs_per_cell']}, "
            f"seed {diff['seed']})",
            ["personality", "proved cells", "runs", "violating runs"],
            [[k, s["proved_cells"], s["runs"], s["violating_runs"]]
             for k, s in diff["per_personality"].items()])
    if truth is not None:
        gt = truth["truth"]
        c: Counter[tuple[str, bool]] = Counter()
        for r in rows:
            k = f"{r['family']}/{r['program']}|{r['contract']}|{r['policy']}"
            if k in gt:
                c[(r["status"], bool(gt[k]["violated"]))] += 1
        safe = sum(v for (s, bad), v in c.items() if not bad)
        alarm = sum(v for (s, bad), v in c.items() if not bad and s in ("REFUTED", "UNKNOWN"))
        t["h2_precision"] = (
            "H2: verdict against exhaustive per-run ground truth (partial: no O3/O4/O7)",
            ["verdict", "violation reachable", "cells"],
            [[s, "yes" if bad else "no", v] for (s, bad), v in sorted(c.items())]
            + [["false-alarm rate (REFUTED or UNKNOWN, no reachable violation)", "",
                f"{alarm}/{safe}" + (f" = {alarm / safe:.2f}" if safe else "")]])
    return t


def _report(a: argparse.Namespace) -> int:
    from . import read_rows

    rows = read_rows(a.results)
    base = Path(a.results)
    base = base if base.is_dir() else base.parent
    diff_p = Path(a.diff) if a.diff else base / "diff" / "diff.json"
    truth_p = Path(a.truth)
    diff = json.loads(diff_p.read_text(encoding="utf-8")) if diff_p.is_file() else None
    truth = json.loads(truth_p.read_text(encoding="utf-8")) if truth_p.is_file() else None
    d = Path(a.tables)
    d.mkdir(parents=True, exist_ok=True)
    out = tables(rows, truth, diff)
    for name, (title, header, body) in out.items():
        _write(d, name, header, body, title)
    print(f"{len(rows)} cells -> {len(out)} tables in {d}")
    if a.figures:
        try:
            import matplotlib  # type: ignore[import-not-found,unused-ignore]

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt  # type: ignore[import-not-found,unused-ignore]
        except ImportError:
            print("figures skipped: matplotlib is not installed (pip install -e '.[bench]')")
            return 0
        fd = Path(a.figures)
        fd.mkdir(parents=True, exist_ok=True)
        title, header, body = out["verdicts_per_contract"]
        fig, ax = plt.subplots(figsize=(7, 3.5))
        bottom = [0] * len(body)
        for j, v in enumerate(header[1:], start=1):
            vals = [r[j] for r in body]
            ax.bar([r[0] for r in body], vals, bottom=bottom, label=v)
            bottom = [x + y for x, y in zip(bottom, vals, strict=True)]
        ax.set_ylabel("cells")
        ax.legend(fontsize=7)
        fig.tight_layout()
        fig.savefig(fd / "verdicts_per_contract.png", dpi=150)
        print(f"figure -> {fd / 'verdicts_per_contract.png'}")
    return 0


def add_parser(sub: Any) -> None:
    r = sub.add_parser("report", help="verdict, tier, assumption and portability tables")
    r.add_argument("results", help="a run directory (or its results.jsonl)")
    r.add_argument("--tables", required=True, help="directory for the .md and .csv tables")
    r.add_argument("--figures", help="directory for figures (needs matplotlib)")
    r.add_argument("--diff", help="diff.json (default: <results>/diff/diff.json)")
    r.add_argument("--truth", default="benchmarks/families/ground_truth.json")
    r.set_defaults(fn=_report)
