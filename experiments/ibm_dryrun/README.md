# IBM dry-run evidence (plan section 18, phase P14)

Primary evidence for the `ibm_heron` contract: `scheduler_timing` metadata of jobs submitted with
`dry_run=True` (no QPU time). Nothing in `jobs/` is committed yet: **no real hardware data exists in
this repository.** Files under `tests/fixtures/evidence/` are SYNTHETIC test fixtures
(`"synthetic": true`); `qtiming evidence ingest` refuses them unless `--allow-synthetic`, and the
resulting patch says so in every `source` string.

## Collector

    python experiments/ibm_dryrun/collect.py                 # local: writes specs/, submits nothing
    pip install -e ".[ibm]"                                  # qiskit-ibm-runtime >= 0.51
    cp .env.example .env                                     # then fill in .env (gitignored)
    python experiments/ibm_dryrun/collect.py --submit        # real dry-run submission

Setup: `QISKIT_IBM_TOKEN` (IBM Quantum Platform API key), `QISKIT_IBM_INSTANCE` (CRN of a Flex,
Premium or On-Prem plan; dry-run jobs are not available on Open or Pay-As-You-Go) and optionally
`QISKIT_IBM_BACKEND`. They are read from the shell environment, or from a repo-root `.env` that
never overrides the shell. `.env` is gitignored; commit only `.env.example`.

`--submit` always calls `Sampler.run(..., dry_run=True)` (no QPU time; there is no way to run for
real) and requests timing with `options.experimental = {"execution": {"scheduler_timing": True}}`.
A job is saved only if the service reports it ran on a mock device (`is_mock`); otherwise the
collector aborts and saves nothing. IBM's raw timing is a text table (`branch,instr,channel,t0,
duration,pulse`); it is normalised to the schema below and kept untouched in `raw_scheduler_timing`.
Dry-run results are random mock data, so `arms.taken` is set only when the schedule shows exactly
one arm. Verified against IBM's docs only: the adapter has not yet run against a live account, so
the first real job should be inspected (do delay instructions appear as rows?).

## Job record schema `qtiming-evidence-job/1` (one JSON file per job)

| field | type | meaning |
|---|---|---|
| `schema` | str | exactly `"qtiming-evidence-job/1"` |
| `job_id`, `backend` | str | IBM job id; backend name (job ids must be unique per ingest) |
| `runtime_version`, `qiskit_version` | str | `qiskit-ibm-runtime` / `qiskit` versions |
| `transpiler_options` | object | options used (optional) |
| `circuit_qpy_sha256` | str | SHA-256 of the QPY of the submitted circuit |
| `submitted_date` | str | `YYYY-MM-DD` |
| `dry_run` | bool | must be `true`; ingest rejects anything else |
| `family` | str | `ff_base`, `arms_equal`, `arms_unequal`, `meas_variant`, `placement`, `two_branches` |
| `tier` | str | optional, default `"default"`; selects latency key `ff.<tier>` |
| `latency_key` | str | optional override of the contract latency key |
| `dt_ns` | str | decimal ns per dt (string, never float) |
| `scheduler_timing.instructions` | list | `{name, qubits, start_dt, stop_dt, block_id}`; `block_id` is null outside a conditional block; names starting `measure` are measurements |
| `arms` | object | unequal-arm families: `{then_dt, else_dt, taken: "then"\|"else"}` |
| `raw_scheduler_timing` | any | optional untouched vendor metadata |
| `synthetic` | bool | test fixtures only; never set on real data |

## Derivation (`qtiming.evidence`)

* Feedforward gap per conditional block: first block start minus end of the latest earlier measure,
  in ns. Per key: `lo = min`, `hi = max`, `n` = jobs, provenance `sched` (exact for those jobs, not
  a bound for all jobs; cannot discharge hard obligations).
* Join behaviour from unequal-arm jobs whose taken arm is the shorter one: block extent equal to the
  longest arm -> `pad_to_longest_block`; equal to the taken arm -> `restart_at_join`. If jobs
  disagree or show neither, the patch leaves `join_behavior` unchanged and records
  `join_behavior_prov = { prov = "vendor", source = "inconclusive: ..." }`. No unequal-arm job: the
  field is simply absent from the patch (UNKNOWN stays UNKNOWN).

Reproduce: `qtiming evidence ingest experiments/ibm_dryrun/jobs/*.json --out evidence.patch.toml`
(byte-identical on re-run; the SHA-256 of every input is recorded under `[[evidence]]`). Apply with
`qtiming.evidence.apply_patch(contract_dict, patch)`.
