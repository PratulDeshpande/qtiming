# Artifact

Reproduces what can be reproduced offline. Nothing here needs hardware, credentials or network
at run time (the Docker build downloads Python packages once).

    docker build -f artifact/Dockerfile -t qtiming-artifact .
    docker run --rm qtiming-artifact            # runs artifact/smoke.sh
    # without Docker, in a venv with `pip install -e ".[qiskit,z3,dev]"`:
    bash artifact/smoke.sh

`smoke.sh` validates the four contracts, runs one PROVED-UNDER, one REFUTED and one
unsupported-contract check with exit-code assertions, replays a counterexample, runs one
`qtiming-bench` cell set, ingests SYNTHETIC evidence, then runs the full pytest suite.
Only `smoke.sh` exists today; the plan's `core.sh`, `full.sh`, `vm/build.sh` and the CSTNU
Tool fetcher are not written, and the Docker image has no JDK.

## Claim to command

Source: `benchmarks/claims.json` (statuses are copied from it; nothing here is a result).

| Claim | Command | Offline? |
| --- | --- | --- |
| Verdicts and exit codes | `qtiming check benchmarks/families/teleportation/tp_basic --contract ibm_heron --policy eq` (expect PROVED-UNDER, exit 0) | yes |
| Counterexamples are replayed | `qtiming check ...tp_sync ... --format json --out cex.json; qtiming replay cex.json ...tp_sync --contract ibm_heron --policy eq` (REPRODUCED) | yes |
| H1 soundness differential | `qtiming-bench diff --runs 200 --seed 1 --programs 3` (the preregistered 1000-run, 3000-program run is not part of smoke) | yes, executor-visible kinds only |
| H2 precision vs exhaustive truth | `qtiming-bench truth --out benchmarks/families/` | partial: the IBM executor emits no violations, so the table is trivial |
| H3 scalability | `qtiming-bench run ... --unroll-limit 16` | needs the full sweep; not scripted |
| H4 portability | `qtiming-bench report` | partial: only IBM publishes gate durations (use `--assume`) |
| H5 policy cost | `qtiming check ... --format json` | not wired: `policy_cost` is not reported yet |
| H6 hardware feed-forward window | `qtiming evidence ingest jobs/*.json` | NOT reproducible offline: needs IBM dry-run or QPU data, none is in the repository |
| Oracle cross-checks (CSTNU Tool, 621 networks) | none | NOT reproducible: the jar is not fetched; the DC checker is UNVERIFIED |
