# Tutorials

Worked examples that run the real tool and show the pictures. Each page is a Jupyter notebook in
`tutorials/` rendered to Markdown; every key result is asserted in a cell, so building the notebook is
the test. Honest limits apply throughout: vendor claims are labelled, UNKNOWN is shown as UNKNOWN, numbers
a contract leaves absent are marked as illustrative assumptions where a tutorial needs one, and features
that are not built yet are not demonstrated (see [Status and limits](../status.md)).

| # | Tutorial |
|---|---|
| 00 | [Why timing breaks dynamic circuits](00-why-timing.md) |
| 01 | [Your first verdict](01-first-verdict.md) |
| 02 | [The four verdicts](02-four-verdicts.md) |
| 03 | [Policies and annotations](03-policies.md) |
| 04 | [Obligation tour](04-obligations.md) |
| 05 | [Contracts are claims](05-contracts.md) |
| 06 | [Same circuit, four stacks](06-four-stacks.md) |
| 07 | [Counterexamples you can trust](07-counterexamples.md) |
| 08 | [Automatic repair](08-repair.md) |
| 09 | [From Qiskit](09-qiskit.md) |
| 10 | [qtiming in CI](10-ci.md) |
| 11 | [Under the hood](11-under-the-hood.md) |
| 12 | [Real workloads](12-workloads.md) |
| 13 | [Evidence from hardware jobs](13-evidence.md) |
| | [Interactive comparison: four stacks, one program](compare.md) |

Run them yourself: `pip install -e ".[dev,qiskit,z3,tutorials]"`, then `python tutorials/build.py` (all notebooks) or `python tutorials/build.py 05` (one). The comparison page is regenerated with `python tutorials/compare.py`.
