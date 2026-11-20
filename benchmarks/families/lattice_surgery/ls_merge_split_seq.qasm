OPENQASM 3.0;
// ls_merge_split_seq: merge, then split, in sequence under one policy
qubit[4] q;
bit[2] c;

h q[0];
h q[3];
cx q[0], q[2];
cx q[3], q[2];
c[0] = measure q[2];
if (c[0]) {
    z q[0];
    z q[3];
}
barrier q;
c[1] = measure q[0];
if (c[1]) {
    x q[3];
}
