# Quickstart

Five commands take a program to a verdict and a replayed counterexample. Run them from the repository root after [installing](install.md) the `qiskit` and `z3` extras. The program is `benchmarks/families/teleportation/tp_basic.qasm`, teleportation with one classical correction:

    qubit[3] q;
    bit[2] c;

    h q[1];
    cx q[1], q[2];
    cx q[0], q[1];
    h q[0];
    c[0] = measure q[0];
    c[1] = measure q[1];

    @timing.policy eq
    @timing.within 3000ns c[1]
    box {
        if (c[1]) {
            x q[2];
        }
    }

`@timing.policy eq` pads both arms of the branch to equal length. `@timing.within 3000ns c[1]` is a deadline: the first operation of the box must start within 3000 ns of the result in `c[1]`. [Policies](policies.md) explains both.

## 1. Lint

    $ qtiming lint benchmarks/families/teleportation/tp_basic --contract ibm_heron
    benchmarks\families\teleportation\tp_basic.qasm:14: warning: E-LINT-IBM-BOX: box present
    $ echo $?
    0

The warning is expected: IBM hardware does not take timing boxes, so strip the annotations before submission. See [Qiskit](qiskit.md).

## 2. Explain

    $ qtiming explain benchmarks/families/teleportation/tp_basic --contract ibm_heron --policy eq
    ibm_heron (ibm): 25 nodes, 28 edges, 2 latency variables, 15 obligations
      facts[block]: 1
      facts[blockend]: 1
      facts[eqbar]: 1
      facts[gap]: 11
      facts[ready]: 1

The graph has 15 obligations. `--obligations` lists them and `--elaborated` prints the program after the equalising delays are inserted.

## 3. Check

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

Every obligation holds if the feed-forward latency is at most 600 ns. That bound is a vendor claim, so the verdict is PROVED-UNDER. The O3 margin of 2400 ns is the 3000 ns deadline minus the 600 ns latency. [Reading a verdict](verdicts.md) covers each line.

## 4. A failing program

`tp_sync.qasm` is the same circuit with `@timing.policy sync`: the branch starts as soon as the result arrives and nothing pads it.

    $ qtiming check benchmarks/families/teleportation/tp_sync --contract ibm_heron --policy eq --format json --out cex.json
    $ echo $?
    1

The same check in text form:

    $ qtiming check benchmarks/families/teleportation/tp_sync --contract ibm_heron --policy eq
    REFUTED  (contract ibm_heron, policy eq, sha256 9cf4d27a06ae)
      why: O4 at node 11: idle gap on q2 must not vary with outcomes or latencies
      O4 failed at benchmarks/families/teleportation/tp_sync.qasm:17 (tier 2)
      ...
      timeline (counterexample):
        t(ns)     0                                                2406
        q0        ....ch.....................................................m.
        q1        h.c.c......................................................m.
        q2        ..c.........................................................x
      ...
    $ echo $?
    1

The `--policy eq` flag applies only to branches without an annotation; the `sync` annotation wins. Qubit q2 idles while it waits for the correction. How long it idles depends on the feed-forward latency, so the gap is not fixed at compile time.

## 5. Replay

    $ qtiming replay cex.json benchmarks/families/teleportation/tp_sync --contract ibm_heron --policy eq
    REPRODUCED: O4 at node 11
    $ echo $?
    0

`replay` runs the counterexample in the reference executor, which is written separately from the checker. `--trace` also prints the executed timeline.

## Next

- To fix an O4 failure, see [Obligations](obligations.md).
- To use your own program, write OpenQASM 3 or build a Qiskit circuit. Pick a [contract](contracts.md). The `q1`, `qua` and `artiq` contracts need `--assume durations.<gate>=<ns>` for each gate your program uses.
