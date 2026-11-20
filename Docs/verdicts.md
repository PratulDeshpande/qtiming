# Reading a verdict

A report has a verdict line, the reasons for it, the assumptions it rests on, one line per obligation kind, notes, and the list of obligation kinds this build did not check.

## The four verdicts

The program verdict is the weakest result among its obligations, in the order REFUTED, UNKNOWN, PROVED-UNDER, PROVED.

**REFUTED** (exit 1). At least one obligation fails. The report names the obligation, the source line and the tier, and draws a timeline of a concrete execution that breaks it. Every counterexample is minimised and then replayed in the reference executor; the checker reports REFUTED only if the executor reproduces the failure. A program whose policy the backend cannot express is also REFUTED, with a `policy-incompatible` reason. See [Policies](policies.md).

**UNKNOWN** (exit 3). No obligation is refuted and at least one could not be decided. The `why:` lines give the cause. Seen in practice:

- `missing contract field: timeline.commit_lead`: the contract leaves a number absent. Supply it with `--assume`, see [Contracts](contracts.md).
- `Tier 2 needs z3`: install the `z3` extra.
- `Tier 1 inconclusive and Tier 2 is disabled`: you passed `--no-tier2` (or `--no-tier1 --no-tier2`).
- `Tier 2 does not encode Events (O5) yet`: the symbolic encoding of O5 is not built. On ARTIQ every program that generates an O5 obligation gets this result, because Tier 0 and Tier 1 do not decide O5 there. In the six ARTIQ benchmark programs I ran, O5 was UNKNOWN each time.
- `fails if in2cpu is large enough`: the counterexample depends on a latency with no upper bound. A violation that needs an unbounded latency is never reported as REFUTED, because the missing number could make the obligation hold.

**PROVED-UNDER** (exit 0). Every generated obligation holds if the listed assumptions are true. The result is also PROVED-UNDER when an obligation is marked `@timing.hard` and its assumptions include anything weaker than a cycle-counted bound.

**PROVED** (exit 0). Every generated obligation holds and no assumption is weaker than a cycle-counted bound. In practice this means a program in which no obligation depends on a latency. A branch-free program on `ibm_heron`:

    $ qtiming check plain --contract ibm_heron
    PROVED  (contract ibm_heron, policy sync, sha256 9cf4d27a06ae)
      O4: 4 obligation(s): proved (tier 0, margin 0 ns)
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    $ echo $?
    0

Every shipped contract states its latencies at the `vendor` class, so any program with a branch on those latencies is at best PROVED-UNDER.

`--strict-proved` turns PROVED-UNDER into exit code 1, for a gate that accepts only PROVED.

The `policy` in the first line is the policy for branches without an annotation: `--policy` if given, else the contract default. A branch with a `timing.policy` annotation uses its own.

## Assumptions and evidence classes

Each assumption is a latency interval a proof used, with its source. The line

    ff.default: [0 ns, 600 ns]  vendor: IBM blog, 2025-11-19 (feedforward about 600 ns); vendor claim, not a certified bound

reads: the proof assumed the key `ff.default` is between 0 and 600 ns; the class is `vendor`; the rest is the citation.[^v] The header `weakest class` is the minimum over all assumptions. The full list is always kept, never collapsed to the weakest class.

The classes, from weakest to strongest (`src/qtiming/core/provenance.py`):

| Class | Meaning |
| --- | --- |
| `vendor` | A documentation claim. Also the class of every `--assume` value. |
| `msigma` | A mean and spread; the entry states `hi` explicitly and records the `k` used by whoever stated it. |
| `pctl` | A percentile under a stated load. |
| `mmax` | A sample maximum over `n` runs. |
| `sched` | A value the scheduler reported for one compiled job. |
| `cyc` | A cycle-counted design bound. |
| `cert` | A formally certified worst case. |

Only `cyc` and `cert` can discharge a `@timing.hard` obligation or make a verdict PROVED. A contract entry in the `msigma` or `pctl` class must state `hi_ns`; the loader never derives it.

## Margins

`proved (tier 1, margin 2400 ns)` means the tightest case still has 2400 ns to spare. `margin 0 ns` is normal for equality-style obligations such as O4 and O7, which are met exactly. On a refuted obligation the report prints `short by` the shortfall instead, for example `O1 failed at ...:7 (tier 0, short by 200 ns)`.

`--max-safe KEY` bisects the largest upper bound of one latency for which the program still verifies, and re-elaborates at each step:

    $ qtiming check benchmarks/families/teleportation/tp_basic --contract ibm_heron --policy eq --max-safe ff.default
    ...
      max safe ff.default.hi: 750 dt = 3000 ns
    ...

The IBM dt is 4 ns, so 750 dt is 3000 ns: the deadline. On a program that already fails at the current bound it prints `max safe ff.default.hi: not safe at the current bound`.

## Tiers

Each obligation goes to the cheapest tier that can decide it. The tier is printed with each result.

| Tier | Method | Can conclude |
| --- | --- | --- |
| 0 | Exact evaluation of the one dispatch the hardware performs, per outcome scenario. Used when the obligation depends on no latency. | PROVED or REFUTED. |
| 1 | Interval abstraction with affine-max forms. | PROVED only. It never refutes; what it cannot prove goes to Tier 2. |
| 2 | Z3 over exact rationals (needs the `z3` extra). | PROVED, or REFUTED with a counterexample. UNKNOWN on timeout (`--timeout`, default 10 s per query) or when the counterexample needs an unbounded latency. |

`--no-tier1` skips Tier 1. `--no-tier2` skips Tier 2: the run needs no Z3, and what Tier 1 cannot prove is UNKNOWN. The same check with each setting:

    $ qtiming check benchmarks/families/teleportation/tp_basic --contract ibm_heron --policy eq --no-tier1
    ...
      O3: 2 obligation(s): proved (tier 2)
    ...
    $ qtiming check benchmarks/families/teleportation/tp_basic --contract ibm_heron --policy eq --no-tier1 --no-tier2
    UNKNOWN  (contract ibm_heron, policy eq, sha256 9cf4d27a06ae)
      why: O2b at node 9: Tier 1 inconclusive and Tier 2 is disabled
      ...

## The counterexample timeline

    timeline (counterexample):
      t(ns)     0                                                2406
      q0        ....ch.....................................................m.
      q1        h.c.c......................................................m.
      q2        ..c.........................................................x
    timeline (second execution):
      t(ns)     0                                                2404
      ...

One row per resource. The axis runs from 0 to the last event, scaled to 60 columns, so two timelines with different end times are drawn at slightly different scales. An event is the first letter of its operation (`h`, `c` for `cx`, `m` for `measure`, `x`). A violating event is drawn as an exclamation mark. Obligations of the O4 and O7 kind compare two executions, so the report draws a second one.

The exact values are in the JSON report: `omega` maps each outcome bit to 0 or 1, and `theta` maps each latency occurrence to its value in dt (exact rationals, so `"1/2"` is half a dt). For the `tp_sync` counterexample the two executions have the same outcome and differ only in `ff.default@m6`: `1/2` against `0`. At 4 ns per dt, a 2 ns change in latency changes the idle gap on q2, which the contract's `idle.max_gap_variation_ns` of 0 forbids.

## Report formats

`--format` selects the report; `--out FILE` writes it to a file.

| Format | Content |
| --- | --- |
| `text` | The default, as shown above. |
| `json` | Verdict, policy, contract name and hash, assumptions (in dt and ns), obligations with tier and margin, counterexamples with `omega` and `theta`, reasons, `not_checked`, notes and `max_safe`. |
| `sarif` | SARIF 2.1.0. Each refuted obligation is a result with rule id `V-O4`, `V-O1` and so on; each assumption is a `V-ASSUME` note; front-end lint findings are included. For GitHub code scanning. |
| `html` | A static page with an inline SVG timeline. |

## Replay

`qtiming replay CEX PROGRAM --contract C` takes the JSON report (or one entry of its `counterexamples` array), runs it in the reference executor and prints `REPRODUCED` or `NOT REPRODUCED`. `--index N` picks one counterexample from a report that has several. Pass the same `--policy` and `--assume` flags as the original check.

    $ qtiming replay cex.json benchmarks/families/teleportation/tp_sync --contract ibm_heron --policy eq
    REPRODUCED: O4 at node 11
    $ echo $?
    0

[^v]: A vendor claim is a number the vendor states without a cycle-counted or certified basis. A verdict that rests on one is PROVED-UNDER at best.
