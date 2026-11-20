OPENQASM 3.0;
// tp_gate_parity: gate teleportation with a parity-controlled correction (c[0] xor c[1]) inside a within box
qubit[3] q;
bit[2] c;

h q[1];
cx q[1], q[2];
cx q[0], q[1];
h q[0];
c[0] = measure q[0];
c[1] = measure q[1];
@timing.within 3000ns c[1]
box {
    if (c[0] ^ c[1]) {
        z q[2];
    }
}
