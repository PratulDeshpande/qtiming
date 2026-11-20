#!/usr/bin/env bash
# Offline smoke test: contracts, two verdicts, one counterexample replay, one benchmark cell,
# one evidence ingest (SYNTHETIC fixtures), then the test suite. Run from anywhere.
set -euo pipefail
cd "$(dirname "$0")/.."
T=families/teleportation; B=benchmarks
expect() { want=$1; shift; set +e; "$@" >/dev/null; got=$?; set -e
  [ "$got" -eq "$want" ] || { echo "FAIL (exit $got, wanted $want): $*"; exit 1; }; echo "ok  ($got) $*"; }
TMP=$(mktemp -d)

qtiming contract validate src/qtiming/contract/instances/*.toml
expect 0 qtiming check $B/$T/tp_basic --contract ibm_heron --policy eq
expect 1 qtiming check $B/$T/tp_sync --contract ibm_heron --policy eq
expect 1 qtiming check $B/$T/tp_sync --contract ibm_heron --policy eq --format json --out "$TMP/cex.json"
qtiming replay "$TMP/cex.json" $B/$T/tp_sync --contract ibm_heron --policy eq | grep -q REPRODUCED
expect 2 qtiming check $B/$T/tp_basic --contract artiq --policy eq   # unpublished numbers -> E-CT-MISSING
qtiming-bench run --suite $B/families/teleportation --contracts ibm_heron --policies eq --repeat 1 --out "$TMP/run" >/dev/null
qtiming evidence ingest tests/fixtures/evidence/conclusive/*.json --allow-synthetic --out "$TMP/evidence.patch.toml"
test -s "$TMP/evidence.patch.toml"
python -m pytest -q
echo "SMOKE OK"
