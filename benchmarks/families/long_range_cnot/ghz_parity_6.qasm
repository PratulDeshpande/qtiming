OPENQASM 3.0;
// ghz_parity_6: 6-qubit GHZ built with CNOTs, odd qubits measured, one wide parity conditional
qubit[6] q;
bit[3] c;

h q[0];
cx q[0], q[1];
cx q[0], q[2];
cx q[0], q[3];
cx q[0], q[4];
cx q[0], q[5];
c[0] = measure q[1];
c[1] = measure q[3];
c[2] = measure q[5];
if (c[0] ^ c[1] ^ c[2]) {
    z q[0];
}
