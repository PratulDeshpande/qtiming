OPENQASM 3.0;
// surf_d3_r1: distance-3 surface-code patch (Z checks only), 1 round(s), toy corrections
qubit[13] q;
bit[4] c;

cx q[0], q[9];
cx q[1], q[9];
cx q[3], q[9];
cx q[4], q[9];
cx q[1], q[10];
cx q[2], q[10];
cx q[4], q[11];
cx q[5], q[11];
cx q[7], q[11];
cx q[8], q[11];
cx q[6], q[12];
cx q[7], q[12];
c[0] = measure q[9];
c[1] = measure q[10];
c[2] = measure q[11];
c[3] = measure q[12];
if (c[0]) {
    x q[4];
}
if (c[1] ^ c[2]) {
    x q[5];
}
if (c[3]) {
    x q[7];
}
reset q[9];
reset q[10];
reset q[11];
reset q[12];
