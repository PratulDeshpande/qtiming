# Counterexamples you can trust

**Question:** `check` says REFUTED and shows two timelines. Why should I believe them?

Because qtiming does not ask you to trust the solver. Every counterexample is a small JSON object that an independent executor re-runs. Reference: [Command reference](../cli.md), [Verdicts](../verdicts.md), [Policies](../policies.md).

## The program
`tp_sync` is teleportation with the correction in a `sync` box: no padding, so the arm starts the moment the result arrives. The idle gap on `q2` then depends on how long feed-forward took, which obligation O4 forbids.

```python
prog = _show.FAMILIES / "teleportation/tp_sync.qasm"
_show.source(prog)
```

    OPENQASM 3.0;
    // Teleportation with one correction under the SYNC policy: no padding, the arm starts as soon
    // as the result arrives. Expected to be REFUTED where idle gaps must not vary (O4).
    qubit[3] q;
    bit[2] c;
    
    h q[1];
    cx q[1], q[2];
    cx q[0], q[1];
    h q[0];
    c[0] = measure q[0];
    c[1] = measure q[1];
    
    @timing.policy sync
    box {
        if (c[1]) {
            x q[2];
        }
    }
    

## 1. The verdict and its predicted timelines

```python
code, out = _show.run("check", prog, "--contract", "ibm_heron")
assert code == 1 and out.startswith("REFUTED")

def timeline(text, title):
    lines = text.splitlines()
    i = next(k for k, l in enumerate(lines) if l.strip() == title)
    return [l.strip() for l in lines[i + 1 : i + 5]]

first = timeline(out, "timeline (counterexample):")
second = timeline(out, "timeline (second execution):")
assert first != second and first[0].endswith("2406") and second[0].endswith("2404")
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
    

The two executions differ by 2 ns (2406 vs 2404): the same outcomes, different feed-forward latency. Both latencies lie inside the contract's assumed range, `ff.default` in [0 ns, 600 ns], a *vendor claim* from IBM.

## 2. The counterexample as data
`--format json` writes the counterexample as plain JSON. It is small: one measurement outcome (`omega`) and the latency each feed-forward took (`theta`), once for the counterexample and once for the second execution.

```python
tmp = tempfile.TemporaryDirectory()
cex = Path(tmp.name) / "cex.json"
_show.run("check", prog, "--contract", "ibm_heron", "--format", "json", "--out", cex, show=False)
report = json.loads(cex.read_text(encoding="utf-8"))
c = report["counterexamples"][0]
print(json.dumps({k: c[k] for k in ("obligation", "tier", "omega", "theta", "second")}, indent=1))
assert c["obligation"]["code"] == "O4" and c["tier"] == 2
assert c["omega"] == c["second"]["omega"]            # same outcomes
assert c["theta"] != c["second"]["theta"]            # only the latencies differ
assert c["theta"]["ff.default@m6"] == "1/2" and c["second"]["theta"]["ff.default@m6"] == "0"
```

    {
     "obligation": {
      "code": "O4",
      "nid": 11
     },
     "tier": 2,
     "omega": {
      "c[1]@m6": 1
     },
     "theta": {
      "ff.default@m5": "0",
      "ff.default@m6": "1/2"
     },
     "second": {
      "omega": {
       "c[1]@m6": 1
      },
      "theta": {
       "ff.default@m5": "0",
       "ff.default@m6": "0"
      }
     }
    }
    

## 3. `replay --trace`: run it again, independently
`replay` feeds exactly those outcomes and latencies to the reference executor, which never imports the graph or solver code (enforced by `lint-imports`). `--trace` prints the timeline it executed.

```python
code, replayed = _show.run("replay", cex, prog, "--contract", "ibm_heron", "--trace")
assert code == 0 and replayed.startswith("REPRODUCED: O4")
```

    REPRODUCED: O4 at node 11
    t(ns)     0                                                2406
    q0        ....ch.....................................................m.
    q1        h.c.c......................................................m.
    q2        ..c.........................................................x
    [exit 0]
    

## 4. Executed vs predicted
The solver predicted the first timeline; the executor produced its own. They must agree line for line.

<div class="qt-fig"><table><tr><th></th><th>predicted (solver)</th><th>executed (replay)</th></tr><tr><th><code></code></th><td><pre>t(ns)     0                                                2406</pre></td><td><pre>t(ns)     0                                                2406</pre></td></tr><tr><th><code>q0</code></th><td><pre>q0        ....ch.....................................................m.</pre></td><td><pre>q0        ....ch.....................................................m.</pre></td></tr><tr><th><code>q1</code></th><td><pre>q1        h.c.c......................................................m.</pre></td><td><pre>q1        h.c.c......................................................m.</pre></td></tr><tr><th><code>q2</code></th><td><pre>q2        ..c.........................................................x</pre></td><td><pre>q2        ..c.........................................................x</pre></td></tr></table></div>

## 5. A wrong counterexample is rejected
Edit the JSON so the second execution uses the same latency as the first, and nothing differs any more. The executor says so rather than agreeing.

```python
bad = Path(tmp.name) / "bad.json"
bad.write_text(cex.read_text(encoding="utf-8").replace('"1/2"', '"0"'), encoding="utf-8")
code, out = _show.run("replay", bad, prog, "--contract", "ibm_heron")
assert code == 1 and out.startswith("NOT REPRODUCED")
```

    NOT REPRODUCED: O4 at node 11
    [exit 1]
    

Replaying the real counterexample against a different program fails the same way:

```python
code, out = _show.run("replay", cex, _show.FAMILIES / "teleportation/tp_basic.qasm", "--contract", "ibm_heron")
assert code == 1 and out.startswith("NOT REPRODUCED")
tmp.cleanup()
```

    NOT REPRODUCED: O4 at node 11
    [exit 1]
    

If the solver and executor ever disagreed on a genuine REFUTED, `check` itself would stop with `I-REPLAY-MISMATCH` (exit 4) instead of printing a verdict.

## 6. The same program on QUA
The QUA contract is built on a different personality, but it does not publish a duration for `h`, so qtiming refuses to guess:

```python
code, out = _show.run("check", prog, "--contract", "qua")
assert code == 2 and "E-CT-MISSING" in out
```

    error: E-CT-MISSING: contract 'qm_qua' has no duration for 'h'
      hint: add it to [durations] or import it from the backend Target
    [exit 2]
    

That is a usage error (exit 2), not a verdict: there is no QUA counterexample to replay here. Fill the missing duration in a contract and the same pipeline applies; see [Contracts](../contracts.md).

## What just happened
- The solver (tier 2) found two executions of `tp_sync` that differ on `q2` timing.
- The counterexample is a small JSON object: outcomes plus per-feed-forward latencies.
- `replay --trace` re-executed it in an independent executor and reproduced the same timeline (exit 0); tampered or mismatched input gives `NOT REPRODUCED` (exit 1).

Next: [tutorials index](index.md).
