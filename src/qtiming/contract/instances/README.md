# Shipped contract instances

Written only from public documentation. Every number carries its source string. Where a number is
not published it is absent (unbounded, listed in `Contract.missing`) or a flagged placeholder, so a
verdict depending on it is UNKNOWN or carries the placeholder in its assumption list.

## ibm_heron.toml
- `dt`, alignments and gate/measure durations come from a Target. The shipped
  `ibm_heron_snapshot.json` is an **unofficial** offline fixture (dt 4 ns; measure 2180 ns,
  measure_2 1380 ns, kingston values from the plan); pass a live Target to replace it.
- `ff.default`: hi = 600 ns is a **vendor claim**; `lo = 0` is a conservative widening, not a
  measurement. To be replaced by `sched` evidence (plan Section 18).
- `join_behavior` is a named parameter (vendor class) until calibrated.
- `dd_inserted_by_backend = "unknown"` (not documented in the sources reviewed).

## q1.toml
- Trigger-network figures (212-239 ns, 252 ns busy, 149 ns OP+IP) are documented vendor figures
  [verify page path]. 149 + 239 = 388 ns reproduces the documented worked example in ns; after
  outward rounding to dt the same path is 392 ns, and the loader says so (`W-CT-ROUND`).
- Issue costs are cycle-counted design values (re-verify against the current instruction table).

## artiq.toml
- `commit_lead` is required but **unpublished**: left absent (`timeline.commit_lead` in
  `Contract.missing`). Supply with `--assume timeline.commit_lead=<ns>`.
- `in2cpu` has no published upper bound: `hi` absent.
- `lane_fifo_depth` unknown [verify].

## qua.toml
- All three `align.*` entries are **placeholders** (illustrative: the docs say only "a few
  cycles"). `active_reset` 224 ns is a vendor claim.
