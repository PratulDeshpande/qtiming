# Tutorials

Worked examples that run the real tool and show the pictures. Each page is a Jupyter notebook in
`tutorials/` rendered to Markdown; every key result is asserted in a cell, so building the notebook is
the test. Honest limits apply throughout: vendor claims are labelled, UNKNOWN is shown as UNKNOWN, numbers
a contract leaves absent are marked as illustrative assumptions where a tutorial needs one, and features
that are not built yet are not demonstrated (see [Status and limits](../status.md)).

| # | Tutorial | Answers |
|---|---|---|
| 00 | [Why timing breaks dynamic circuits](00-why-timing.md) | Why *when* things happen is part of whether the program is correct |
| 01 | [Your first verdict](01-first-verdict.md) | Will my circuit's timing hold on IBM Heron? |
| 02 | [The four verdicts](02-four-verdicts.md) | Is `PROVED-UNDER` a pass, and what would make it `PROVED`? |
| 03 | [Policies and annotations](03-policies.md) | How do I say what a branch with unequal arms should do? |
| 04 | [Obligation tour](04-obligations.md) | What is an obligation, and which stack produces which one? |
| 05 | [Contracts are claims](05-contracts.md) | Where do the numbers behind a verdict come from? |
| 06 | [Same circuit, four stacks](06-four-stacks.md) | What does one circuit get on IBM, QUA, Q1 and ARTIQ? |
| 07 | [Counterexamples you can trust](07-counterexamples.md) | Why should I believe a `REFUTED` timeline? |
| 08 | [Automatic repair](08-repair.md) | Can qtiming fix an ARTIQ commit-lead failure, and can I trust the fix? |
| 09 | [From Qiskit](09-qiskit.md) | How do I check, pad and still submit a Qiskit circuit? |
| 10 | [qtiming in CI](10-ci.md) | Can a pull request fail when timing breaks? |
| 11 | [Under the hood](11-under-the-hood.md) | What does `check` build, and what do the solver knobs change? |
| 12 | [Real workloads](12-workloads.md) | What does it say about a whole suite, on every stack? |
| 13 | [Evidence from hardware jobs](13-evidence.md) | How would measured data replace a vendor-claimed latency? |

Also: [Interactive comparison](compare.md), one program on four stacks with a slider for the latency that matters most on each.

Run them yourself: `pip install -e ".[dev,qiskit,z3,tutorials]"`, then `python tutorials/build.py` (all notebooks) or `python tutorials/build.py 05` (one). The comparison page is regenerated with `python tutorials/compare.py`.
