# Contracts

A timing contract is a TOML file that states the numbers the checker may use for one hardware target: the time base, gate durations, feedback latencies with their evidence class, the branch model and a few resource limits. The checker uses only what the contract states. A number the contract does not state is absent, and any obligation that needs it is UNKNOWN. It is never guessed.

Pass a contract with `--contract`, either as a file path or as the name of a shipped instance.

## Shipped contracts

The four contracts live in `src/qtiming/contract/instances/`. They were written from public documentation only; each number carries its source string.

| Name | Personality | Branch class | Default policy | What is absent |
| --- | --- | --- | --- | --- |
| `ibm_heron` | IBM | restricted | `sync` | Nothing is missing. Gate durations come from an unofficial offline snapshot of one backend (dt 4 ns). `ff.default` is 0 to 600 ns, `vendor` class; the upper bound is a vendor claim and the lower bound is a conservative widening. |
| `q1` (Qblox) | Q1 | predicated | `eq` | All gate durations. The trigger-network latency is 212 to 239 ns (`vendor`); issue costs are cycle-counted (`cyc`). |
| `artiq` | ARTIQ | exposed | `exp` | `timeline.commit_lead`, the upper bound of `in2cpu`, and all gate durations. |
| `qua` | QUA | resync | `sync` | All gate durations. The three `align.*` latencies are placeholders: the vendor documentation says only "a few cycles". `active_reset` is 0 to 224 ns, `vendor`. |

Validate the four:

    $ qtiming contract validate src/qtiming/contract/instances/ibm_heron.toml src/qtiming/contract/instances/q1.toml src/qtiming/contract/instances/artiq.toml src/qtiming/contract/instances/qua.toml
    OK ibm_heron sha256=9cf4d27a06ae placeholders=0 missing=0 warnings=0
    OK qblox_q1 sha256=df77f741d36f placeholders=0 missing=0 warnings=2
    OK artiq_rtio sha256=f893d78201d1 placeholders=0 missing=2 warnings=0
      missing: latency.in2cpu.hi
      missing: timeline.commit_lead
    OK qm_qua sha256=87985e202758 placeholders=3 missing=0 warnings=0
    $ echo $?
    0

`validate` takes file paths, not instance names. It exits 1 if a contract fails to load:

    $ qtiming contract validate bad.toml
    FAIL bad.toml
      E-CT-SCHEMA: latency.0: Value error, lo_ns 212 > hi_ns 100
    $ echo $?
    1

(`bad.toml` was `q1.toml` with `hi_ns` changed to 100.) The two `q1` warnings are `W-CT-ROUND`: a latency in ns is not a whole number of dt, so it is rounded outward to the enclosing dt interval.

## Absent numbers

Running the `artiq` contract on a program with no supplied gate durations stops:

    $ qtiming check benchmarks/families/teleportation/tp_basic --contract artiq --policy eq
    error: E-CT-MISSING: contract 'artiq_rtio' has no duration for 'h'
      hint: add it to [durations] or import it from the backend Target
    $ echo $?
    2

A missing latency bound or missing `commit_lead` does not stop the run. The dependent obligation is UNKNOWN and the `why:` line names the key:

    $ qtiming check benchmarks/families/artiq/artiq_reset_fb --contract artiq --assume durations.x=100 --assume durations.measure=1000 --assume durations.h=50
    UNKNOWN  (contract artiq_rtio, policy exp, sha256 06e2688c8777)
      why: O1 at node 7: missing contract field: timeline.commit_lead
      why: O5 at node 7: Tier 2 does not encode Events (O5) yet
      ...
    $ echo $?
    3

## `--assume`

`--assume KEY=VALUE` overrides or supplies a number for one run. It is accepted by `check`, `explain`, `lint`, `replay`, `repair` and the `contract` subcommands. Every assumed value is recorded in the report under `note: contract assumed value`, and the contract hash changes.

| Form | Sets |
| --- | --- |
| `durations.NAME=NS` | The duration of gate `NAME`, in ns. It must be a whole number of dt. |
| `timeline.commit_lead=NS` | The commit lead, in ns. |
| `KEY=LO:HI` | The latency `KEY` in ns. `HI` may be empty for unbounded. Existing entries keep their other fields; the new entry is flagged `placeholder`. |

The only evidence class an assumption can have is `vendor`; `KEY=0:600:cyc` is rejected with `E-CT-ASSUME`. This is deliberate: a number typed on the command line must never make a verdict PROVED.

The numbers in this documentation that come from `--assume` (gate durations of 32 ns, 100 ns and so on, `commit_lead=200`, `in2cpu=0:300`) are illustrative. They are not vendor values.

## Inspect and compare

`contract show` accepts a file or an instance name and prints a JSON summary. Durations and latencies are in dt.

    $ qtiming contract show ibm_heron
    {
      "name": "ibm_heron",
      "personality": "ibm",
      "dt_ns": "4",
      "commit_lead_dt": null,
      "missing": [],
      "durations": {
        "cx": 20,
        ...
        "x": 8,
        "z": 8
      },
      "latencies": {
        "ff.default": [
          0,
          150,
          "vendor"
        ]
      }
    }

`contract diff A B` lists the fields that differ and exits 1 if there are any:

    $ qtiming contract diff ibm_heron q1
    name: 'ibm_heron' -> 'qblox_q1'
    personality: 'ibm' -> 'q1'
    commit_lead_dt: None -> 0
    ...
    $ echo $?
    1

`--assume` is applied to both sides, so it cannot be used to compare an assumed contract with its base.

## Evidence classes of contract numbers

A latency entry has a `prov` field, one of `vendor`, `msigma`, `pctl`, `mmax`, `sched`, `cyc`, `cert`, and a `source` string. `mmax` requires `n`, `pctl` requires `p` and `load`, `msigma` requires `k_sigma`; `msigma` and `pctl` entries must state `hi_ns`. The classes are defined in [Reading a verdict](verdicts.md). All shipped latencies are `vendor`; the Q1 issue costs are `cyc`.

## Fields of the TOML schema

`src/qtiming/contract/schema.py` is the source. Unknown keys are rejected. Floats are rejected in time fields: write a decimal string or an integer.

| Table | Field | Meaning |
| --- | --- | --- |
| `[meta]` | `name`, `version`, `schema`, `personality` | `schema` must be `qtiming-contract/0.2`. `personality` is `ibm`, `artiq`, `q1` or `qua`. |
| `[target]` | `source`, `backend`, `import` | Optional. `source = "snapshot:FILE"` reads a Target snapshot; `import` lists what to take from it: `dt`, `alignments`, `durations`. |
| `[timebase]` | `dt_ns`, `grid`, `latency_resolution` | `dt_ns` may be `"from_target"`. `latency_resolution` is `continuous` or `dt`. |
| `[timeline]` | `late_policy`, `commit_lead` | `late_policy` is one of `raise`, `drop_log`, `delay`, `defer_round`, `halt`, `compile_error`, `mixed`. |
| `[durations]` | gate name = ns | Fixed gate durations. `import_from_target = true` takes them from the Target. |
| `[[latency]]` | `key`, `src`, `dst`, `tier`, `lo_ns`, `hi_ns`, `data_dependent`, `prov`, `source`, `placeholder` | A feedback or alignment latency. Absent `hi_ns` means unbounded. At least one entry is required. |
| `[branch]` | `class`, `default_policy`, `allow_nested`, `allow_measure_in_branch`, `allow_loops`, `max_cond_bits` | `class` is `predicated`, `equalized`, `resync`, `exposed` or `restricted`; it decides which policies the backend accepts. |
| `[idle]` | `max_gap_variation_ns` | The tolerance for O4. |
| `[loop]` | `while_supported` | Cannot be true if `branch.allow_loops` is false (`E-CT-LOOP`). |
| `[issue_cost]`, `[capacity]`, `[personality_params.*]` | personality-specific | For example `capacity.lanes` (ARTIQ), `personality_params.ibm.join_behavior`. |

`dep`, `domain_call`, `sync`, `topology`, `feedback_tier` and `evidence` are accepted by the schema. I did not verify that any obligation reads them in 0.1.0.
