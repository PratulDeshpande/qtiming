# qtiming

A static timing checker for dynamic quantum circuits. Given a program and a hardware timing
contract, it returns PROVED, PROVED-UNDER (assumptions), REFUTED (replayable counterexample)
or UNKNOWN before the program runs.

Status: pre-alpha. Built phase by phase from `Plans/Implementation Plan v2 (validated).md`.

What works today: `qtiming check` verifies a program against a hardware timing contract (IBM, Q1, ARTIQ, QUA personalities) with exact (Tier 0), interval (Tier 1) and SMT (Tier 2, optional `z3` extra) solvers; every counterexample is replayed in an independent reference executor. What does not exist yet: the symbolic ARTIQ lane (O5) encoding, RUS verdicts inside `check`, windowing for long programs, controllability synthesis, Qiskit passes, and the benchmark suite. Every verdict lists the obligation kinds it did not check.

```
qtiming check benchmarks/families/teleportation/tp_basic --contract ibm_heron --policy eq --max-safe ff.default
qtiming check benchmarks/families/teleportation/tp_sync --contract ibm_heron --format html --out report.html
```

Reports: text, JSON, SARIF 2.1.0 (for GitHub code scanning) and a static HTML timeline. Full command reference: `Docs/cli.md`.

Done so far: P0 (skeleton, tooling) and P1 (core data model).

## Develop

    python -m venv .venv
    .venv/Scripts/pip install -e ".[dev]"
    ruff check . && mypy --strict src/qtiming/core && lint-imports && pytest -q

Licence: Apache-2.0.
