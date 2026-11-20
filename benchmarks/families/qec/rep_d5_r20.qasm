OPENQASM 3.0;
// rep_d5_r20: distance-5 repetition code, 20 syndrome round(s), toy lookup decoder
qubit[9] q;
bit[4] c;

for int i in [0:19] {
barrier q;
cx q[0], q[5];
cx q[1], q[5];
cx q[1], q[6];
cx q[2], q[6];
cx q[2], q[7];
cx q[3], q[7];
cx q[3], q[8];
cx q[4], q[8];
c[0] = measure q[5];
c[1] = measure q[6];
c[2] = measure q[7];
c[3] = measure q[8];
if (c[0] && !c[1]) {
    x q[0];
}
if (c[0] && c[1]) {
    x q[1];
}
if (c[1] && c[2]) {
    x q[2];
}
if (c[2] && c[3]) {
    x q[3];
}
if (!c[2] && c[3]) {
    x q[4];
}
reset q[5];
reset q[6];
reset q[7];
reset q[8];
barrier q;
}
