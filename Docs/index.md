# qtiming

A static timing checker for dynamic quantum circuits. Given a program and a hardware timing
contract it answers PROVED, PROVED-UNDER (assumptions), REFUTED (a counterexample replayed in an
independent executor) or UNKNOWN, before the program runs.

**Pre-alpha.** Read [Status and limits](status.md) before relying on a verdict.

* [Quickstart](quickstart.md): install and run a first check.
* [Command reference](cli.md): every command, option and exit code.
* Semantics: [timed semantics](Timed semantics for dynamic quantum programs.md) and the
  [timing rulebook](Timing rulebook for quantum computers.md).
* Personality specs: [IBM](personality-spec/ibm.md), [Q1](personality-spec/q1.md),
  [ARTIQ](personality-spec/artiq.md), [QUA](personality-spec/qua.md).
* Theory: [windowing](theory/T4-windowing.md), [DC rules](theory/dc-rules.md) (flagged UNVERIFIED).
