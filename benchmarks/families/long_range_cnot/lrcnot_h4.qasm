OPENQASM 3.0;
// lrcnot_h4: long-range CNOT over 4 Bell-pair hop(s): parity corrections over 8 bits
qubit[10] q;
bit[8] c;

h q[1];
cx q[1], q[2];
h q[3];
cx q[3], q[4];
h q[5];
cx q[5], q[6];
h q[7];
cx q[7], q[8];
cx q[0], q[1];
cx q[2], q[3];
cx q[4], q[5];
cx q[6], q[7];
cx q[8], q[9];
c[0] = measure q[1];
c[1] = measure q[2];
c[2] = measure q[3];
c[3] = measure q[4];
c[4] = measure q[5];
c[5] = measure q[6];
c[6] = measure q[7];
c[7] = measure q[8];
if (c[0] ^ c[2] ^ c[4] ^ c[6]) {
    x q[9];
}
if (c[1] ^ c[3] ^ c[5] ^ c[7]) {
    z q[0];
}
