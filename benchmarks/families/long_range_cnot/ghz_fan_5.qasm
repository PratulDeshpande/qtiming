OPENQASM 3.0;
// ghz_fan_5: 5-qubit GHZ built with CNOTs, odd qubits measured, many parallel conditionals
qubit[5] q;
bit[2] c;

h q[0];
cx q[0], q[1];
cx q[0], q[2];
cx q[0], q[3];
cx q[0], q[4];
c[0] = measure q[1];
c[1] = measure q[3];
if (c[0]) {
    z q[2];
}
if (c[1]) {
    z q[4];
}
