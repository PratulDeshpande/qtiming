OPENQASM 3.0;
// ghz_parity_4: 4-qubit GHZ built with CNOTs, odd qubits measured, one wide parity conditional
qubit[4] q;
bit[2] c;

h q[0];
cx q[0], q[1];
cx q[0], q[2];
cx q[0], q[3];
c[0] = measure q[1];
c[1] = measure q[3];
if (c[0] ^ c[1]) {
    z q[0];
}
