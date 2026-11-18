OPENQASM 3.0;
// Teleportation with one correction under the SYNC policy: no padding, the arm starts as soon
// as the result arrives. Expected to be REFUTED where idle gaps must not vary (O4).
qubit[3] q;
bit[2] c;

h q[1];
cx q[1], q[2];
cx q[0], q[1];
h q[0];
c[0] = measure q[0];
c[1] = measure q[1];

@timing.policy sync
box {
    if (c[1]) {
        x q[2];
    }
}
