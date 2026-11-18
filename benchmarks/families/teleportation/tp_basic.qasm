OPENQASM 3.0;
// Teleportation with one classical correction (plan Appendix A.1).
// Policy EQ with a 3000 ns deadline from the arrival of the measurement result.
qubit[3] q;
bit[2] c;

h q[1];
cx q[1], q[2];
cx q[0], q[1];
h q[0];
c[0] = measure q[0];
c[1] = measure q[1];

@timing.policy eq
@timing.within 3000ns c[1]
box {
    if (c[1]) {
        x q[2];
    }
}
