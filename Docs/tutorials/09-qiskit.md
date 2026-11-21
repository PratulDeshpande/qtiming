# From Qiskit

**Question:** My circuit lives in Qiskit, not in a `.qasm` file. How do I check it, pad it, and still submit something IBM accepts?

This tutorial builds teleportation in Python and uses `from_circuit`, the annotation classes, the three transpiler passes, the `scheduling_method="qtiming"` plug-in, and the OpenQASM 3 / QPY round trip. Reference: [Qiskit](../qiskit.md), [Policies](../policies.md). Needs the `qiskit` extra; supported Qiskit is 2.3 to 2.6.

```python
from qiskit import QuantumCircuit
from qiskit.transpiler import PassManager
from qiskit.transpiler.exceptions import TranspilerError
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager

from qtiming.frontend import from_circuit, from_qpy
from qtiming.frontend.annotations import Policy, Within
from qtiming.frontend.serialise import qasm3_dumps, qasm3_loads, qpy_dumps, qpy_loads
from qtiming.qiskit_pass import EqualizeBranches, StripTimingAnnotations, TimingCheck
```

## The circuit
Annotations are attached to a `box` (a Qiskit 2.x feature). `Policy("eq")` asks that the two arms of the `if` take equal time; `Within("3000ns c[1]")` says the correction must start within 3000 ns of the result `c[1]` arriving.

```python
def teleport(deadline: str) -> QuantumCircuit:
    qc = QuantumCircuit(3, 2)
    qc.h(1)
    qc.cx(1, 2)
    qc.cx(0, 1)
    qc.h(0)
    qc.measure(0, 0)
    qc.measure(1, 1)
    with qc.box(annotations=[Policy("eq"), Within(deadline)]):
        with qc.if_test((qc.clbits[1], 1)):
            qc.x(2)
    return qc

qc = teleport("3000ns c[1]")
P(qc.draw("text"))
```

                        ┌───┐┌─┐                                             
    q_0: ────────────■──┤ H ├┤M├─────────────────────────────────────────────
         ┌───┐     ┌─┴─┐└┬─┬┘└╥┘                                             
    q_1: ┤ H ├──■──┤ X ├─┤M├──╫──────────────────────────────────────────────
         └───┘┌─┴─┐└───┘ └╥┘  ║ ┌───────   ┌──────  ┌───┐ ───────┐  ───────┐ 
    q_2: ─────┤ X ├───────╫───╫─┤ Box-0  ──┤ If-1  ─┤ X ├  End-1 ├─  End-0 ├─
              └───┘       ║   ║ └───────   └──╥───  └───┘ ───────┘  ───────┘ 
                          ║   ║          ┌────╨────┐                         
    c: 2/═════════════════╩═══╩══════════╡ c_1=0x1 ╞═════════════════════════
                          1   0          └─────────┘                         

## 1. `from_circuit`: the front end
`from_circuit` turns the circuit into qtiming's own program. The box keeps its annotations as `(key, payload)` pairs. Without a contract, gate durations are left unresolved (a note, not a guess).

```python
prog = from_circuit(qc)
box = prog.body.stmts[-1]
P("qubits:", prog.qubits, " bits:", [f"{b.reg}[{b.idx}]" for b in prog.bits])
P("box annotations:", box.annotations)
P("notes:", sorted({n.code for n in prog.notes}))
assert box.annotations == (("policy", "eq"), ("within", "3000ns c[1]"))
```

    qubits: (0, 1, 2)  bits: ['c[0]', 'c[1]']

    box annotations: (('policy', 'eq'), ('within', '3000ns c[1]'))

    notes: ['N-FE-DUR-UNRESOLVED']

## 2. `TimingCheck`: the verdict inside a pass manager
An analysis pass. The circuit is untouched; the verdict lands in `property_set["qtiming_verdict"]`. As in [Your first verdict](01-first-verdict.md), the answer rests on a vendor-claimed feed-forward latency.

```python
pm = PassManager([TimingCheck("ibm_heron", fail_on="refuted")])
pm.run(qc)
v = pm.property_set["qtiming_verdict"]
P(v.verdict, v.weakest_class, [a.key for a in v.assumptions])
assert v.verdict == "PROVED-UNDER" and [a.key for a in v.assumptions] == ["ff.default"]
```

    PROVED-UNDER vendor ['ff.default']

A deadline the contract cannot meet makes the pass raise `TranspilerError` (`fail_on` is `"never"`, `"refuted"` or `"unknown"`):

```python
try:
    PassManager([TimingCheck("ibm_heron")]).run(teleport("300ns c[1]"))
    raise AssertionError("expected TranspilerError")
except TranspilerError as e:
    P(f"TranspilerError: {e}")
    assert "REFUTED" in str(e)
```

    TranspilerError: 'qtiming: REFUTED under ibm_heron: O3 at node 7: first operation must start within the deadline after the result'

## 3. `EqualizeBranches`: pad, then look
The `eq` policy inserts a barrier, a wait for the feed-forward latency, and a padded `else` arm. The pass writes that padding out as ordinary `barrier` and `delay` instructions. Before:

```python
P(qc.draw("text"))
```

                        ┌───┐┌─┐                                             
    q_0: ────────────■──┤ H ├┤M├─────────────────────────────────────────────
         ┌───┐     ┌─┴─┐└┬─┬┘└╥┘                                             
    q_1: ┤ H ├──■──┤ X ├─┤M├──╫──────────────────────────────────────────────
         └───┘┌─┴─┐└───┘ └╥┘  ║ ┌───────   ┌──────  ┌───┐ ───────┐  ───────┐ 
    q_2: ─────┤ X ├───────╫───╫─┤ Box-0  ──┤ If-1  ─┤ X ├  End-1 ├─  End-0 ├─
              └───┘       ║   ║ └───────   └──╥───  └───┘ ───────┘  ───────┘ 
                          ║   ║          ┌────╨────┐                         
    c: 2/═════════════════╩═══╩══════════╡ c_1=0x1 ╞═════════════════════════
                          1   0          └─────────┘                         

After. The `delay(150 dt)` (600 ns at the snapshot's dt) precedes the branch; the new `else` arm holds `delay(8 dt)`, the duration of `x`:

```python
eq = PassManager([EqualizeBranches("ibm_heron")]).run(qc)
P(eq.draw("text"))
inner = eq.data[-1].operation.blocks[0].data
names = [i.operation.name for i in inner]
P(names)
assert names == ["barrier", "delay", "if_else"]
if_else = inner[2].operation
assert [b.data[0].operation.name for b in if_else.blocks] == ["x", "delay"]
```

                        ┌───┐┌─┐                                              »
    q_0: ────────────■──┤ H ├┤M├──────────────────────────────────────────────»
         ┌───┐     ┌─┴─┐└┬─┬┘└╥┘┌───────                                      »
    q_1: ┤ H ├──■──┤ X ├─┤M├──╫─┤        ─────────────────────────────────────»
         └───┘┌─┴─┐└───┘ └╥┘  ║ │ Box-0   ░ ┌────────────────┐  ┌──────  ┌───┐»
    q_2: ─────┤ X ├───────╫───╫─┤        ─░─┤ Delay(150[dt]) ├──┤ If-1  ─┤ X ├»
              └───┘       ║   ║ └───────  ░ └────────────────┘  └──╥───  └───┘»
                          ║   ║                               ┌────╨────┐     »
    c: 2/═════════════════╩═══╩═══════════════════════════════╡ c_1=0x1 ╞═════»
                          1   0                               └─────────┘     »
    «                                                   
    «q_0: ──────────────────────────────────────────────
    «                                          ───────┐ 
    «q_1: ────────────────────────────────────        ├─
    «     ┌──────── ┌──────────────┐ ───────┐   End-0 │ 
    «q_2: ┤ Else-1  ┤ Delay(8[dt]) ├  End-1 ├─        ├─
    «     └──────── └──────────────┘ ───────┘  ───────┘ 
    «c: 2/══════════════════════════════════════════════
    «                                                   

    ['barrier', 'delay', 'if_else']

Re-checking the padded circuit passes:

```python
pm2 = PassManager([TimingCheck("ibm_heron", fail_on="refuted")])
pm2.run(eq)
P(pm2.property_set["qtiming_verdict"].verdict)
assert pm2.property_set["qtiming_verdict"].verdict == "PROVED-UNDER"
```

    PROVED-UNDER

## 4. `StripTimingAnnotations`: what you submit
IBM hardware does not take timing boxes (the lint warning `E-LINT-IBM-BOX` says so). The pass removes `timing.*` annotations and unwraps boxes that only carried them.

```python
plain = PassManager([StripTimingAnnotations()]).run(qc)
P(plain.draw("text"))
assert [i.operation.name for i in plain.data] == ["h", "cx", "cx", "h", "measure", "measure", "if_else"]
```

                        ┌───┐┌─┐                          
    q_0: ────────────■──┤ H ├┤M├──────────────────────────
         ┌───┐     ┌─┴─┐└┬─┬┘└╥┘                          
    q_1: ┤ H ├──■──┤ X ├─┤M├──╫───────────────────────────
         └───┘┌─┴─┐└───┘ └╥┘  ║   ┌──────  ┌───┐ ───────┐ 
    q_2: ─────┤ X ├───────╫───╫───┤ If-0  ─┤ X ├  End-0 ├─
              └───┘       ║   ║   └──╥───  └───┘ ───────┘ 
                          ║   ║ ┌────╨────┐               
    c: 2/═════════════════╩═══╩═╡ c_1=0x1 ╞═══════════════
                          1   0 └─────────┘               

## 5. The scheduling plug-in
`scheduling_method="qtiming"` runs `TimingCheck(fail_on="refuted")` then `StripTimingAnnotations()`. The contract comes from `QTIMING_CONTRACT`. It **replaces** Qiskit's own scheduling stage for that pass manager; nothing else is scheduled.

```python
os.environ["QTIMING_CONTRACT"] = "ibm_heron"
staged = generate_preset_pass_manager(optimization_level=0, scheduling_method="qtiming")
out = staged.run(qc)
P(staged.property_set["qtiming_verdict"].verdict, [i.operation.name for i in out.data])
assert staged.property_set["qtiming_verdict"].verdict == "PROVED-UNDER"
assert "box" not in [i.operation.name for i in out.data]
```

    PROVED-UNDER ['h', 'cx', 'cx', 'h', 'measure', 'measure', 'if_else']

## 6. Round trips: OpenQASM 3 and QPY
The annotations survive both. The OpenQASM 3 text is the same format the CLI reads, so you can hand a Qiskit-built circuit to `qtiming check`.

```python
text = qasm3_dumps(qc)
P(text)
assert "@timing.within 3000ns c[1]" in text and "@timing.policy eq" in text
back = qasm3_loads(text)
assert from_circuit(back).body.stmts[-1].annotations == box.annotations
```

    OPENQASM 3.0;
    include "stdgates.inc";
    bit[2] c;
    qubit[3] q;
    h q[1];
    cx q[1], q[2];
    cx q[0], q[1];
    h q[0];
    c[0] = measure q[0];
    c[1] = measure q[1];
    @timing.within 3000ns c[1]
    @timing.policy eq
    box {
      if (c[1]) {
        x q[2];
      }
    }
    

```python
with tempfile.TemporaryDirectory() as d:
    f = Path(d) / "tp.qpy"
    f.write_bytes(qpy_dumps(qc))
    via_qpy = from_qpy(str(f))
    assert qpy_loads(f.read_bytes()).num_qubits == 3
assert via_qpy.body.stmts[-1].annotations == box.annotations
P("QPY annotations:", via_qpy.body.stmts[-1].annotations)
```

    QPY annotations: (('policy', 'eq'), ('within', '3000ns c[1]'))

```python
with tempfile.TemporaryDirectory() as d:
    f = Path(d) / "tp.qasm"
    f.write_text(text, encoding="utf-8")
    code, out = _show.run("check", f, "--contract", "ibm_heron", show=False)
P(out.splitlines()[0])
assert code == 0 and out.startswith("PROVED-UNDER")
```

    PROVED-UNDER  (contract ibm_heron, policy sync, sha256 9cf4d27a06ae)

## What just happened
- `from_circuit` read a Qiskit circuit with `box` annotations; `TimingCheck` produced PROVED-UNDER (vendor-claimed feed-forward latency) and raised `TranspilerError` for a 300 ns deadline.
- `EqualizeBranches` rewrote the `if` with explicit `barrier` / `delay` padding; re-checking it still passes. `StripTimingAnnotations` and the scheduling plug-in produce a box-free circuit for submission.
- Annotations round-trip through OpenQASM 3 and QPY.
- Limits: loops are refused by `EqualizeBranches`; `TimingCheck` takes no `--assume` values (pass a loaded `Contract`); nothing here has run on real IBM hardware. See [Qiskit](../qiskit.md).
