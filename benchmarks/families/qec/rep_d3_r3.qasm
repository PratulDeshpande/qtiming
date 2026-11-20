OPENQASM 3.0;
// rep_d3_r3: distance-3 repetition code, 3 syndrome round(s), toy lookup decoder
qubit[5] q;
bit[2] c;

for int i in [0:2] {
barrier q;
cx q[0], q[3];
cx q[1], q[3];
cx q[1], q[4];
cx q[2], q[4];
c[0] = measure q[3];
c[1] = measure q[4];
if (c[0] && !c[1]) {
    x q[0];
}
if (c[0] && c[1]) {
    x q[1];
}
if (!c[0] && c[1]) {
    x q[2];
}
reset q[3];
reset q[4];
barrier q;
}
