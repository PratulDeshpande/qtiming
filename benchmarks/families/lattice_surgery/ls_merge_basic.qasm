OPENQASM 3.0;
// ls_merge_basic: merge two patches by a joint-parity measurement; correct both patches on the outcome
qubit[4] q;
bit[1] c;

h q[0];
h q[3];
cx q[0], q[2];
cx q[3], q[2];
c[0] = measure q[2];
if (c[0]) {
    z q[0];
    z q[3];
}
