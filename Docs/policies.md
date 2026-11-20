# Policies and annotations

A branch on a measurement result makes the two arms take different amounts of time. A policy states what the program expects the hardware to do about that. There are three.

| Policy | What it asks for | Idle time and timing |
| --- | --- | --- |
| `eq` | Both arms take the same time, whatever the outcome. | The elaborator inserts a barrier over the qubits involved, a wait equal to the upper bound of the feedback latency, and pads the shorter arm with a `delay` to the length of the longer. Idle time is longer, and it is the same for every outcome and every latency. |
| `sync` | Each arm runs as soon as the result is available; the branches rejoin afterwards. | Nothing is padded. The gap before the branch depends on the latency, and the length of the branch depends on the outcome. On QUA the elaborator adds an align (barrier) after the branch. |
| `exp` | The programmer owns the timeline: delays are written out and the checker does not insert any. | Whatever the program writes. |

`eq` is implemented by rewriting the program (see it with `qtiming explain PROG --contract C --elaborated`). On ARTIQ it inserts nothing: an `eq` branch there relies on delays you write. On Q1 it does not pad either; see below.

The same circuit under two policies, on `ibm_heron`: `msi_soft_within.qasm` has no policy annotation, so `--policy` decides.

    $ qtiming check benchmarks/families/magic_state/msi_soft_within --contract ibm_heron --policy eq
    PROVED-UNDER  (contract ibm_heron, policy eq, sha256 9cf4d27a06ae)
    ...
    $ echo $?
    0

    $ qtiming check benchmarks/families/magic_state/msi_soft_within --contract ibm_heron --policy sync
    REFUTED  (contract ibm_heron, policy sync, sha256 9cf4d27a06ae)
      why: O4 at node 8: idle gap on q0 must not vary with outcomes or latencies
    ...
    $ echo $?
    1

## Which backend accepts which

The branch class of the contract decides. The table is `src/qtiming/contract/compat.py`.

| Policy | `predicated` (Q1) | `equalized` | `resync` (QUA) | `exposed` (ARTIQ) | `restricted` (IBM) |
| --- | --- | --- | --- | --- | --- |
| `eq` | native if arms match | native | via padding | via delays you write | via padding, single non-nested `if` only |
| `sync` | rejected | rejected | native | via a resync delay you write | native for a single `if` |
| `exp` | rejected | rejected | rejected | native | rejected |

No shipped contract has the `equalized` class. "Via delays" means the checker accepts the policy and does not insert the delays.

A rejected policy is reported as REFUTED with a `policy-incompatible` reason and exit code 1. The annotation wins over `--policy`:

    $ qtiming check benchmarks/families/teleportation/tp_exp --contract ibm_heron
    REFUTED  (contract ibm_heron, policy sync, sha256 9cf4d27a06ae)
      why: policy-incompatible: policy 'exp' is not accepted on restricted backends: restricted backend has no exposed timeline
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    $ echo $?
    1

The `policy sync` in the header is the default for unannotated branches; `tp_exp` has an `exp` annotation, which is what was rejected. On Q1:

    $ qtiming check benchmarks/families/active_reset/reset_basic --contract q1 --assume durations.x=32 --assume durations.measure=1000 --policy sync
    REFUTED  (contract qblox_q1, policy sync, sha256 c9650047ddee)
      why: policy-incompatible: policy 'sync' is not accepted on predicated backends: cannot express a join gap bound; the RT core never resynchronises
    ...

What to change: pick a policy the backend accepts, or a different contract.

### Q1 and `eq`

On Q1 an `eq` branch is not padded. The two arms must already hold the same real-time instructions in total time, counting the per-skipped-instruction wait (`else_time_dt`). If they do not, the run stops:

    $ qtiming check benchmarks/families/teleportation/tp_basic --contract q1 --assume durations.h=32 --assume durations.cx=64 --assume durations.x=32 --assume durations.measure=1000
    error: E-ELAB-Q1-NOT-EQUALISABLE: arm totals differ: 8 dt when true, 1 dt when false
      hint: match RT instruction counts and durations, or use policy sync/exp
    $ echo $?
    2

`tp_q1.qasm` shows the form that works: the `else` arm holds a `delay[32ns]` to match the `x`.

## Annotations

Annotations are written `@timing.<kind> <payload>` in OpenQASM 3, immediately before a `box`. In Qiskit they are objects from `qtiming.frontend.annotations`, passed to `qc.box(annotations=[...])`; see [Qiskit](qiskit.md). An annotation on anything other than a box is an error:

    $ qtiming check misplaced --contract ibm_heron
    error: E-FE-ANNOT-PLACEMENT: timing.* annotations attach only to a box
      hint: wrap the statement in `box { ... }`
    $ echo $?
    2

(`misplaced.qasm` put `@timing.policy eq` directly before an `if`.)

| Annotation | Payload | Effect |
| --- | --- | --- |
| `policy` | `eq`, `exp`, or `sync` with optional `(delta=<dur>,gap=<dur>)` | Sets the policy for branches inside the box, nested boxes included. |
| `within` | `<dur> <reg>[<i>]` | A deadline: generates O3. The first operation in the box must start within `<dur>` of the result in the named bit. The bit must be written by a measurement earlier in the program (`E-ELAB-WITHIN-ANCHOR` otherwise). |
| `hard` | none | Used with `within`. The O3 it produces can be discharged only by `cyc` or `cert` evidence; otherwise the verdict is PROVED-UNDER. |
| `cap` | `<N>` | The iteration bound of a `while` loop in the box. Required: a `while` without it fails with `E-FE-UNBOUNDED-WHILE`. `exhaust=<label>` is not implemented. |

Durations are a number and a unit: `ns`, `us`, `ms`, `s` or `dt`. A deadline in time units is rounded down to a whole number of dt, so it never looks looser than written. A duration written in `dt` must be a whole number.

Examples, each run above or in [Obligations](obligations.md):

- `@timing.policy eq` with `@timing.within 3000ns c[1]`: `tp_basic`, [Quickstart](quickstart.md).
- `@timing.policy sync`: `tp_sync`, REFUTED on O4 under IBM.
- `@timing.policy exp`: `tp_exp`; accepted only on ARTIQ.
- `@timing.within 300ns c[0]`: `reset_within_tight`, REFUTED on O3.
- `@timing.within 3000ns c[0]` with `@timing.hard`: `msi_hard_3000`. On `ibm_heron` it is PROVED-UNDER, as `msi_soft_within` is; the `hard` flag records that a vendor bound is not enough to call the deadline met.
- `@timing.cap 4` with `@timing.policy eq`, on QUA:

        $ qtiming check benchmarks/families/rus/rus_while_policy_eq --contract qua --assume durations.h=32 --assume durations.cx=64 --assume durations.x=32 --assume durations.measure=1000
        PROVED-UNDER  (contract qm_qua, policy sync, sha256 d44238256a60)
          assumptions (weakest class: vendor):
            active_reset: [0 ns, 224 ns]  vendor: QM claim: 224 ns active reset (vendor)
          O2b: 4 obligation(s): proved (tier 1, margin 0 ns)
          O4: 29 obligation(s): proved (tier 0, margin 0 ns); proved (tier 1, margin 0 ns)
          ...
        $ echo $?
        0

    The `while` is unrolled into 4 nested branches. The same loop on `ibm_heron` stops with `E-GRAPH-UNSUPPORTED: IBM arms may not nest ifs or measure`.

`sync(delta=<dur>,gap=<dur>)` is parsed, converted to dt and stored. No obligation uses `delta` or `gap` in 0.1.0, because O7 for `sync` with a spread bound is not generated. `ls_merge_sync_delta.qasm` uses `sync(delta=100ns)` and is REFUTED on `ibm_heron` for O4, as plain `sync` is.

The names `pmin`, `call`, `declared_idle` and `cut` are accepted as annotation kinds. `pmin` and `call` payloads are validated; I found no code that acts on any of the four. `cut` is not read by the loop windowing, which works from the shape of the loop.
