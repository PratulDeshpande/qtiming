# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

MkDocs with a fully custom theme (own templates, CSS and type; not stock Material). Existing `Docs/*.md` stay the source. Deployed to GitHub Pages from `.github/workflows/docs.yml`. Chosen by the maintainer.

## Users

Primary: circuit authors, people writing dynamic quantum circuits (mid-circuit measurement plus classical feed-forward) in Qiskit or OpenQASM 3 who want to run `qtiming check` on a program and understand the verdict it prints. They are at a terminal, usually mid-task, and read documentation to answer one question: what does this verdict, error or flag mean, and what do I do next.

Secondary (served by links out of the main path, not by the front page): researchers and reviewers evaluating the semantics and soundness claims; hardware and compiler teams writing or auditing timing contracts for IBM, Q1, ARTIQ or QUA.

## Product Purpose

`qtiming` is a static timing checker for dynamic quantum circuits. Given a program and a hardware timing contract it answers, before the program runs, whether the program's timing obligations hold. Success for the docs: a circuit author installs it, runs `check` on their own program, and can read the result without opening the theory.

## Positioning

Four verdicts, not a pass/fail: PROVED, PROVED-UNDER (holds if the listed latency bounds are true, each printed with its source), REFUTED (a minimised counterexample replayed in an independent reference executor), UNKNOWN (a contract number is missing or no solver tier decided). It never guesses an unpublished vendor number: the field stays absent and the dependent result is UNKNOWN. Verification is checked against one fixed dispatch per hardware personality, not against a free schedule.

## Operating Context

Command-line tool, Python 3.10 to 3.14, optional extras `qiskit` and `z3`. Inputs: OpenQASM 3 (`.qasm`) or QPY programs and a TOML timing contract; four shipped contracts (`ibm_heron`, `q1`, `artiq`, `qua`). Output formats: text, JSON, SARIF, HTML. Exit codes: 0 proved, 1 refuted, 2 usage error, 3 unknown, 4 internal error. Commands: `check`, `explain`, `lint`, `replay`, `repair`, `evidence`, `contract validate|show|diff`, and `qtiming-bench`.

## Capabilities and Constraints

Built: front end, elaboration, per-personality timed event graph, obligations O1 to O7 (O4a, O6, O8, O9 and O7 for SYNC with a spread bound are not generated and every report says so), Tier 0 exact, Tier 1 interval and Tier 2 Z3 solvers, replayed counterexamples, reports, windowing for IBM loops, Qiskit passes, `repair` for O1 only, benchmark harness.
Undecided or not true yet: the dynamic-controllability checker is flagged UNVERIFIED and is not used for verdicts; there is no real IBM hardware evidence (fixtures are synthetic); RUS formulas are not wired into `check`; there is no `qtiming synth` command; the benchmark expectations are a regression snapshot, not ground truth.
Distribution: version 0.1.0 (alpha), intended for PyPI. Licence Apache-2.0. Repository: https://github.com/PratulDeshpande/QTiming.

## Brand Commitments

Name: `qtiming` (lowercase, code-set). Author and maintainer: Pratul Deshpande. The prose is plain and states limits as plainly as capabilities; the README's "Status and limitations" voice is the model. No other identity assets exist yet (no logo).

## Evidence on Hand

Real command transcripts in `README.md` and `Docs/quickstart.md` (produced by the exact commands shown). Four shipped contracts. A 56-program benchmark suite under `benchmarks/families/` (regression snapshot only). Theory write-ups with an honest per-theorem status in `Docs/theory/`. Personality specifications with hand-computed golden traces in `Docs/personality-spec/`.
Absent, and must not be invented: testimonials, named users or customers, performance or scaling figures, hardware measurements, adoption numbers, PyPI download counts, comparisons against other tools. The internal `Plans/` documents are not part of the public site.

## Product Principles

1. State what is not checked as prominently as what is.
2. Show real output: every example is a command that was run, with its real exit code.
3. A verdict is a claim with a source: assumptions and their provenance are part of the answer, not a footnote.
4. Reference first for the person at the terminal; theory is one click away, never in the way.
5. Never present a vendor number, snapshot or synthetic fixture as established fact.

## Accessibility & Inclusion

No product-specific requirement was established. Documentation is text-heavy, read at length and used as a lookup: it must be fully keyboard-navigable, work at 200 percent zoom and on a phone, meet WCAG AA contrast, and not rely on colour alone to distinguish verdicts.
