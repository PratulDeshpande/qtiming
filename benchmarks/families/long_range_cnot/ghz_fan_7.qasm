OPENQASM 3.0;
// ghz_fan_7: 7-qubit GHZ built with CNOTs, odd qubits measured, many parallel conditionals
qubit[7] q;
bit[3] c;

h q[0];
cx q[0], q[1];
cx q[0], q[2];
cx q[0], q[3];
cx q[0], q[4];
cx q[0], q[5];
cx q[0], q[6];
c[0] = measure q[1];
c[1] = measure q[3];
c[2] = measure q[5];
if (c[0]) {
    z q[2];
}
if (c[1]) {
    z q[4];
}
if (c[2]) {
    z q[6];
}
