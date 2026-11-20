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


def _load(args: argparse.Namespace):  # type: ignore[no-untyped-def]
    from qtiming.frontend import from_qasm3, from_qpy

    contract = load_contract(resolve_contract(args.contract), assume=tuple(args.assume))
    path = resolve_program(args.program)
    if path.suffix == ".qpy":
        prog = from_qpy(str(path), contract=contract)
    else:
        prog = from_qasm3(path.read_text(encoding="utf-8"), filename=str(path), contract=contract)
    return contract, prog


def _guard(fn):  # type: ignore[no-untyped-def]
    """Map load/usage errors to exit code 2 and internal (I-*) errors to 4."""

    def run(args: argparse.Namespace) -> int:
        try:
            return int(fn(args))
        except ContractLoadError as e:
            for err in e.errors:
                print(f"error: {err}", file=sys.stderr)
            return 2
        except QtError as e:
            print(f"error: {e}" + (f"\n  hint: {e.hint}" if e.hint else ""), file=sys.stderr)
            return 4 if e.code.startswith("I-") else 2  # I-* are internal errors

    return run


def _emit(text: str, out: str | None) -> None:
    if out:
        Path(out).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


@_guard
def _check(args: argparse.Namespace) -> int:
    from qtiming.frontend.lint import lint
    from qtiming.solve.dispatcher import SolveCfg
    from qtiming.verdict.model import PROVED_UNDER
    from qtiming.verdict.render import render_text
    from qtiming.verdict.render_html import render_html
    from qtiming.verdict.render_json import render_json
    from qtiming.verdict.render_sarif import render_sarif
    from qtiming.verdict.run import check_program, max_safe

    contract, prog = _load(args)
    cfg = SolveCfg(use_tier1=not args.no_tier1, use_tier2=not args.no_tier2,
                   timeout_ms=int(args.timeout * 1000))
    verdict = check_program(prog.body, contract, policy=args.policy, cfg=cfg,
                            first_failure=args.first_failure, window=not args.no_window)
    if args.max_safe:
        h = max_safe(prog.body, contract, args.max_safe, policy=args.policy)
        found = ("not safe at the current bound" if h is None
                 else f"{h} dt = {float(h * contract.dt_ns):g} ns")
        verdict = replace(verdict, max_safe={f"{args.max_safe}.hi": found})
    dt = contract.dt_ns
    if args.format == "json":
        text = render_json(verdict, dt)
    elif args.format == "sarif":
        text = render_sarif(verdict, dt, lint(prog.body, contract.personality))
    elif args.format == "html":
        text = render_html(verdict, dt)
    else:
        text = render_text(verdict, dt)
    _emit(text, args.out)
    if args.strict_proved and verdict.verdict == PROVED_UNDER:
        return 1
    return verdict.exit_code


def dump_stmt(s, indent: int = 0) -> list[str]:  # type: ignore[no-untyped-def]
    """Readable dump of an elaborated TQ program (`explain --elaborated`)."""
    pad = "  " * indent
    name = type(s).__name__
    fields = []
    for f in ("name", "qubits", "qubit", "dur", "cbit", "policy", "declared"):
        if hasattr(s, f) and getattr(s, f) not in (None, False):
            fields.append(f"{f}={getattr(s, f)!r}")
    if getattr(s, "origin_nid", None) is not None:
        fields.append(f"synth(from n{s.origin_nid})")
    lines = [f"{pad}{name} n{s.nid} {' '.join(fields)}".rstrip()]
    for f in ("stmts",):
        for c in getattr(s, f, ()):
            lines += dump_stmt(c, indent + 1)
    for f, label in (("body", ""), ("then_", "then:"), ("else_", "else:")):
        c = getattr(s, f, None)
        if c is not None and hasattr(c, "nid"):
            if label:
                lines.append(f"{pad}  {label}")
            lines += dump_stmt(c, indent + (2 if label else 1))
    return lines


@_guard
def _explain(args: argparse.Namespace) -> int:
    from qtiming.core.ast import Policy
    from qtiming.dispatch import build_graph
    from qtiming.elab import elaborate
    from qtiming.graph.export import to_dot
    from qtiming.oblig.generate import generate
    from qtiming.verdict.run import with_policy

    contract, prog = _load(args)
    body = with_policy(prog.body, Policy(args.policy)) if args.policy else prog.body
    el = elaborate(body, contract)
    g = build_graph(el.body, contract)
    obs = generate(g, el, contract)
    out: list[str] = []
    if args.elaborated:
        out += dump_stmt(el.body)
    if args.graph == "dot":
        out.append(to_dot(g))
    if args.obligations:
        for o in obs:
            out.append(f"{o.code} n{o.nid}: {o.check}  deps={sorted(o.deps)}  {o.message}")
    if not (args.elaborated or args.obligations or args.graph):
        out.append(f"{contract.name} ({contract.personality}): {len(g.nodes)} nodes, "
                   f"{len(g.edges)} edges, {len(g.lats)} latency variables, "
                   f"{len(obs)} obligations")
        for k, v in sorted(g.facts.items()):
            out.append(f"  facts[{k}]: {len(v)}")
    _emit("\n".join(out), args.out)
    return 0


@_guard
def _lint(args: argparse.Namespace) -> int:
    from qtiming.frontend.lint import lint
    from qtiming.verdict.model import Verdict

    contract, prog = _load(args)
    found = list(prog.notes) + lint(prog.body, contract.personality)
    if args.format == "sarif":
        from qtiming.verdict.render_sarif import render_sarif

        empty = Verdict("PROVED", contract.name, contract.sha256, contract.branch.default_policy,
                        (), None, (), (), ())
        _emit(render_sarif(empty, contract.dt_ns, found), args.out)
    else:
        for e in found:
            where = f"{e.loc.file}:{e.loc.line}: " if e.loc and e.loc.line else ""
            print(f"{where}{e.severity}: {e.code}: {e.message}")
        if not found:
            print("no lint findings")
    return 2 if any(e.severity == "error" for e in found) else 0


@_guard
def _replay(args: argparse.Namespace) -> int:
    from fractions import Fraction

    from qtiming.core.ast import Policy
    from qtiming.dispatch import build_graph
    from qtiming.elab import elaborate
    from qtiming.oblig.generate import generate
    from qtiming.solve.concrete import Result
    from qtiming.verdict.render import ascii_timeline
    from qtiming.verdict.replay import replay
    from qtiming.verdict.run import with_policy

    contract, prog = _load(args)
    doc = json.loads(Path(args.cex).read_text(encoding="utf-8"))
    cexs = doc["counterexamples"] if "counterexamples" in doc else [doc]
    cex = cexs[args.index]
    body = with_policy(prog.body, Policy(args.policy)) if args.policy else prog.body
    el = elaborate(body, contract)
    g = build_graph(el.body, contract)
    code, nid = cex["obligation"]["code"], cex["obligation"]["nid"]
    obl = next((o for o in generate(g, el, contract) if o.code == code and o.nid == nid), None)
    if obl is None:
        print(f"error: no obligation {code} at node {nid} in this program", file=sys.stderr)
        return 2
    sec = cex.get("second")
    res = Result("refuted", cex.get("tier"), omega={k: int(v) for k, v in cex["omega"].items()},
                 theta={k: Fraction(v) for k, v in cex["theta"].items()},
                 second=None if sec is None else {k: int(v) for k, v in sec["omega"].items()},
                 second_theta=None if sec is None else
                 {k: Fraction(v) for k, v in sec["theta"].items()})
    ok = replay(g, obl, res, el.body, contract)
    print(f"{'REPRODUCED' if ok else 'NOT REPRODUCED'}: {code} at node {nid}")
    if args.trace:
        from qtiming.exec.engine import execute
        from qtiming.exec.oracle import Fixed

        run = execute(el.body, contract, Fixed(res.omega, res.theta))
        for ln in ascii_timeline(run, contract.dt_ns):
            print(ln)
    return 0 if ok else 1


def _contract_cmd(args: argparse.Namespace) -> int:
    try:
        a = load_contract(resolve_contract(args.files[0]), assume=tuple(args.assume))
        b = (load_contract(resolve_contract(args.files[1]), assume=tuple(args.assume))
             if args.sub == "diff" else None)
    except (ContractLoadError, QtError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    def view(c):  # type: ignore[no-untyped-def]
        return {"name": c.name, "personality": c.personality, "dt_ns": str(c.dt_ns),
                "commit_lead_dt": c.commit_lead, "missing": list(c.missing),
                "durations": dict(c.durations),
                "latencies": {x.latency.key: [x.latency.iv.lo, x.latency.iv.hi,
                                              x.latency.prov.cls.name.lower()]
                              for x in c.latencies}}

    if b is None:
        print(json.dumps(view(a), indent=2))
        return 0
    va, vb = view(a), view(b)
    diffs = [f"{k}: {va[k]!r} -> {vb[k]!r}" for k in va if va[k] != vb[k]]
    print("\n".join(diffs) if diffs else "contracts are equivalent")
    return 1 if diffs else 0


@_guard
def _repair(args: argparse.Namespace) -> int:
    from qtiming.repair.suggest import _find, repair
    from qtiming.verdict.render import render_text

    contract, prog = _load(args)
    r = repair(prog.body, contract, policy=args.policy)
    dt = contract.dt_ns
    lines = [f"repair: {r.status}: {r.message}", f"before: {r.before.verdict}  "
             f"after: {r.after.verdict}"]
    for h in r.hunks:
        node = _find(r.program, h.nid)
        where = f"line {node.loc.line}" if node is not None and node.loc.line else f"node {h.nid}"
        qs = ", ".join(f"${q}" for q in getattr(node, "qubits", ()))
        lines.append(f"  {h.code}: insert before {where}:  delay[{float(h.dur * dt):g}ns] {qs};"
                     f"  ({h.dur} dt)")
    if r.hunks:
        lines.append(f"added idle time: {float(r.idle_dt * dt):g} ns; the patched program was "
                     "re-verified by the full pipeline")
    _emit("\n".join(lines), args.out)
    if args.verbose:
        _emit(render_text(r.after, dt), None)
    return {"ok": 0, "fixed": 0, "unknown": 3}.get(r.status, 1)


def _common(p: argparse.ArgumentParser) -> None:
    p.add_argument("program", help="OpenQASM 3 file (.qasm) or QPY file (.qpy)")
    p.add_argument("--contract", required=True, help="contract file or shipped instance name")
    p.add_argument("--assume", action="append", default=[], metavar="KEY=VALUE",
                   help="e.g. durations.x=32, timeline.commit_lead=100, ff.default=0:600")


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="qtiming")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ct = sub.add_parser("contract", help="contract tools").add_subparsers(dest="sub", required=True)
    v = ct.add_parser("validate", help="load and validate contract files")
    v.add_argument("files", nargs="+")
    v.add_argument("--assume", action="append", default=[], metavar="KEY=VALUE")
    for name in ("show", "diff"):
        x = ct.add_parser(name, help=f"{name} contract(s)")
        x.add_argument("files", nargs="+")
        x.add_argument("--assume", action="append", default=[], metavar="KEY=VALUE")

    c = sub.add_parser("check", help="verify a program against a timing contract")
    _common(c)
    c.add_argument("--policy", choices=["eq", "sync", "exp"],
                   help="policy for branches that carry no annotation")
    c.add_argument("--format", choices=["text", "json", "sarif", "html"], default="text")
    c.add_argument("--out", metavar="FILE")
    c.add_argument("--max-safe", metavar="KEY", help="bisect the largest safe hi of a latency")
    c.add_argument("--no-tier1", action="store_true")
    c.add_argument("--no-tier2", action="store_true", help="skip exact SMT (no z3 needed)")
    c.add_argument("--timeout", type=float, default=10.0, help="seconds per SMT query")
    c.add_argument("--first-failure", action="store_true", help="stop at the first REFUTED")
    c.add_argument("--no-window", action="store_true",
                   help="never summarise long loops by a window; unroll or fail")
    c.add_argument("--strict-proved", action="store_true",
                   help="treat PROVED-UNDER as failure (exit 1)")

    e = sub.add_parser("explain", help="show the elaborated program, graph and obligations")
    _common(e)
    e.add_argument("--policy", choices=["eq", "sync", "exp"])
    e.add_argument("--elaborated", action="store_true")
    e.add_argument("--obligations", action="store_true")
    e.add_argument("--graph", choices=["dot"])
    e.add_argument("--out", metavar="FILE")

    li = sub.add_parser("lint", help="front-end and static lint only")
    _common(li)
    li.add_argument("--format", choices=["text", "sarif"], default="text")
    li.add_argument("--out", metavar="FILE")

    r = sub.add_parser("replay", help="replay a counterexample in the reference executor")
    r.add_argument("cex", help="JSON from `check --format json` (or one counterexample)")
    _common(r)
    r.add_argument("--policy", choices=["eq", "sync", "exp"])
    r.add_argument("--index", type=int, default=0, help="which counterexample of the report")
    r.add_argument("--trace", action="store_true")

    rp = sub.add_parser("repair", help="suggest delays that fix a REFUTED program (re-verified)")
    _common(rp)
    rp.add_argument("--policy", choices=["eq", "sync", "exp"])
    rp.add_argument("--out", metavar="FILE")
    rp.add_argument("--verbose", action="store_true", help="also print the patched verdict")

    from qtiming.cli import cmd_evidence

    cmd_evidence.add_parser(sub)

    args = ap.parse_args(argv)
    try:
        if args.cmd == "evidence":
            return cmd_evidence.run(args)
        if args.cmd == "repair":
            return _repair(args)
        if args.cmd == "check":
            return _check(args)
        if args.cmd == "explain":
            return _explain(args)
        if args.cmd == "lint":
            return _lint(args)
        if args.cmd == "replay":
            return _replay(args)
        if args.sub in ("show", "diff"):
            return _contract_cmd(args)
        return _validate(args.files, args.assume)
    except KeyboardInterrupt:  # pragma: no cover
        return 130
    except Exception as ex:  # noqa: BLE001  (exit 4 = internal error, per the CLI reference)
        print(f"internal error: {type(ex).__name__}: {ex}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
