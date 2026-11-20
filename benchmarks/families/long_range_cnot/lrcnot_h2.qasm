OPENQASM 3.0;
// lrcnot_h2: long-range CNOT over 2 Bell-pair hop(s): parity corrections over 4 bits
qubit[6] q;
bit[4] c;

h q[1];
cx q[1], q[2];
h q[3];
cx q[3], q[4];
cx q[0], q[1];
cx q[2], q[3];
cx q[4], q[5];
c[0] = measure q[1];
c[1] = measure q[2];
c[2] = measure q[3];
c[3] = measure q[4];
if (c[0] ^ c[2]) {
    x q[5];
}
if (c[1] ^ c[3]) {
    z q[0];
}
