# qtiming

qtiming is a static timing checker for dynamic quantum circuits: programs that measure a qubit mid-circuit and branch on the result. You give it a program (OpenQASM 3 or a Qiskit circuit) and a hardware timing contract. It reports whether the program's timing obligations hold, before the program runs.

The version is 0.1.0 (alpha). Read [Status and limits](status.md) before relying on a verdict. To start, see [Install](install.md) and [Quickstart](quickstart.md).

A branch that idles one qubit for a different time than its sibling branch, or a feed-forward that arrives after its deadline, is a timing bug that shows up only on hardware. qtiming looks for these before the program runs.

## One run

From the repository root:

    $ qtiming check benchmarks/families/teleportation/tp_basic --contract ibm_heron --policy eq
    PROVED-UNDER  (contract ibm_heron, policy eq, sha256 9cf4d27a06ae)
      assumptions (weakest class: vendor):
        ff.default: [0 ns, 600 ns]  vendor: IBM blog, 2025-11-19 (feedforward about 600 ns); vendor claim, not a certified bound
      O2b: 1 obligation(s): proved (tier 1, margin 0 ns)
      O3: 2 obligation(s): proved (tier 1, margin 2400 ns)
      O4: 11 obligation(s): proved (tier 0, margin 0 ns); proved (tier 1, margin 0 ns)
      O7: 1 obligation(s): proved (tier 1, margin 0 ns)
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    $ echo $?
    0

The result is PROVED-UNDER and not PROVED because the proof uses the IBM feed-forward latency, a vendor claim.[^1] O2b, O3, O4 and O7 are obligations; [Obligations](obligations.md) defines each.

## Verdicts

| Verdict | Exit code | Meaning | What it assumes |
| --- | --- | --- | --- |
| `PROVED` | 0 | Every generated obligation holds. | No assumption weaker than a cycle-counted bound. A program with no latency in play (no branch on a measurement) has no assumptions. |
| `PROVED-UNDER` | 0 | Every generated obligation holds if the listed latency bounds are true. | The report prints each bound with its source and evidence class. |
| `REFUTED` | 1 | A counterexample exists: concrete outcomes and latencies that break an obligation. It is minimised and replayed in the independent reference executor. A policy the backend cannot express is also reported as REFUTED. | Nothing. A counterexample is a witness. |
| `UNKNOWN` | 3 | The checker could not decide: a contract number is missing, or no solver tier concluded. | Nothing is claimed. |

Exit codes 2 (usage or contract error) and 4 (internal error) are not verdicts. See [Command reference](cli.md).

Every report ends with a line naming the obligation kinds this build does not generate.[^2] A verdict says nothing about those.

## What it checks

The checker builds the timed event graph of the program for one hardware personality (IBM, Q1, ARTIQ or QUA) and checks a fixed list of obligations against it: no underflow of the real-time queue (O1), a branch condition that is valid when read (O2a, O2b), reaction deadlines (O3), no idle gap whose length depends on a measurement outcome or a latency (O4), capacity (O5) and equal block length for equalised branches (O7). [Obligations](obligations.md) lists each one.

The checker needs numbers: gate durations, feed-forward latency, commit lead. These come from the contract. A number a vendor has not published is absent from the shipped contract and is never guessed.

## Install

The package is not on PyPI. From a clone:

    python -m venv .venv
    .venv/Scripts/pip install -e ".[qiskit,z3]"

On Linux and macOS the venv path is `.venv/bin/pip`. Details: [Install](install.md).

## Where to go

- [Install](install.md): Python versions and extras.
- [Quickstart](quickstart.md): from a program to a verdict in five commands.
- [Reading a verdict](verdicts.md): assumptions, margins, tiers, counterexamples, report formats.
- [Obligations](obligations.md): what O1 to O7 protect and how to fix a failure.
- [Contracts](contracts.md): the four shipped contracts and `--assume`.
- [Policies](policies.md): `eq`, `sync`, `exp` and the `timing.*` annotations.
- [Qiskit](qiskit.md): the transpiler passes.
- [Command reference](cli.md) and [Error codes](errors.md).
- [Status and limits](status.md).
- Background: [personality specs](personality-spec/ibm.md) and [theory](theory/index.md).

[^1]: IBM blog, 2025-11-19: feed-forward takes about 600 ns. A vendor statement, not a certified bound.
[^2]: O4a, O6, O8, O9, and O7 for SYNC with a spread bound. See [Status and limits](status.md).
