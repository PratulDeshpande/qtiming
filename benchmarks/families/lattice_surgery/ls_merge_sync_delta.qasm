OPENQASM 3.0;
// ls_merge_sync_delta: merge with an explicit sync(delta=100ns) policy
qubit[4] q;
bit[1] c;

h q[0];
h q[3];
cx q[0], q[2];
cx q[3], q[2];
c[0] = measure q[2];
@timing.policy sync(delta=100ns)
box {
    if (c[0]) {
    z q[0];
    z q[3];
    }
}
