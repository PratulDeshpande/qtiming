# Timing Checker: Technical Implementation Plan

Oct 26, 2026 · @Someone

## 1. What we are building

We are building **`qtiming`**, a Python package that takes a dynamic quantum program plus a hardware timing contract and returns one of four verdicts before the program runs: PROVED, PROVED-UNDER (assumptions), REFUTED (with a replayable counterexample), or UNKNOWN. It ships with a reference executor that replays counterexamples, a benchmark suite, and a Qiskit transpiler pass so it slots into normal workflows.

Think of it as a spell-checker for time. The program says what should happen and when. The contract says what the machine promises about how long things take. The checker asks one question: across every possible measurement outcome and every allowed latency, does anything arrive late, collide, or leave a gap nobody planned for?

### Scope of version 1.0 (the OOPSLA artifact)

| In scope | Out of scope (stated non-goals) |
| --- | --- |
| OpenQASM 3 / Qiskit circuits with mid-circuit measurement and `if`/`else` | Unbounded `while` loops |
| Bounded `for`, capped `while` (repeat-until-success) with an exhaust handler | Pulse-level `defcal` bodies |
| Three branch-timing policies: EQ, SYNC, EXP | Noise and fidelity modelling |
| Blocking classical calls with declared latency | Multi-controller sync protocols (abstracted as sync domains) |
| Provenance-typed contracts for 4 backend personalities | Decoder internals (a decoder is just a latency bound) |
| Static obligations O1–O9 and counterexamples | Qubit mapping and routing |
| Reference executor with 3 personalities | Mechanised proofs (Lean/Agda is a stretch goal) |

### Engineering principles

These rules decide every trade-off later in the plan.

1. **Soundness over completeness.** The checker may say UNKNOWN. It must never say PROVED for a program that can fail. Every solver tier is cross-checked against a slower, simpler one.
2. **Integers everywhere.** All times are integer multiples of the backend's `dt`. No floating point enters a solver, so no rounding can flip a verdict.
3. **Provenance travels with every number.** Each latency carries its evidence class. A verdict reports the weakest evidence it relied on.
4. **Cheap tier first.** Most programs are EQ-only and collapse to a plain simple temporal network (STN). The expensive CSTNU machinery runs only when it is needed.
5. **Every REFUTED is replayable.** A counterexample is a concrete outcome sequence plus latency values that the reference executor reproduces deterministically.
6. **Pure core, thin adapters.** The core IR and solvers never import Qiskit. Front ends and back ends are adapters, so the core stays testable and reusable.
7. **One artifact, every committee.** The repository is built from day one to pass artifact evaluation: pinned dependencies, Docker image, VM script, smoke test under 30 minutes.

## 2. System architecture

The system is a seven-stage pipeline: two inputs (program and contract) meet in a labelled timed event graph, which becomes a set of obligations, which a tiered solver discharges into a verdict. A reference executor sits beside the pipeline to replay counterexamples and to test soundness.

&#91;embedded content: checker architecture · 7 stages, 4 solver tiers\]

The event graph (highlighted) is the one representation every solver reads. The contract also feeds the obligation generator directly, and every REFUTED verdict must be reproduced by the executor before it is reported.

### Pipeline stages and their contracts

| # | Stage | Input | Output | Module |
| --- | --- | --- | --- | --- |
| 1 | Front end | `QuantumCircuit`, QPY, or OpenQASM 3 text | TQ core AST | `qtiming.frontend` |
| 2 | Contract loader | TOML/JSON contract file | validated `Contract` object | `qtiming.contract` |
| 3 | Elaboration | TQ AST + contract | elaborated AST (policies made explicit, loops unrolled or capped) | `qtiming.elab` |
| 4 | Graph builder | elaborated AST | labelled timed event graph (LTEG) | `qtiming.graph` |
| 5 | Obligation generator | LTEG + contract | list of obligations O1–O9 with provenance | `qtiming.oblig` |
| 6 | Solver dispatcher | obligations | per-obligation result | `qtiming.solve` |
| 7 | Verdict and witness | results | `Verdict` + optional `Counterexample` | `qtiming.verdict` |
| — | Reference executor | elaborated AST + contract + (ω, θ) | trace or violation | `qtiming.exec` |

Each stage is a pure function from an immutable input to an immutable output. That makes every stage independently unit-testable, cacheable, and easy to snapshot in regression tests.

### Repository layout

```text
qtiming/
├── pyproject.toml            # hatchling build, pinned extras: [qiskit], [z3], [dev]
├── CITATION.cff  LICENSE (Apache-2.0)  CONTRIBUTING.md
├── src/qtiming/
│   ├── core/                 # no Qiskit imports allowed (enforced by import-linter)
│   │   ├── ast.py            # TQ syntax tree (frozen dataclasses)
│   │   ├── time.py           # Dur (int dt), Interval, Provenance lattice
│   │   ├── labels.py         # outcome-label algebra (conjunctions of literals)
│   │   └── errors.py
│   ├── frontend/
│   │   ├── qiskit_fe.py      # DAG walk -> TQ AST
│   │   ├── qasm3_fe.py       # openqasm3 AST -> TQ AST (fallback)
│   │   └── annotations.py    # timing.* Annotation classes + serialisers
│   ├── contract/
│   │   ├── schema.py         # pydantic v2 models
│   │   ├── loader.py         # TOML/JSON -> Contract, unit normalisation
│   │   └── instances/        # artiq.toml, q1.toml, ibm_heron.toml, qua.toml
│   ├── elab/                 # EQ / SYNC / EXP elaboration, loop handling
│   ├── graph/                # LTEG builder, resource clocks
│   ├── oblig/                # O1..O9 generators
│   ├── solve/
│   │   ├── stn.py            # Bellman-Ford / Floyd-Warshall, negative-cycle witness
│   │   ├── scenario.py       # 2^k per-scenario STN enumeration
│   │   ├── smt.py            # Z3 QF_IDL / QF_LIA encodings
│   │   ├── cstnu.py          # own DC propagation (RUL- style) for STNU/CSTNU
│   │   └── cstnu_tool.py     # GraphML export + subprocess bridge to CSTNU Tool jar
│   ├── verdict/              # Verdict, Counterexample, pretty printers, SARIF output
│   ├── exec/                 # discrete-event reference executor + personalities
│   ├── qiskit_pass.py        # TimingCheck and EqualizeBranches transpiler passes
│   └── cli.py                # `qtiming check prog.qasm --contract ibm_heron.toml`
├── benchmarks/               # programs, contracts, expected verdicts (YAML)
├── tests/                    # unit, property (hypothesis), differential, golden
├── experiments/              # IBM probe notebooks + cached result data
├── docs/                     # mkdocs site, contract spec, tutorials
└── artifact/                 # Dockerfile, vm/ build script, smoke.sh, full.sh
```

### Dependency policy

| Dependency | Role | Pin | Why |
| --- | --- | --- | --- |
| Python | runtime | 3.11–3.13 | Matches current Qiskit support |
| `qiskit` | front end, pass manager | ≥ 2.3, tested on 2.6.x | Rust-native control flow; `BoxOp` annotations since 2.1 |
| `openqasm3` | raw-text fallback parser | 1.0.x | Covers programs Qiskit cannot import |
| `z3-solver` | SMT tier | 4.13+ | Difference logic and linear integer arithmetic |
| `networkx` | graph utilities, debugging only | 3.x | Not on the hot path |
| `pydantic` | contract schema | v2 | Validation with clear error messages |
| `hypothesis` | property tests | dev only | Random program and contract generation |
| CSTNU Tool 7.2 (Java) | oracle only | jar via subprocess | LGPL-3.0, never vendored or linked |

The core package has only `pydantic` as a hard dependency. Qiskit and Z3 are optional extras, so the core runs anywhere and reviewers can install it in seconds.

## 3. Core data model

The core is a small, frozen, Qiskit-free representation of "timed OpenQASM 3" (TQ): durations are integers in `dt`, latencies are integer intervals tagged with provenance, and every statement node carries a stable ID so errors and counterexamples can point back to the source line.

### Time primitives (`core/time.py`)

```python
from dataclasses import dataclass
from enum import IntEnum

class Prov(IntEnum):
    """Evidence class. Higher = stronger. Verdicts report the minimum used."""
    VENDOR = 0     # marketing claim, e.g. "<550 ns"
    MEAN_SD = 1    # mean ± sigma
    PCTL = 2       # percentile under a stated load
    MMAX = 3       # sample maximum over n runs
    CYC = 4        # cycle-counted design bound
    CERT = 5       # formally certified WCET

    @property
    def hard(self) -> bool:            # may discharge a hard deadline
        return self >= Prov.CYC

@dataclass(frozen=True, slots=True)
class Interval:
    lo: int            # in dt, inclusive
    hi: int            # in dt, inclusive; lo <= hi enforced in __post_init__
    prov: Prov
    source: str = ""   # citation / measurement id, carried into verdicts
    n: int | None = None   # sample count for MMAX

    def __add__(self, o: "Interval") -> "Interval":
        return Interval(self.lo + o.lo, self.hi + o.hi, min(self.prov, o.prov))
```

Design notes:

- **Why `IntEnum` and `min`.** Provenance forms a total order (a chain). Combining two latencies keeps the weaker class, so `min` is the correct join. If we later need incomparable classes, this becomes a proper lattice type with a `meet` method; the call sites do not change.
- **Why integer `dt`.** Contracts declare `dt` (for example 4 ns on IBM Heron and Qblox, 1 ns machine units on ARTIQ). The loader converts every number to `dt` once, rounding *outward* (lower bounds down, upper bounds up), which is the sound direction.
- **Overflow.** Python ints are unbounded, but exports to the Java oracle use 64-bit `long`. The exporter asserts every value fits.

### TQ abstract syntax (`core/ast.py`)

| Node | Fields | Notes |
| --- | --- | --- |
| `Gate` | `name, qubits, dur` | `dur` resolved from contract at elaboration |
| `Delay` | `qubits, dur, declared=True` | `declared` gaps are exempt from O4 |
| `Barrier` | `qubits` | zero-duration join on resources |
| `Measure` | `qubit, cbit, tier` | `tier` selects the feedback-latency path (self, intra, multicast, network) |
| `Reset` | `qubit` | may itself be conditional on some backends |
| `Seq` | `stmts` | n-ary for cache-friendliness |
| `Box` | `dur, body, annotations` | hard duration; carries `timing.*` annotations |
| `If` | `cond, then_, else_, policy` | `policy ∈ {EQ, SYNC(Δ,G), EXP}` |
| `For` | `var, n, body` | `n` static |
| `While` | `cond, body, cap, exhaust, policy` | `cap` mandatory, `exhaust` handler mandatory |
| `Call` | `fn, args, latency: Interval, blocking` | extern / `device_call` |
| `Within` | `deadline, anchor_cbit, body` | `body` must start ≤ deadline after `anchor_cbit` is valid |

Every node has `nid: int` (stable, assigned in source order) and `loc: SourceLoc` (file, line, column, or Qiskit instruction index). All nodes are `@dataclass(frozen=True, slots=True)`, so they hash cheaply and can be cached.

### Classical expressions and outcome labels (`core/labels.py`)

Conditions are restricted to what real controllers support: a single bit, a bit compared with a constant, or a register compared with a constant (IBM allows operands of up to 32 bits). The checker turns each condition into a **label**, a conjunction of literals over outcome propositions:

```python
@dataclass(frozen=True, slots=True)
class Lit:
    prop: str        # e.g. "c0@m17" = bit c0 written by measure node 17
    pos: bool

Label = frozenset[Lit]          # empty set = always true

def consistent(a: Label, b: Label) -> bool:
    return not any(Lit(l.prop, not l.pos) in b for l in a)
```

Propositions are keyed by the **measurement occurrence** (`bit@node`), not just the bit name. This matters because a bit can be overwritten in a loop, and two different measurements into the same bit are different observations.

A register comparison such as `c == 5` over 3 bits expands to the label `{c0, ¬c1, c2}`. An inequality such as `c > 2` expands into a disjunction of labels; the graph builder handles disjunctions by duplicating the branch body per disjunct (rare in practice, and capped at 32 disjuncts with a clear error).

## 4. Front end: getting programs in

The primary front end walks a Qiskit `QuantumCircuit` (or its DAG) and emits TQ; timing intent travels as custom `Annotation` objects on `BoxOp`, which round-trip through OpenQASM 3 and QPY without changing either language. A secondary front end parses raw OpenQASM 3 text with the `openqasm3` package for programs Qiskit cannot import.

### 4.1 The `timing.*` annotation namespace

Users express policy and deadlines by wrapping code in a `box` and attaching annotations. Example in OpenQASM 3 form:

```text
OPENQASM 3.0;
include "stdgates.inc";
qubit[3] q; bit[2] c;

h q[1]; cx q[1], q[2];          // Bell pair on q1, q2
cx q[0], q[1]; h q[0];
c[0] = measure q[0];
c[1] = measure q[1];

@timing.policy eq
@timing.within 3000ns from c[1]
box {
  if (c[1]) { x q[2]; }
  if (c[0]) { z q[2]; }
}
```

In Qiskit the same intent is:

```python
from qtiming.frontend.annotations import Policy, Within

with qc.box(annotations=[Policy("eq"), Within(3000, unit="ns", anchor=c[1])]):
    with qc.if_test((c[1], 1)):
        qc.x(2)
    with qc.if_test((c[0], 1)):
        qc.z(2)
```

| Annotation | Arguments | Meaning | Default when absent |
| --- | --- | --- | --- |
| `timing.policy` | `eq` \| `sync(Δ, G)` \| `exp` | branch policy for every `if`/`while` inside the box | contract's `branch.default_policy` |
| `timing.within` | duration, anchor bit | box must start within the deadline of the anchor becoming valid | none |
| `timing.cap` | integer N, exhaust label | iteration cap for a `while` in the box | `while` without cap → front-end error |
| `timing.pmin` | float | declared lower bound on per-iteration success probability (RUS) | none; expected-time verdict skipped |
| `timing.declared_idle` | — | gaps inside the box are intentional (exempt from O4) | not exempt |
| `timing.call` | function name, latency key | binds an extern to a contract latency entry | front-end error if unbound |

**Serialisation.** Since Qiskit 2.1, `qasm3.dumps(..., annotation_handlers={"timing": TimingHandler()})` and `qpy.dump(..., annotation_factories={"timing": ...})` route our namespace through custom handlers. We implement one `OpenQASM3Serializer` and one QPY serializer per annotation class, and a golden test that asserts `load(dump(c)) == c` for every benchmark. IBM's samplomatic also uses box annotations, so we keep our namespace distinct (`timing`) and add a test that a circuit carrying both namespaces round-trips intact.

### 4.2 Qiskit DAG walk

The front end walks `circuit.data` in order, keeping a per-qubit and per-clbit cursor, and maps instructions as follows:

| Qiskit instruction | TQ node | Duration source |
| --- | --- | --- |
| standard gate | `Gate` | `Target[name][qargs].duration` or contract override |
| `Delay(d, unit)` | `Delay(declared=True)` | converted to `dt`; `Stretch` resolved in elaboration |
| `Measure` | `Measure` | contract `measure.duration`, feedback `tier` from layout |
| `Reset` | `Reset` | contract |
| `IfElseOp` | `If` | policy from enclosing box or default |
| `ForLoopOp` | `For` | `n = len(indexset)` |
| `WhileLoopOp` | `While` | requires `timing.cap` |
| `SwitchCaseOp` | nested `If` chain | rejected on IBM-like contracts (unsupported there) |
| `BoxOp` | `Box` | `duration` may be a `Duration` or `Stretch` expression |
| `Barrier` | `Barrier` | zero |

Two engineering details matter:

- **Do not mutate in place.** From Qiskit 2.3 control flow is Rust-native. Our passes rebuild nodes and call `DAGCircuit.substitute_node()` rather than editing a box's annotations in place.
- **Stretch resolution.** OpenQASM 3 resolves `stretch` at compile time. We solve the stretch system as a small linear problem (each `box[d]` gives an equality; each stretch must be ≥ 0) and record the solved values. IBM restricts stretch to one per qubit set per barrier region, in the linear form X·stretch + Y; the front end checks that restriction when an IBM-like contract is selected and reports a precise error otherwise.

### 4.3 Validation errors the front end reports

- Unbounded `while` (no cap) — error, with a suggested `timing.cap` annotation.
- Measurement or reset inside a conditional, nested `if`, or any loop when the contract is IBM-like — error naming the IBM restriction.
- A bit read before any measurement writes it — error (would make the label meaningless).
- An `extern` call without a `timing.call` binding — error.

Each error is a structured object (`code`, `message`, `loc`, `hint`) and is also emitted as SARIF so editors and CI can show it inline.

## 5. The timing contract file

A contract is a per-backend TOML file, separate from the program, in which every number carries a provenance tag and a source; the loader validates it with pydantic, converts every value to integer `dt` with outward rounding, and refuses to load a contract with a missing required field.

### 5.1 Schema, clause by clause

```toml
[meta]
name = "ibm_heron_r2"
version = "0.1.0"
schema = "qtiming-contract/0.1"
personality = "ibm"                  # which executor personality replays it

[timebase]
dt_ns = 4
grid = { gate = 1, acquire = 16, feedback = 1 }   # alignment in dt (O8)

[timeline]
commit_lead = { lo = 0, hi = 0, prov = "vendor", source = "none published" }
late_policy = "compile_error"       # raise | drop_log | delay | defer_round | halt | compile_error

[branch]
class = "restricted"                # predicated | equalized | resync | restricted
default_policy = "sync"
allow_nested = false
allow_measure_in_branch = false
allow_loops = false
max_cond_bits = 32

[durations]                          # gate and measurement durations in ns
measure = { lo = 1660, hi = 1660, prov = "vendor", source = "IBM QPU info" }
cz = { lo = 68, hi = 68, prov = "vendor" }
sx = { lo = 32, hi = 32, prov = "vendor" }    # placeholder: read from Target at load

[[latency]]
name = "ff"                          # measurement end -> result usable by branch
src = "measure"; dst = "branch"; tier = "intra"
lo = 0; hi = 600; prov = "vendor"; source = "IBM blog, dynamic circuits"
data_dependent = false

[capacity]
instructions_per_qubit = 26_800_000

[idle]
max_unplanned_gap_ns = { default = 0 }   # G_r per resource; 0 = any undeclared gap is flagged
dd_inserted_by_backend = true

[loop]
while_supported = false
```

| Clause | Required | Feeds obligation | Validation rule |
| --- | --- | --- | --- |
| `meta` | yes | — | `schema` must match a supported version |
| `timebase` | yes | O8 | `dt_ns > 0`; grid values ≥ 1 |
| `timeline` | yes | O1 | `late_policy` from fixed enum |
| `issue_cost` | for Q1-like, ARTIQ-like | O1 | instruction → cycles, taken/not-taken for jumps |
| `capacity` | yes | O5 | lanes ≥ 1, FIFO depth ≥ 1 |
| `durations` | yes | all | `lo ≤ hi`; every gate in the program must resolve |
| `latency` | yes, ≥ 1 | O2, O3, O6 | unique names; `prov` from the six classes |
| `branch` | yes | policy compatibility | program policy must be ⊑ backend class |
| `dep` | optional | O2, O3 | deadline/freshness triple |
| `domain_call` | optional | O6 | WCET and RTT both present |
| `sync` | optional | O7 | cost per participant count and tier |
| `idle` | yes | O4 | `G_r ≥ 0` per resource or a default |
| `loop` | yes | O9 | consistency with `branch.allow_loops` |

### 5.2 Policy compatibility relation

The program asks for a policy; the backend offers a class. The checker accepts the pair only if the backend can implement the request. This is a small table, coded as a frozen dict and unit-tested exhaustively:

| Program policy ↓ / backend class → | predicated (Q1) | equalized | resync (QUA, QubiC) | exposed (ARTIQ) | restricted (IBM) |
| --- | --- | --- | --- | --- | --- |
| EQ | native | native | via padding pass | via explicit delays | via padding pass, only if no nesting |
| SYNC(Δ, G) | reject (cannot express a join gap) | reject | native | via explicit resync delay | native for single `if_test` |
| EXP | reject | reject | reject | native | reject |

"Via padding pass" means our `EqualizeBranches` pass rewrites the program so the backend's native behaviour realises EQ. "Reject" produces a REFUTED verdict of kind `policy-incompatible`, which is exactly the portability finding we want to measure (hypothesis H4).

### 5.3 The four shipped instances

Each instance is written only from public documentation, with every number's source in the `source` field. Where a number is unpublished, the field is present with `prov = "vendor"` and an explicit placeholder flagged in the instance's README, so a verdict depending on it reads PROVED-UNDER.

| Instance | dt | Branch class | Key latencies (as published) | Known gaps to fill |
| --- | --- | --- | --- | --- |
| `artiq.toml` | 1 ns (mu) | exposed | none numeric | input→output latency; slack lead |
| `q1.toml` | 4 ns | predicated | 160 / 250 / 472 ns (self / intra / multicast); jump 16 ns taken, 4 ns not | none for FPGA-local path |
| `ibm_heron.toml` | 4 ns | restricted | \~600 ns feedforward; measurement 1.66 µs | join behaviour for unequal branches (probe, Section 14) |
| `qua.toml` | 4 ns | resync | 224 ns active reset (vendor) | sync-gap bound ("a few cycles") |

### 5.4 Loader implementation

1. Parse TOML with `tomllib` (stdlib) or JSON.
2. Validate against the pydantic model; collect all errors, not just the first.
3. Convert ns → `dt`: `lo_dt = floor(lo_ns / dt_ns)`, `hi_dt = ceil(hi_ns / dt_ns)`. Record a warning when rounding changes a value.
4. Cross-check against a Qiskit `Target` if one is supplied: gate durations in the contract override the Target only when the contract's provenance is at least as strong; otherwise warn.
5. Freeze into an immutable `Contract` and compute a SHA-256 of the canonical form. Every verdict records this hash, so results are traceable to the exact contract version.

## 6. Policy elaboration

Elaboration rewrites the program so that each branch's timing policy becomes explicit structure: EQ inserts padding delays, SYNC inserts a join event with a contingent gap, EXP inserts explicit cursor operations, and loops are unrolled or capped. After this stage, no later stage needs to know what a "policy" is; it only sees delays, joins and contingent links.

The pass is a recursive function `elab(stmt, Γ) -> (stmt', [l, u], Γ')`, where Γ maps each classical bit to its valid-time interval relative to the current point, and `[l, u]` is the statement's duration interval. This is the typing judgement from the feasibility report, implemented directly.

### 6.1 EQ (equalize)

The branch waits until the result is valid in the *worst* case, then both arms are padded to the longer arm.

```python
def elab_if_eq(node, env):
    a, b = env.valid[node.cond_bit]                 # result valid in [a, b] from now
    s1, (l1, u1) = elab(node.then_, env)
    s2, (l2, u2) = elab(node.else_, env)
    if l1 != u1 or l2 != u2:
        raise ElabError("EQ requires fixed-duration arms", node.loc)  # nested SYNC/EXP inside EQ
    w, d = max(0, b), max(u1, u2)
    pad = lambda s, di: Seq([WaitUntil(w), s, Delay(d - di, declared=True)])
    return If(node.cond, pad(s1, u1), pad(s2, u2), EQ), (w + d, w + d)
```

`WaitUntil(w)` is a marker that later becomes a requirement edge "branch start ≥ measure end + hi(latency)". The idle cost of EQ is (b − θ) + (d − d\_taken), where θ is the realised latency. We record that cost per branch so the evaluation can report it (hypothesis H5).

### 6.2 SYNC(Δ, G) (synchronise at join)

Each arm runs as soon as the result arrives; a runtime barrier rejoins all resources afterwards.

- Insert a `Join` node after the `If` covering every resource touched by either arm.
- Attach a contingent gap λ = `contract.sync.cost(n_participants, tier)` to the join.
- Emit the side condition (b − a) + (max uᵢ − min lᵢ) + (λ\_hi − λ\_lo) ≤ Δ, and gap\_r ≤ G for each resource r.
- Duration interval: \[max(0, a) + min lᵢ + λ\_lo, max(0, b) + max uᵢ + λ\_hi\].

If the contract has no sync-gap bound, λ gets `hi = +∞` with `prov = VENDOR`, and any obligation depending on it comes back UNKNOWN with a message naming the missing field. That is honest and useful: it tells vendors which number to publish.

### 6.3 EXP (exposed timeline)

The ARTIQ model. Arms are not padded; the programmer owns the cursor.

- Each measurement-dependent read is modelled as moving the cursor to "now + negative slack", as ARTIQ does after an input read.
- Every subsequent output event carries an O1 obligation: slack at commit ≥ commit lead.
- Explicit `delay` statements in the source are kept as-is; they are how the programmer restores slack.

### 6.4 Loops

| Construct | Strategy | Threshold |
| --- | --- | --- |
| `for i in [0, n)` with n ≤ 64 | unroll; each copy gets fresh proposition names (`c0@m17#i3`) | default 64, configurable |
| `for` with n > 64 | summarise: check one iteration symbolically, prove the slack invariant (O9), multiply duration | invariant must hold or verdict is UNKNOWN |
| `while` with cap N | unroll to N iterations, each guarded by "not yet succeeded", plus the exhaust handler | N ≤ 64 unrolled; above, summarised |
| RUS with `timing.pmin` | add expected-time and tail verdicts (Section 10.3) | — |

Fresh proposition names per iteration are essential. Without them, the solver would wrongly believe iteration 3's outcome is known when iteration 1 runs.

### 6.5 Blocking calls and deadlines

- `Call` with `blocking = true` becomes a contingent link of length WCET(f) + RTT on the classical issue resource; all later operations on that resource are ordered after it (O6).
- `Within(D, c, body)` becomes a requirement edge: start(first op of body) − valid(c) ≤ D (O3).

### 6.6 Outputs of elaboration

The elaborated AST is still valid TQ, so it can be printed back to OpenQASM 3 for inspection. The `EqualizeBranches` Qiskit pass uses exactly this: it runs EQ elaboration and re-emits a circuit with explicit `delay` instructions, so downstream passes such as dynamical-decoupling insertion see fixed windows.

## 7. The labelled timed event graph (LTEG)

The LTEG is the single intermediate representation every solver reads: nodes are time-points (an operation's start or end, a result becoming valid, a commit), edges are difference constraints or contingent links, and every node and edge carries a label saying under which measurement outcomes it exists. It is a CSTNU in all but name, kept in our own format so the cheap solvers can read it directly.

### 7.1 Data structures

```python
@dataclass(frozen=True, slots=True)
class TP:                       # time-point
    id: int
    kind: Literal["start", "end", "valid", "issue", "join", "origin"]
    nid: int                    # source AST node
    resource: str | None        # "q3", "frame:q3.drive", "core", ...
    label: Label                # outcomes under which this point exists
    obs: str | None = None      # proposition observed here (valid-points of measurements)

@dataclass(frozen=True, slots=True)
class Req:                      # requirement: t[dst] - t[src] <= w, under label
    src: int; dst: int; w: int; label: Label; why: str   # why = obligation / rule tag

@dataclass(frozen=True, slots=True)
class Cont:                     # contingent link: t[dst] - t[src] in [lo, hi], chosen by nature
    src: int; dst: int; lo: int; hi: int; prov: Prov; label: Label; why: str

class LTEG:
    tps: list[TP]; reqs: list[Req]; conts: list[Cont]
    origin: int                 # absolute zero
    props: dict[str, int]       # proposition -> observation time-point
```

Storage is plain arrays plus index maps (`out_edges[tp]`, `in_edges[tp]`). For a typical benchmark (a few hundred time-points) this is faster and easier to debug than a general graph library.

### 7.2 Construction rules

| Program element | Time-points | Edges |
| --- | --- | --- |
| gate U on qubits q̄, duration δ | `start`, `end` per op | `end − start ≤ δ` and `start − end ≤ −δ` (equality as two edges) |
| resource order on r | — | `start(next) − end(prev) ≥ 0`, i.e. `end(prev) − start(next) ≤ 0` |
| multi-qubit gate | one `start` shared by all qubits | `start ≥ end(prev on each qubit)` |
| measurement into c | `start`, `end`, `valid` | duration equality; `Cont(end → valid, [lo, hi])` from contract tier; `valid.obs = "c@m"` |
| `if` arm | all points inside get `label ∧ lit` | as above |
| EQ `WaitUntil` | — | `start(arm) − end(measure) ≥ hi(latency)` |
| SYNC join | `join` point | `Cont(join_in → join, [λlo, λhi])`; spread `≤ Δ` |
| declared delay d | `start`, `end` | duration equality; marked declared (O4 exempt) |
| `within[D] from c` | — | `start(first) − valid(c) ≤ D` |
| commit (EXP, Q1) | `issue` point per output event | `start(e) − issue(e) ≥ commit_lead` |

### 7.3 Two invariants checked after construction

1. **Label well-formedness.** An edge's label must imply both endpoint labels. If not, the builder has a bug; we assert and fail loudly.
2. **Causality of observations.** A point whose label mentions proposition p must not be forced to occur before p's observation point. This is condition (iii) of the DMO definition; it is checked structurally here and semantically by the solvers.

### 7.4 Size and windowing

Let N be time-points and K the number of contingent links. Each gate adds 2 points, each measurement 3, so a 50-op circuit with 6 measurements has about 120 points. QEC and RUS programs are long but repetitive, so the builder supports **windows**: a cut at a round boundary where every resource passes through a join. Each window is solved separately with the previous window's end-time interval as its start, which keeps K per window small. Proving that this composition is sound is one of the paper's technical results; the implementation keeps a flag `window_composition = off` so we can compare against whole-program solving in tests.

## 8. Obligation generator (O1–O9)

Each obligation is a small, named, independently checkable claim about the LTEG, with a pointer to the source node it protects and the provenance of every latency it depends on. Generating them separately (rather than one giant query) gives precise error messages and lets the dispatcher route cheap obligations to cheap solvers.

```python
@dataclass(frozen=True)
class Obligation:
    code: Literal["O1","O2","O3","O4","O5","O6","O7","O8","O9"]
    nid: int                         # program node it protects
    label: Label                     # outcomes under which it must hold
    constraints: list[Req]           # extra edges whose violation = failure
    deps: frozenset[int]             # contingent links it relies on
    weakest_prov: Prov               # min over deps
    hard: bool                       # from contract: hard deadline or advisory
    message: str                     # human text for the report
```

| Code | Name | What it checks (plain words) | Encoding | Typical solver |
| --- | --- | --- | --- | --- |
| O1 | No underflow | Every output event is issued early enough before it must play | `start(e) − issue(e) ≥ Δ_lead`, where `issue(e)` = WCET of the classical stream up to e | STN (+ classical WCET from `issue_cost`) |
| O2 | Result ready | A branch never acts on a bit before it is valid | EQ: `start(arm) ≥ end(M) + hi(ℓ)`; EXP/SYNC: dispatched on observation | STN / STNU DC |
| O3 | Deadline | A `within[D]` body starts in time | `start(first) − valid(c) ≤ D` under every θ | STNU DC |
| O4 | No unplanned idle | No undeclared gap longer than G\_r on a resource | `start(next) − end(prev) ≤ G_r` unless declared | STN per scenario |
| O5 | Capacity | No more events per coarse cycle than lanes; FIFO never overflows; lane timestamps increase | counting over a fixed schedule; sliding window | direct computation, or SMT if times are symbolic |
| O6 | Domain call | Enough slack at a blocking call for WCET + RTT | `slack(call) ≥ WCET(f) + RTT_max` | STN |
| O7 | Sync bound | Join spread within Δ | `(λ_hi − λ_lo) + spread ≤ Δ` | STNU DC |
| O8 | Grid | Every timestamp sits on its op class's grid | `t_e ≡ 0 (mod g)` | SMT (QF\_LIA) only when times are not fixed; else arithmetic |
| O9 | Loops | Worst case bounded; slack does not shrink across iterations | bounded: n·u; capped: N·u + u\_exhaust; `slack_after ≥ slack_before` | STN on one iteration + induction |

### 8.1 Why O5 catches ARTIQ's silent drops

ARTIQ drops events on sequence, collision and busy errors without raising an exception. O5 turns those runtime conditions into static checks: with 8 SED lanes and a coarse cycle of 8 ns, more than 8 events with timestamps in the same coarse slot, or a non-monotonic timestamp on one lane, is a static violation. Because the check runs on every scenario, it covers rare branches that a test bench would never exercise.

### 8.2 Classical WCET for O1

For Q1-like contracts the classical sequencer has a documented cycle table (for example 4 ns for set/move, 12 ns for ALU ops, 16/4 ns for taken/not-taken jumps). We compute `issue(e)` by a straight-line walk over the elaborated program, using the taken cost on every branch (sound upper bound). Loops multiply by their bound. This is a deliberately simple IPET: no caches, no pipelines, so the walk is exact for straight-line code and sound otherwise.

### 8.3 Hard versus advisory

An obligation is **hard** if the contract marks it so (for example a fault-tolerance reaction deadline) and **advisory** otherwise. Hard obligations may be discharged only with latencies whose provenance is `CYC` or `CERT`. If a hard obligation holds but relies on weaker evidence, the verdict is PROVED-UNDER, never PROVED.

## 9. Solver tiers

The dispatcher sends each window to the cheapest tier that is exact for its shape: a plain STN when outcomes do not affect timing, per-scenario STNs when few outcome bits matter, dynamic-controllability propagation when latencies are uncertain and the schedule must react, and Z3 only for grids, rates and symbolic parameters. Every tier returns either a proof or a witness, never just "false".

### 9.1 Dispatch rule

1. Count k = timing-relevant propositions in the window (those whose labels appear on any requirement edge that differs between branches).
2. If k = 0 and every contingent link is handled by EQ padding → **Tier A (STN)**.
3. Else if the window has no contingent links that the schedule must react to (all EQ), and k ≤ 12 → **Tier B (scenario enumeration)**.
4. Else if k = 0 but reactive contingent links exist (EXP, SYNC) → **Tier C1 (STNU DC)**.
5. Else → **Tier C2 (CSTNU DC)**.
6. Any obligation with modular or rate constraints, or with symbolic `stretch` parameters → also **Tier D (SMT)**.

The thresholds (k ≤ 12, i.e. ≤ 4,096 scenarios) are configuration values. We tune them on the benchmark suite and report the chosen values in the paper.

### 9.2 Tier A: STN consistency (Bellman–Ford with witness)

Build the distance graph: for each requirement `t[v] − t[u] ≤ w`, an edge u → v with weight w. Under EQ, contingent links are replaced by their worst-case end (hi) and best-case end (lo) as two requirement edges, which is sound for strong controllability over latencies. The network is consistent iff the graph has no negative cycle.

```python
def bellman_ford(n, edges, src):
    dist = [INF] * n; dist[src] = 0; pred = [-1] * n
    for _ in range(n - 1):
        changed = False
        for (u, v, w, tag) in edges:
            if dist[u] + w < dist[v]:
                dist[v] = dist[u] + w; pred[v] = (u, tag); changed = True
        if not changed: return dist, None
    for (u, v, w, tag) in edges:
        if dist[u] + w < dist[v]:
            return None, extract_cycle(pred, v)     # negative cycle = conflict
    return dist, None
```

The negative cycle is the witness: a short loop of constraints that cannot all hold. Each edge carries its `tag` (obligation code and source node), so the cycle maps straight to a human explanation such as "O2 at line 14 requires ≥ 2,260 ns but box at line 12 allows ≤ 2,000 ns". A virtual source with zero-weight edges to every node avoids reachability gaps. Complexity O(N·E); for all-pairs tightness (used to compute the minimal schedule) we run Floyd–Warshall, O(N³), only on small windows.

### 9.3 Tier B: per-scenario enumeration

For each of the 2^k assignments ω to timing-relevant propositions, project the LTEG to the edges whose labels are consistent with ω and run Tier A. Scenarios are independent, so we run them in a process pool. We also apply two prunings:

- **Label projection caching.** Many scenarios produce identical projected graphs; hash the edge set and solve each distinct graph once.
- **Early exit.** Stop at the first failing scenario when the user asks only for a verdict; continue when they ask for the full failure set.

This tier gives strong controllability over outcomes and latencies, which is exactly what EQ promises (DMO).

### 9.4 Tier C1: STNU dynamic controllability

When the schedule may react to observed latencies (EXP and SYNC), we need dynamic controllability (DC): a dispatcher that waits for each contingent link to finish, then reacts, must always succeed. We implement a published DC-checking algorithm in our own code, following Cairo, Hunsberger and Rizzi's RUL⁻ (complexity O(MN + K²N + KN log N)). Implementation plan:

1. Normal form: split contingent links with lo > 0 into a requirement plus a zero-start contingent link.
2. Build the labelled distance graph with ordinary, upper-case and lower-case edges.
3. Run the propagation rules to a fixpoint; detect a semi-reducible negative cycle.
4. On failure, return the cycle plus the contingent durations it fixes at their extremes; this becomes the counterexample θ.

Because DC checking is subtle, we treat our implementation as untrusted until it agrees with two oracles (Section 12): the CSTNU Tool and HEATlab's Prob-in-Ctrl checker with its 452 DC and 169 non-DC example networks.

### 9.5 Tier C2: CSTNU dynamic controllability

The general case: outcomes and latencies both uncertain, and the schedule reacts to both. Dynamic consistency of conditional STNs is PSPACE-complete in general, so we do not implement our own complete algorithm in v1. Instead:

- **Export** the window to the CSTNU Tool's GraphML format and run the jar in a subprocess with a timeout (default 60 s).
- **Parse** its verdict and, on failure, its negative-cycle report back into our IDs.
- **On timeout**, return UNKNOWN with the window and its k, so the user can split or annotate.

Windowing (Section 7.4) is what keeps this tier practical: in QEC and RUS benchmarks each round's outcome affects only that round's correction, so k per window stays small.

### 9.6 Tier D: SMT (Z3)

Used only where difference constraints are not enough:

| Use | Logic | Example |
| --- | --- | --- |
| Grid alignment (O8) with symbolic times | QF\_LIA | `t = 16·k` for acquire on IBM |
| Stretch systems with linear coefficients | QF\_LIA | X·stretch + Y = box duration |
| Rate constraints (issue rate ≤ allowed) | QF\_LIA | eQASM-style R\_req ≤ R\_allowed |
| Parametric questions | QF\_LIA + optimisation | "largest feedforward latency for which this program is still safe" |

The parametric query is a useful by-product: for a PROVED-UNDER verdict, Z3's `Optimize` gives the maximum latency at which the proof still holds. Reporting that number ("safe as long as feedforward ≤ 740 ns") is more useful to users and vendors than a yes/no.

## 10. Verdicts and counterexamples

A verdict is a structured, serialisable object that states the result, the weakest evidence it rests on, and (when REFUTED) a counterexample that the reference executor replays to the same violation. Output formats are a terminal report, JSON for tooling, and SARIF for editors and CI.

### 10.1 Verdict lattice

| Verdict | Meaning | When produced |
| --- | --- | --- |
| PROVED | All obligations hold for every ω and θ, using only `CYC`/`CERT` latencies for hard obligations | rare today; possible on Q1-like FPGA-local paths |
| PROVED-UNDER | All obligations hold, assuming the listed latencies are true bounds | the common case on real contracts |
| REFUTED | At least one obligation fails for a concrete (ω, θ) | witness found |
| UNKNOWN | A tier timed out, or a needed bound is missing (`hi = +∞`) | names the missing field or the window |

The program-level verdict is the worst over its obligations, in the order REFUTED < UNKNOWN < PROVED-UNDER < PROVED.

```json
{
  "verdict": "PROVED-UNDER",
  "contract": {"name": "ibm_heron_r2", "sha256": "…"},
  "assumptions": [
    {"latency": "ff", "hi_ns": 600, "prov": "vendor", "source": "IBM blog"}
  ],
  "margins": [{"obligation": "O3", "nid": 41, "slack_ns": 740}],
  "max_safe": {"ff": 1340},
  "policy_cost": {"eq_idle_ns": 600},
  "tiers_used": ["A", "D"], "time_ms": 38
}
```

### 10.2 Counterexamples

A counterexample is the tuple (ω, θ, event, obligation):

- **ω**: the outcome prefix along the failing path, e.g. `{c0@m3: 1, c1@m4: 0}`.
- **θ**: a value for every contingent link on that path. Strong-controllability failures need only interval endpoints, so θ is chosen from {lo, hi} per link; DC failures take the values fixed by the negative cycle.
- **event**: the AST node and timestamp where the violation happens.
- **obligation**: which of O1–O9 failed, with the numeric gap ("late by 120 ns").

**Minimisation.** Before reporting, we shrink the witness: set every link not in the conflict cycle to its midpoint and every irrelevant proposition to "don't care", then re-check. The user sees only what matters.

**Replay.** Every REFUTED verdict is automatically replayed in the reference executor with the matching personality. If the executor does not reproduce the violation, the checker reports an internal error rather than the counterexample. This catches solver bugs in normal use, not just in tests.

### 10.3 Repeat-until-success verdicts

For a capped loop with body duration T, cap N, exhaust handler T\_exhaust, and declared p\_min, the report gives three numbers instead of one:

```latex
\mathrm{WCET}_{\text{cap}} = N\,T + T_{\text{exhaust}}, \qquad
\mathbb{E}[T] = T\,\frac{1-(1-p_{\min})^{N}}{p_{\min}}, \qquad
\Pr[\text{exhaust}] = (1-p_{\min})^{N}
```

If a `within[D]` deadline encloses the loop, the report also gives the probability of missing D: with m = floor(D / T) iterations fitting inside D, the miss probability is (1 − p\_min)^m. Using p\_min (a declared lower bound on success) makes all three numbers conservative. These are elementary geometric-distribution formulas, implemented in exact rational arithmetic (`fractions.Fraction`) and only rounded for display.

### 10.4 Report rendering

The terminal report has four parts: the verdict line, the assumptions table, the failing obligations with source excerpts, and an ASCII timeline of the counterexample (one row per resource, branch arms shaded). The same data drives an optional HTML timeline in the docs site.

## 11. Reference executor

The reference executor is a deterministic discrete-event interpreter for elaborated TQ that, given an outcome stream ω and a latency realisation θ, produces a timestamped trace or a violation. It is deliberately independent of the solvers (it shares only the AST and contract types), so agreement between the two is real evidence of soundness.

### 11.1 Engine

- **Event queue.** A binary heap keyed by (time, sequence number). The sequence number makes ties deterministic.
- **State.** Per-resource clocks τ, classical store σ, result-valid times V, and personality-specific state (cursor and slack for ARTIQ, RT queue for Q1, block state for IBM).
- **Nature.** ω and θ come from an `Oracle` object with three implementations: `Fixed` (replay a counterexample), `Random(seed)` (property tests), and `Extreme` (every link at lo or hi, chosen adversarially).
- **No quantum state.** The executor tracks timing only. Outcomes come from ω, so we never simulate amplitudes. This keeps it fast (millions of events per minute in pure Python) and keeps it out of fidelity modelling, which is a non-goal.

### 11.2 Personalities

Each personality is a subclass that overrides four hooks: `on_branch`, `on_join`, `on_commit`, `on_late`. Behaviour comes only from public documentation; undocumented behaviour is a constructor parameter, never a hidden guess.

| Hook | ARTIQ-like | Q1-like | IBM-like |
| --- | --- | --- | --- |
| `on_branch` | cursor continues; input read leaves negative slack | `set_cond`; false path waits `else_duration` | single `if_test`; fast-path blocks padded to the longest block |
| `on_join` | none (programmer's delays) | none (equal by construction) | block restart; behaviour for unequal branches = parameter until the probe settles it |
| `on_commit` | event enters RTIO FIFO; 8 SED lanes | RT queue push; 32-entry feedback queue | n/a (static schedule) |
| `on_late` | underflow → raise; sequence/collision/busy → **drop and log** | RT queue empty → **halt** with underflow error | validation failure (job rejected) |

The ARTIQ "drop and log" behaviour is modelled faithfully: the event disappears from the trace, and a `SilentDrop` record is appended. That is how the evaluation shows that a static checker catches what a run cannot see.

### 11.3 Cross-check against an external simulator

For the Q1-like personality we also run selected programs through q1simulator (MIT licence), which models the Q1 core's buffer and aborts on underrun. Agreement on underflow/no-underflow for those programs validates our Q1 model independently.

### 11.4 API

```python
res = execute(prog_elab, contract, oracle=Fixed(omega, theta), personality="artiq")
res.trace        # list[(t_dt, resource, op, nid)]
res.violations   # list[Violation(kind, nid, t_dt, detail)]
res.drops        # silent drops (ARTIQ-like)
```

## 12. Testing and verification strategy

The checker's whole value is that PROVED can be trusted, so testing is organised around catching false proofs: five layers, from unit tests up to differential testing against independent oracles, with the soundness check (hypothesis H1) run in CI on every commit.

| Layer | What it tests | Tool | Volume | Runs |
| --- | --- | --- | --- | --- |
| 1. Unit | each module in isolation (interval arithmetic, label algebra, Bellman–Ford, elaboration rules) | pytest | \~400 tests | every commit, < 1 min |
| 2. Golden | end-to-end verdicts on the benchmark suite match stored expectations | pytest + YAML | \~60 programs × 4 contracts | every commit |
| 3. Property | invariants over random programs and contracts | hypothesis | 2,000 examples per property in CI, 100,000 nightly | commit + nightly |
| 4. Differential (soundness) | checker vs reference executor | custom harness | ≥ N randomised + extreme runs per program (N pre-registered) | nightly |
| 5. Oracle | our DC solver vs CSTNU Tool and Prob-in-Ctrl | subprocess + Python | 452 DC + 169 non-DC STNUs, plus every exported window | nightly |

### 12.1 Key properties (layer 3)

1. **Soundness.** If `check(P, C)` is PROVED or PROVED-UNDER, then for every sampled (ω, θ) within C, `execute(P, C, ω, θ)` has no violation.
2. **Witness validity.** If REFUTED with (ω, θ), then `execute` with that (ω, θ) reproduces the same obligation failure.
3. **Monotonicity in contracts.** Tightening any latency interval never turns PROVED into REFUTED.
4. **Monotonicity in provenance.** Upgrading provenance never weakens a verdict.
5. **Tier agreement.** On any window where several tiers apply, they agree (Tier A = Tier B with k = 0; Tier B ⇒ Tier C1 DC; C1 = oracle).
6. **Elaboration idempotence.** Elaborating an already-elaborated program changes nothing.
7. **Round-trip.** `load(dump(c)) == c` for OpenQASM 3 and QPY with `timing.*` annotations.

### 12.2 Random program generator

A hypothesis strategy builds well-typed TQ programs: 1–8 qubits, 0–6 measurements, `if` nesting up to depth 3, bounded loops up to 4 iterations, random policies, plus random contracts with intervals in \[0, 2,000\] dt. Shrinking produces minimal failing programs, which become new golden tests.

### 12.3 Exhaustive ground truth for precision (H2)

For programs small enough (k ≤ 10, ≤ 6 contingent links), we enumerate every ω and every θ at the endpoints in the executor. That gives the true answer, so we can measure false alarms (checker says REFUTED or UNKNOWN, but no reachable violation exists).

### 12.4 Mutation testing

We run `mutmut` on `solve/` and `oblig/` monthly. Each surviving mutant in a solver is a gap in the tests. The target is a mutation score of at least 85% on those two packages before the OOPSLA submission.

## 13. Benchmarks and evaluation harness

The benchmark suite has about 60 programs in seven families, each run against all four contracts and three policies, with expected verdicts stored in YAML; one command regenerates every table and figure in the paper from scratch.

### 13.1 Benchmark families

| Family | Programs | Why it is there | Main obligations exercised |
| --- | --- | --- | --- |
| Teleportation and gate teleportation | 6 | canonical feedforward; fits IBM restrictions | O2, O3, O4 |
| Active reset | 4 | simplest conditional; vendor latency claims exist | O2, O4 |
| Long-range CNOT / GHZ via measurement | 8 | many parallel conditionals, wide joins | O4, O7 |
| Repeat-until-success gate synthesis | 8 | capped loops, expected-time verdicts | O9, O3 |
| Repetition code and small surface-code rounds (d = 3, 5) | 12 | rare correction branches, windowing | O2, O3, O5 |
| Magic-state injection with conditional S, `within[D]` | 6 | fault-tolerance reaction deadline | O3 (hard) |
| Lattice-surgery merge/split with patch-sync slack | 6 | sync policies, modelled on Maurya & Tannu | O7 |
| ARTIQ manual kernels in EXP form | 6 | negative slack, silent drops, not written by us | O1, O5 |
| Dynamarq programs (where available) | \~10 | external, reduces benchmark bias | all |

Each benchmark is a directory: `prog.qasm` (or `prog.py`), `meta.yaml` (family, expected verdict per contract and policy, notes), and an optional `ground_truth.json` from exhaustive enumeration.

### 13.2 Experiments mapped to hypotheses

| Hypothesis | Experiment | Metric | Output |
| --- | --- | --- | --- |
| H1 Soundness | differential runs on all benchmarks + 10,000 random programs | executor violations on PROVED programs (must be 0) | table |
| H2 Precision | exhaustive enumeration on small programs | false-alarm rate | table |
| H3 Scalability | sweep circuit size and k per window; windowing on/off | check time, % certified within time limit | scaling plot (log time vs size) |
| H4 Portability | same source × 4 contracts | % of dynamic programs with differing verdicts | verdict matrix heatmap |
| H5 Policy cost | EQ vs SYNC on QEC and RUS families, IBM-like latencies | added idle time (%) | bar chart |
| H6 Hardware | IBM delay sweep (Section 14) | inferred window vs \~600 ns | fit plot |
| — | provenance dependence | count of verdicts resting on non-certified numbers | headline number |

Thresholds (⟨N⟩, ⟨x⟩%, ⟨y⟩%, and so on) are fixed in a pre-registration file committed to the repository with a dated tag before the evaluation runs, so they cannot drift to fit the results.

### 13.3 Harness

```bash
qtiming-bench run --suite benchmarks/ --contracts all --policies eq,sync,exp \
                  --repeat 5 --timeout 60 --out results/2027-03-15/
qtiming-bench report results/2027-03-15/ --figures paper/figs/ --tables paper/tables/
```

- Results are written as Parquet (one row per program × contract × policy × repetition) with the git commit, contract hashes, machine info, and package versions.
- Timing measurements use 5 repetitions and report the median and interquartile range; the machine spec is recorded in the paper.
- Figures are produced by plain matplotlib scripts in `paper/figs/`, each reading only from the Parquet file. No hand-edited numbers enter the paper.

## 14. IBM hardware probe

The probe answers one question the documentation does not: when an `if`/`else` on an IBM Heron device has arms of unequal length, are they padded to equal length or does the timeline diverge until a join? It uses ibm\_kingston on the Open Plan budget (10 minutes per 28 days, plus a 180-minute opt-in), so it is designed to be small and to read timing from physics rather than timestamps. This is a proposed method and has not been tested yet.

### 14.1 Experiment design

The idea: a spectator qubit in superposition accumulates phase at a known detuning while it waits. If the branch timing differs between outcomes, the spectator's phase differs between the two outcome-conditioned subsets of shots. Measuring that phase difference reveals the timing difference.

1. Prepare a control qubit qc in |+⟩ and measure it mid-circuit (random outcome, roughly 50/50).
2. Prepare spectator qs in |+⟩ before the measurement.
3. Branch on the outcome: arm A = one `x` on a third qubit; arm B = a `delay[d]` plus `x`, with d swept over 0, 100, 200, …, 1,000 ns.
4. After the `if`, apply a virtual Z rotation φ on qs (swept over 8 values), then H, then measure qs.
5. Post-select shots by qc's outcome and fit the Ramsey fringe of qs in each subset.

If arms are padded (EQ-like), the fringe phase is the same for both subsets at every d. If the timeline diverges (SYNC-like), the phase difference grows linearly with d, with slope 2π·δf, where δf is the qubit's detuning from its frame. Run with dynamical decoupling on and off; DD should suppress decay but, unless it is outcome-aware, not the relative phase.

### 14.2 Budget

| Item | Value |
| --- | --- |
| Circuit variants | 11 delays × 8 phases × 2 DD settings = 176 |
| Shots per variant | 2,000 |
| Estimated QPU time | within the 10-minute monthly allowance if batched in one job; split across two months if not (to be confirmed with a dry run on 10 variants first) |
| Data stored | raw counts JSON + fitted parameters, in `experiments/ibm_probe/` |

### 14.3 What each outcome means for the project

- **Padded:** set the IBM-like personality's `on_join` to EQ-like padding; tag with `prov = mmax(n)` from our fit.
- **Diverging:** set it to SYNC-like with the fitted gap; the portability finding (H4) strengthens.
- **Inconclusive:** keep the documented fast-path padding behaviour, tag it `vendor`, and report the inconclusive result in the paper's threats-to-validity section.

Either clean outcome is publishable on its own, which is why the publication plan keeps an optional QCE empirical paper.

## 15. Packaging, CI, artifact and reproducibility

The repository is public from early November 2026 under Apache-2.0, so the six-month public history JOSS requires starts immediately; every tagged release produces a PyPI package, a multi-arch Docker image and a Zenodo version DOI, and the artifact passes a 30-minute smoke test on a laptop.

### 15.1 CI pipeline (GitHub Actions)

| Job | Trigger | Steps | Budget |
| --- | --- | --- | --- |
| `lint` | every push | ruff, mypy `--strict` on `core/` and `solve/`, import-linter (core must not import qiskit) | 1 min |
| `test` | every push | pytest layers 1–3 on Python 3.11, 3.12, 3.13 × Linux, macOS | 5 min |
| `oracle` | nightly | download pinned CSTNU Tool jar (checksum-verified), run layer 5 | 20 min |
| `diff` | nightly | layer 4 differential soundness, 100,000 hypothesis examples | 45 min |
| `bench-smoke` | PRs touching `solve/` | 10 benchmarks, compare check time to main (fail on > 25% regression) | 5 min |
| `release` | tag `v*` | build sdist/wheel → PyPI (trusted publishing), Docker image → GHCR (amd64 + arm64), Zenodo webhook | 15 min |

### 15.2 Artifact layout

```text
artifact/
├── Dockerfile          # python:3.12-slim + JDK 21 (for oracle) + pinned requirements.lock
├── vm/build.sh         # Ubuntu 24.04 VM recipe, for committees that prefer a VM (e.g. POPL)
├── smoke.sh            # < 30 min: install, 10 benchmarks, 1 counterexample replay
├── core.sh             # < 8 h: every table and figure in the paper from cached IBM data
├── full.sh             # everything, including 100k-example soundness run
└── README.md           # claims → commands → expected outputs mapping
```

The README maps each claim in the paper to the exact command and expected output, which is what artifact committees check first. Cached IBM results are shipped as data, so reviewers never need hardware access.

### 15.3 Versioning and documentation

- Semantic versioning. The contract schema has its own version (`qtiming-contract/0.1`) so contracts can evolve independently of the code.
- Docs site (mkdocs-material): quickstart, contract specification, annotation reference, "how to write a contract for your lab", and one tutorial per benchmark family.
- `CITATION.cff` with ORCID; Zenodo concept DOI in the README, version DOI cited in each paper.

### 15.4 Ecosystem integration

- **Qiskit ecosystem listing** once v0.2 works (submitted as a new project; membership does not carry over from qiskit-waveform-sim).
- **Transpiler passes** exposed as `qtiming.qiskit_pass.TimingCheck` (analysis pass, writes the verdict to the property set) and `EqualizeBranches` (transformation pass). A `generate_preset_pass_manager` plug-in stage lets users add them with one line.
- **CLI** for non-Python users and CI: `qtiming check prog.qasm --contract q1.toml --format sarif`.

## 16. Build sequence

The build order puts a working, useful tool first (EQ programs checked by Tier A by 20 December), then adds one policy or solver per step, so that a late slip removes features from the paper rather than the paper itself.

&#91;embedded content: build roadmap · 6 phases, 5 gates\]

Each phase ends in a gate that can be checked with a command, not a feeling: a passing benchmark run, a replayed counterexample, or a submitted PDF.

### 16.1 Effort estimate (at about 15 hours a week)

| Phase | Weeks | Hours (estimate) | Engineering share | Biggest single task |
| --- | --- | --- | --- | --- |
| 0 Skeleton | 1 | 20 | 40% | PLanQC abstract (not code) |
| 1 Tier A checker | 7 | 105 | 60% | Qiskit front end + LTEG builder |
| 2 Policies and solvers | 10 | 170 | 55% | own DC solver and its oracle tests |
| 3 Evaluation and artifact | 5 | 110 | 35% | evaluation runs and paper writing |
| 4 Hardening | 16 | 200 | 60% | windowed composition at scale |
| 5 Tool paper and standards | 20 | 220 | 50% | tool-paper benchmarking |

### 16.2 What to cut first if time runs short

1. QUA personality (keep three personalities).
2. Own Tier C2 work (rely on the CSTNU Tool bridge).
3. Summarised (non-unrolled) loops above 64 iterations.
4. The IBM probe's DD-on/off variant.

Never cut: the soundness differential test, counterexample replay, or the artifact smoke test.

## 17. Technical risks and decision log

The largest engineering risk is a subtle bug in the DC solver producing a false PROVED; it is mitigated by never trusting one solver alone. The other risks are about missing vendor data and state-space blow-up, and each has a fallback that keeps the paper alive.

### 17.1 Risks

| Risk | Likelihood | Impact | Mitigation | Fallback |
| --- | --- | --- | --- | --- |
| Own RUL⁻ DC implementation has a bug | high during development | false proofs | oracle cross-check, replay of every REFUTED, exhaustive ground truth on small programs | use CSTNU Tool as the C1 solver too; own solver becomes "fast path, verified by oracle" |
| Scenario blow-up (large k) | medium | UNKNOWN on QEC benchmarks | windowing at round boundaries; label-projection caching | report UNKNOWN honestly; split by annotation |
| CSTNU Tool timeouts or format changes | medium | gaps in C2 | pin version 7.2 with checksum; 60 s timeout | Z3 encoding of per-scenario DC for small k |
| Qiskit API churn (control flow, annotations) | medium | front end breaks | test against latest Qiskit nightly weekly; adapters isolated from core | pin a known-good Qiskit range for the artifact |
| Vendor latencies unpublished | certain | weak verdicts | provenance typing; parametric "max safe latency" | turn it into a finding ("what vendors must publish") |
| IBM join behaviour unknown | certain today | IBM personality is a guess | delay-sweep probe | documented fast-path padding, tagged `vendor` |
| Soundness proof of windowed composition fails | low–medium | technical contribution weakens | prove for the restricted case (full joins at cuts) first | disable windowing; restrict benchmarks |
| Part-time hours slip | medium–high | late artifact | build order puts a working Tier A tool first | submit with Tiers A, B, C1; C2 as future work |

### 17.2 Decision log

| Decision | Chosen | Rejected | Reason |
| --- | --- | --- | --- |
| Language | Python 3.11+ | Rust, OCaml | Qiskit ecosystem, reviewer accessibility; graphs are small enough |
| Time representation | integer `dt` | float ns | exactness; outward rounding is sound |
| Formal core | (C)STNU controllability | bespoke calculus, timed automata | mature algorithms and tools; pre-empts "just STNU" by making the reduction the contribution |
| CSTNU Tool integration | subprocess + GraphML | JPype linking | LGPL isolation, crash isolation, simpler packaging |
| Annotation carrier | Qiskit `BoxOp` annotations | new OpenQASM syntax | round-trips today without changing the language |
| Contract format | TOML + pydantic | YAML, extend Qiskit `Target` | human-editable, strict; `Target` has no latency fields yet |
| Loops | bounded `for`, capped `while` | unbounded `while` | keeps every verdict finite and honest |
| Mechanised proofs | stretch goal only | on critical path | time budget of a part-time solo researcher |

## Appendix: end-to-end worked example

This traces one small teleportation-style program through every stage, so each abstraction above has a concrete instance. The program is PROVED-UNDER on the IBM-like contract with a 2,400 ns deadline margin, and a one-line change makes it REFUTED with a replayable counterexample. Gate durations other than measurement and feedforward are illustrative.

### A.1 Input

The OpenQASM 3 program from Section 4.1, simplified to one correction: measure q1 into c1, then `if (c1) x q2`, inside a box annotated `@timing.policy eq` and `@timing.within 3000ns from c[1]`. Contract: `ibm_heron.toml` (dt = 4 ns; measure 1,660 ns; feedforward `ff` ∈ \[0, 600\] ns, `vendor`; x gate taken as 32 ns for illustration).

### A.2 Elaboration (EQ)

- Result valid interval relative to measurement start: \[1,660, 2,260\] ns = \[415, 565\] dt.
- Arms: then = `x q2` (8 dt), else = empty (0 dt), so d = 8 dt.
- Elaborated: `WaitUntil(565 dt); if (c1) { x q2 } else { delay[8 dt] q2 }`.
- Box duration: 565 + 8 = 573 dt (2,292 ns) from measurement start, identical for both outcomes.

### A.3 Event graph (excerpt)

| Time-point | Kind | Label | Constraint |
| --- | --- | --- | --- |
| tp1 | start M(q1) | ⊤ | origin + 0 |
| tp2 | end M(q1) | ⊤ | tp2 − tp1 = 415 |
| tp3 | valid c1 | ⊤, observes `c1@m2` | contingent tp2 → tp3 ∈ \[0, 150\] |
| tp4 | start X(q2) | c1 | tp4 − tp2 ≥ 150 (EQ wait) |
| tp5 | start delay(q2) | ¬c1 | tp5 − tp2 ≥ 150 |
| tp6 | end of box | ⊤ | tp6 − tp4 = 8; tp6 − tp5 = 8 |

### A.4 Obligations and dispatch

- **O2** (result ready): tp4 ≥ tp2 + hi = tp2 + 150. Holds by construction.
- **O3** (deadline): tp4 − tp3 ≤ 750 dt (3,000 ns). Worst case is the earliest valid time, θ = 0: tp4 − tp3 = 150 dt = 600 ns. Margin 2,400 ns.
- **O4** (idle): q2's gap before the arm is an EQ-inserted wait, so it is declared; holds.
- k = 0 timing-relevant propositions (both arms have equal length after EQ), so the dispatcher picks **Tier A**. Bellman–Ford finds no negative cycle.

### A.5 Verdict

PROVED-UNDER {ff ≤ 600 ns : vendor}. Z3's parametric query reports the program stays safe for any feedforward upper bound up to 3,000 ns, because the deadline is measured from the result's own arrival. EQ idle cost reported: up to 600 ns of padding per shot.

### A.6 The failing variant

Change the policy to EXP and tighten the deadline to 400 ns, then target the ARTIQ-like contract with an unpublished input-to-output latency tagged `vendor` at \[0, 600\] ns and no explicit `delay` before the correction.

- The dispatcher sees a reactive contingent link and picks **Tier C1**.
- DC propagation finds a negative cycle: the correction's output must commit before the result is known in the case θ = 600 ns.
- Counterexample: ω = {c1@m2: 1}, θ = {ff: 600 ns}, event = X(q2) at line 14, obligation O1 (underflow), late by the commit lead plus the shortfall.
- Replay in the ARTIQ-like executor raises `RTIOUnderflow` at the same event. The checker reports REFUTED, and the report suggests the fix: insert `delay` of at least the latency hi plus the commit lead, or switch to EQ.
