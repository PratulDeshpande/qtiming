OPENQASM 3.0;
// reset_parallel: two qubits reset in parallel from independent results
qubit[2] q;
bit[2] c;

c[0] = measure q[0];
c[1] = measure q[1];
if (c[0]) {
    x q[0];
}
if (c[1]) {
    x q[1];
}
