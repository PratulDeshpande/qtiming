Install first (`pip install -e ".[qiskit,z3]"` from a clone; see the README).

# Quickstart

Run from the repository root (the benchmark programs are not in the wheel). Output below was
produced by these exact commands.

    $ qtiming contract validate src/qtiming/contract/instances/ibm_heron.toml
    OK ibm_heron sha256=9cf4d27a06ae placeholders=0 missing=0 warnings=0

    $ qtiming check benchmarks/families/teleportation/tp_basic --contract ibm_heron --policy eq
    PROVED-UNDER  (contract ibm_heron, policy eq, sha256 9cf4d27a06ae)
      assumptions (weakest class: vendor):
        ff.default: [0 ns, 600 ns]  vendor: IBM blog, 2025-11-19 (feedforward about 600 ns); vendor claim, not a certified bound
      O2b: 1 obligation(s): proved (tier 1, margin 0 ns)
      O3: 2 obligation(s): proved (tier 1, margin 2400 ns)
      O4: 11 obligation(s): proved (tier 0, margin 0 ns); proved (tier 1, margin 0 ns)
      O7: 1 obligation(s): proved (tier 1, margin 0 ns)
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    (exit 0)

    $ qtiming check benchmarks/families/teleportation/tp_sync --contract ibm_heron --policy eq
    REFUTED  (contract ibm_heron, policy eq, sha256 9cf4d27a06ae)
      why: O4 at node 11: idle gap on q2 must not vary with outcomes or latencies
      O4 failed at benchmarks/families/teleportation/tp_sync.qasm:17 (tier 2)
      ...
      timeline (counterexample):
    (exit 1; the full report also draws the replayed timeline)

    $ qtiming check benchmarks/families/teleportation/tp_basic --contract artiq --policy eq
    error: E-CT-MISSING: contract 'artiq_rtio' has no duration for 'h'
      hint: add it to [durations] or import it from the backend Target
    (exit 2: the ARTIQ contract leaves unpublished numbers absent instead of guessing them)

    $ qtiming repair benchmarks/families/teleportation/tp_sync --contract ibm_heron --policy eq
    repair: unsupported: no automatic patch for O4 (idle gap on q2 must not vary with outcomes or latencies)
    before: REFUTED  after: REFUTED
    (exit 1)

`repair` only patches O1 (commit lead) failures today and re-verifies every patch; for anything
else it says so, as above. Other commands: `explain`, `lint`, `replay`, `evidence`, and
`contract validate|show|diff`; formats `text`, `json`, `sarif` (GitHub code scanning) and `html`.
Full reference: [command reference](cli.md).

Exit codes of `check`: `0` PROVED or PROVED-UNDER, `1` REFUTED, `2` usage or contract error,
`3` UNKNOWN, `4` internal error (including `I-REPLAY-MISMATCH`, an executor/checker disagreement).

