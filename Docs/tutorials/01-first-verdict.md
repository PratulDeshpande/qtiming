# Your first verdict

**Question:** I have a dynamic circuit. Will its timing hold on IBM Heron?

This tutorial walks the four everyday commands: `lint`, `explain`, `check`, `replay`. Reference: [Quickstart](../quickstart.md), [Command reference](../cli.md).

## The program
Teleportation with one classical correction. The `@timing.within` annotation says the correction must be issued within 3000 ns of the measurement result arriving.

```python
_show.source("teleportation/tp_basic.qasm")
```

    OPENQASM 3.0;
    // Teleportation with one classical correction (plan Appendix A.1).
    // Policy EQ with a 3000 ns deadline from the arrival of the measurement result.
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
    

## 1. `lint`: is the front end happy?

```python
code, out = _show.run("lint", _show.FAMILIES / "teleportation/tp_basic.qasm", "--contract", "ibm_heron")
assert code in (0, 1)
```

    benchmarks/families/teleportation/tp_basic.qasm:14: warning: E-LINT-IBM-BOX: box present
    [exit 0]
    

## 2. `explain`: what did qtiming build from it?

```python
code, out = _show.run("explain", _show.FAMILIES / "teleportation/tp_basic.qasm", "--contract", "ibm_heron")
assert code == 0 and "obligations" in out
```

    ibm_heron (ibm): 25 nodes, 28 edges, 2 latency variables, 15 obligations
      facts[block]: 1
      facts[blockend]: 1
      facts[eqbar]: 1
      facts[gap]: 11
      facts[ready]: 1
    [exit 0]
    

## 3. `check`: the verdict
`PROVED-UNDER` means the claim holds **if** the listed assumptions do. Here the only assumption is IBM's public claim that feed-forward takes about 600 ns; it is labelled *vendor*, not a certified bound.

```python
code, out = _show.run("check", _show.FAMILIES / "teleportation/tp_basic.qasm", "--contract", "ibm_heron")
assert code == 0 and out.startswith("PROVED-UNDER") and "ff.default" in out
```

    PROVED-UNDER  (contract ibm_heron, policy sync, sha256 9cf4d27a06ae)
      assumptions (weakest class: vendor):
        ff.default: [0 ns, 600 ns]  vendor: IBM blog, 2025-11-19 (feedforward about 600 ns); vendor claim, not a certified bound
      O2b: 1 obligation(s): proved (tier 1, margin 0 ns)
      O3: 2 obligation(s): proved (tier 1, margin 2400 ns)
      O4: 11 obligation(s): proved (tier 0, margin 0 ns); proved (tier 1, margin 0 ns)
      O7: 1 obligation(s): proved (tier 1, margin 0 ns)
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 0]
    

The same report as HTML carries an SVG timeline:

```python
_show.report_svg(_show.FAMILIES / "teleportation/tp_basic.qasm", "ibm_heron")
```

<div class="qt-fig qt-tl"><svg viewBox="0 0 840 104" role="img" aria-label="typical run" width="100%">
<text x="2" y="14" font-size="11">typical run</text>
<text x="2" y="41" font-size="11">q0</text>
<line x1="80" x2="840" y1="44" y2="44" stroke="#bbb" stroke-width="1"/>
<text x="2" y="67" font-size="11">q1</text>
<line x1="80" x2="840" y1="70" y2="70" stroke="#bbb" stroke-width="1"/>
<text x="2" y="93" font-size="11">q2</text>
<line x1="80" x2="840" y1="96" y2="96" stroke="#bbb" stroke-width="1"/>
<g><title>h (node 1) at 32 ns</title><rect x="88.0" y="58" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>cx (node 2) at 112 ns</title><rect x="108.0" y="58" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>cx (node 2) at 112 ns</title><rect x="108.0" y="84" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>cx (node 3) at 192 ns</title><rect x="127.9" y="32" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>cx (node 3) at 192 ns</title><rect x="127.9" y="58" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>h (node 4) at 224 ns</title><rect x="135.9" y="32" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>measure (node 5) at 2404 ns</title><rect x="680.2" y="32" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>measure (node 6) at 2372 ns</title><rect x="672.2" y="58" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>delay (node 16) at 2972 ns</title><rect x="822.0" y="84" width="6" height="14" fill="#2c6fbb"/></g>
<g><title>delay (node 13) at 3004 ns</title><rect x="830.0" y="84" width="6" height="14" fill="#2c6fbb"/></g>
<text x="80" y="102" font-size="10">0</text><text x="780" y="102" font-size="10">3004 ns</text></svg></div>

## 4. A program that fails: `tp_sync`
The same teleportation, but with the idle time on `q2` required to be identical across measurement outcomes (`sync`). It is not.

```python
prog = _show.FAMILIES / "teleportation/tp_sync.qasm"
code, out = _show.run("check", prog, "--contract", "ibm_heron")
assert code == 1 and out.startswith("REFUTED")
```

    REFUTED  (contract ibm_heron, policy sync, sha256 9cf4d27a06ae)
      why: O4 at node 11: idle gap on q2 must not vary with outcomes or latencies
      O4 failed at E:/PROJECTS/Qtiming/benchmarks/families/teleportation/tp_sync.qasm:17 (tier 2)
      assumptions (weakest class: vendor):
        ff.default: [0 ns, 600 ns]  vendor: IBM blog, 2025-11-19 (feedforward about 600 ns); vendor claim, not a certified bound
      O4: 9 obligation(s): proved (tier 0, margin 0 ns); refuted (tier 2)
      timeline (counterexample):
        t(ns)     0                                                2406
        q0        ....ch.....................................................m.
        q1        h.c.c......................................................m.
        q2        ..c.........................................................x
      timeline (second execution):
        t(ns)     0                                                2404
        q0        ....ch......................................................m
        q1        h.c.c......................................................m.
        q2        ..c.........................................................x
      not checked by this build: O4a (off by default), O6 (blocking calls), O8 (grid), O9 (loop windows), O7 for SYNC with a spread bound
    [exit 1]
    

The two timelines above are the counterexample: two executions that differ by a few nanoseconds on `q2`. Exit code **1** means refuted; the full list is `0` proved, `1` refuted, `2` usage error, `3` unknown, `4` internal.

## 5. `replay`: don't trust it, re-run it
qtiming re-executes every counterexample in an independent executor that shares no code with the solver.

```python
with tempfile.TemporaryDirectory() as d:
    cex = Path(d) / "cex.json"
    _show.run("check", prog, "--contract", "ibm_heron", "--format", "json", "--out", cex, show=False)
    assert json.loads(cex.read_text(encoding="utf-8"))["verdict"] == "REFUTED"
    code, out = _show.run("replay", cex, prog, "--contract", "ibm_heron")
assert code == 0
```

    REPRODUCED: O4 at node 11
    [exit 0]
    

## What just happened
- `check` turned the program into an event graph, generated timing obligations, and discharged them.
- `tp_basic` held under a vendor-claimed latency, so it is PROVED-UNDER, not PROVED.
- `tp_sync` was REFUTED with a concrete pair of executions, confirmed by replay.

Next: [The four verdicts](02-four-verdicts.md).
