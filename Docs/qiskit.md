# Qiskit

The `qiskit` extra ([Install](install.md)) adds three transpiler passes and a scheduling-stage plug-in. Supported Qiskit versions are 2.3 to 2.6; the runs below used 2.6.2.

The checker reads a circuit through `qtiming.frontend.from_circuit` (also `from_qpy` for a `.qpy` file). Timing intent is written as annotations on a `box`:

    from qtiming.frontend.annotations import Policy, Within

    with qc.box(annotations=[Policy("eq"), Within("3000ns c[1]")]):
        with qc.if_test((qc.clbits[1], 1)):
            qc.x(2)

The available annotation classes are `Policy`, `Within`, `Cap`, `Hard`, `PMin`, `DeclaredIdle`, `Call` and `Cut`. `Within` also accepts `Within(3000, unit="ns", anchor="c[1]")`. The same payloads as in OpenQASM 3 apply; see [Policies](policies.md) for what each does. Annotations survive OpenQASM 3 and QPY round trips.

## The passes

| Pass | Kind | Does |
| --- | --- | --- |
| `TimingCheck(contract, *, policy=None, fail_on="refuted")` | analysis | Runs `check` on the circuit and stores the `Verdict` in `property_set["qtiming_verdict"]`. The circuit is not changed. |
| `EqualizeBranches(contract)` | transformation | Rewrites every `if` with the barrier, wait and arm padding that the `eq` policy inserts, as ordinary `barrier` and `delay` instructions. |
| `StripTimingAnnotations()` | transformation | Removes `timing.*` annotations at any depth and unwraps boxes that existed only to carry them. |

`contract` is a loaded `Contract`, a path to a TOML file, or the name of a shipped instance. `fail_on` is `"never"`, `"refuted"` or `"unknown"` (refuted or unknown); a failure raises `TranspilerError` naming the verdict.

## A run

This script was executed from the repository root:

    import os

    from qiskit import QuantumCircuit
    from qiskit.transpiler import PassManager
    from qiskit.transpiler.exceptions import TranspilerError
    from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager

    from qtiming.frontend.annotations import Policy, Within
    from qtiming.qiskit_pass import EqualizeBranches, StripTimingAnnotations, TimingCheck


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


    # 1. Check only: the verdict goes to the property set; the circuit is unchanged.
    pm = PassManager([TimingCheck("ibm_heron", fail_on="refuted")])
    pm.run(teleport("3000ns c[1]"))
    v = pm.property_set["qtiming_verdict"]
    print(v.verdict, v.weakest_class, [a.key for a in v.assumptions])

    # 2. A deadline the contract cannot meet raises TranspilerError.
    try:
        PassManager([TimingCheck("ibm_heron")]).run(teleport("300ns c[1]"))
    except TranspilerError as e:
        print("TranspilerError:", e)

    # 3. Equalise: the box now holds a barrier, a wait and a padded else arm.
    eq = PassManager([EqualizeBranches("ibm_heron")]).run(teleport("3000ns c[1]"))
    box = eq.data[-1]
    print(box.operation.name, [b.operation.name for b in box.operation.blocks[0].data])

    # 4. Strip the timing annotations before submission.
    plain = PassManager([StripTimingAnnotations()]).run(teleport("3000ns c[1]"))
    print([i.operation.name for i in plain.data])

    # 5. The scheduling plug-in: check, then strip.
    os.environ["QTIMING_CONTRACT"] = "ibm_heron"
    staged = generate_preset_pass_manager(optimization_level=0, scheduling_method="qtiming")
    out = staged.run(teleport("3000ns c[1]"))
    print(staged.property_set["qtiming_verdict"].verdict, [i.operation.name for i in out.data])

Output, exit code 0:

    PROVED-UNDER vendor ['ff.default']
    TranspilerError: 'qtiming: REFUTED under ibm_heron: O3 at node 7: first operation must start within the deadline after the result'
    box ['barrier', 'delay', 'if_else']
    ['h', 'cx', 'cx', 'h', 'measure', 'measure', 'if_else']
    PROVED-UNDER ['h', 'cx', 'cx', 'h', 'measure', 'measure', 'if_else']

In step 3 the `if_else` inside the box has a second arm with a `delay` of 8 dt (the duration of `x`), and a `delay` of 150 dt (600 ns) precedes the branch. After `EqualizeBranches` the result of the circuit is the same program with the padding spelled out, and re-checking it passes.

## The scheduling plug-in

`qtiming` is registered as a pass-manager stage plug-in for the `scheduling` stage (entry point group `qiskit.transpiler.scheduling`, written as `scheduling_method="qtiming"`). It runs `TimingCheck(contract, fail_on="refuted")` and then `StripTimingAnnotations()`. The contract comes from the environment variable `QTIMING_CONTRACT`, a path or an instance name; if it is unset the plug-in raises `ValueError`. Selecting the plug-in replaces Qiskit's own scheduling stage for that pass manager: nothing else is scheduled.

## What is and is not supported

- The passes check the circuit as written. `TimingCheck` takes a policy but not `--assume` values; to use an assumed number, build the contract with `qtiming.contract.loader.load_contract(path, assume=(...))` and pass the `Contract` object.
- Gate durations must be in the contract. For `ibm_heron` they come from the shipped snapshot, which is unofficial. For the other contracts you supply them, as with `--assume durations.x=...`. A gate with no duration raises `E-CT-MISSING`; an instruction that is not a gate or a supported operation raises `E-FE-UNKNOWN-OP`.
- `EqualizeBranches` refuses a circuit whose elaboration changes the number of branches, which includes loops (`TranspilerError`). It also refuses to pad onto a qubit the `if` does not touch: add the qubit to the branch first.
- `EqualizeBranches` applies `eq` to every branch regardless of annotations.
- `box` durations are not implemented (`E-FE-UNSUPPORTED`).
- IBM hardware does not take timing boxes. The lint warning `E-LINT-IBM-BOX` reminds you to strip them; the plug-in and `StripTimingAnnotations` do that.
- The passes do not insert dynamical decoupling, do not reorder gates and do not submit jobs.
- Nothing here has been run against real IBM hardware.
