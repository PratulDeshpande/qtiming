OPENQASM 3.0;
// lrcnot_h1: long-range CNOT over 1 Bell-pair hop(s): parity corrections over 2 bits
qubit[4] q;
bit[2] c;

h q[1];
cx q[1], q[2];
cx q[0], q[1];
cx q[2], q[3];
c[0] = measure q[1];
c[1] = measure q[2];
if (c[0]) {
    x q[3];
}
if (c[1]) {
    z q[0];
}
