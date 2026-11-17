# qtiming

A static timing checker for dynamic quantum circuits. Given a program and a hardware timing
contract, it returns PROVED, PROVED-UNDER (assumptions), REFUTED (replayable counterexample)
or UNKNOWN before the program runs.

Status: pre-alpha. Built phase by phase from `Plans/Implementation Plan v2 (validated).md`.
Done so far: P0 (skeleton, tooling) and P1 (core data model).

## Develop

    python -m venv .venv
    .venv/Scripts/pip install -e ".[dev]"
    ruff check . && mypy --strict src/qtiming/core && lint-imports && pytest -q

Licence: Apache-2.0.
