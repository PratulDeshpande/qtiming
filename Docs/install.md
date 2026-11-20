# Install

## Requirements

Python 3.10 or later. `pyproject.toml` lists 3.10 to 3.14 as supported; the project's CI tests 3.10, 3.12 and 3.14.

## From a clone

The package is not on PyPI. `pip index versions qtiming` returns `ERROR: No matching distribution found for qtiming`. Install from a clone of the repository:

    python -m venv .venv
    .venv/Scripts/pip install -e ".[qiskit,z3]"

On Linux and macOS use `.venv/bin/pip`. Run the examples in this documentation from the repository root: the programs in `benchmarks/` are not part of the installed package.

## Extras

The base install has two dependencies: pydantic, and tomli on Python 3.10. It reads contracts and runs the Tier 0 and Tier 1 solvers, but it cannot read a program file.

| Extra | Adds | Needed for |
| --- | --- | --- |
| (none) | `pydantic`, `tomli` (3.10 only) | `contract` commands, the graph, Tier 0 and Tier 1 |
| `qiskit` | `qiskit` (2.3 to 2.6), `openqasm3[parser]`, `qiskit-qasm3-import` | reading `.qasm` and `.qpy` programs; the [Qiskit passes](qiskit.md) |
| `z3` | `z3-solver` | Tier 2: counterexamples, and proofs Tier 1 cannot make |
| `bench` | `pyarrow`, `matplotlib` | the `qtiming-bench` harness |
| `docs` | `mkdocs-material` | building this documentation |
| `dev` | pytest, hypothesis, ruff, mypy, import-linter, jsonschema | running the test and lint gate |
| `synth` | nothing | a placeholder name; no code uses it |

Without the `qiskit` extra, `qtiming check program.qasm` stops with `error: E-FE-MISSING-EXTRA: reading OpenQASM 3 needs the openqasm3 parser`, the hint `pip install 'qtiming[qiskit]'` and exit code 2. Without the `z3` extra, any obligation that Tier 1 cannot prove is UNKNOWN, and the reason says so:

    $ qtiming check benchmarks/families/teleportation/tp_sync --contract ibm_heron --policy eq
    UNKNOWN  (contract ibm_heron, policy eq, sha256 9cf4d27a06ae)
      why: O4 at node 11: Tier 2 needs z3: pip install 'qtiming[z3]'
      ...
    $ echo $?
    3

With the `z3` extra the same command is REFUTED (exit 1). The output above came from a clean environment with only the `qiskit` extra.

## Verify the install

    $ qtiming --help
    usage: qtiming [-h] {contract,check,explain,lint,replay,repair,evidence} ...
    ...

    $ qtiming contract validate src/qtiming/contract/instances/ibm_heron.toml
    OK ibm_heron sha256=9cf4d27a06ae placeholders=0 missing=0 warnings=0

    $ qtiming check benchmarks/families/teleportation/tp_basic --contract ibm_heron --policy eq
    PROVED-UNDER  (contract ibm_heron, policy eq, sha256 9cf4d27a06ae)
    ...

The first line of the last output is the check. A run that ends in `E-FE-MISSING-EXTRA` is a missing extra.

## Build the documentation

    pip install -e ".[docs]"
    mkdocs build --strict
