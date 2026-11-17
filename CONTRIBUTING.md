# Contributing

Setup: `python -m venv .venv && .venv/Scripts/pip install -e ".[dev]"`

Gate (must be green before a PR):

    ruff check . && mypy --strict src/qtiming/core && lint-imports && pytest -q

Rules: tests first (a test must fail before the code that fixes it); `core/` imports only the
standard library; `exec/` never imports the graph/solver side (see `.importlinter`).
Behaviour changes to a personality go through the decision log in the implementation plan.
