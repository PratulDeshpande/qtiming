OPENQASM 3.0;
// msi_two_stage: two-stage injection: S fix-up then a Z fix-up from a second result, both under hard deadlines
qubit[3] q;
bit[2] c;

h q[0];
cx q[0], q[1];
cx q[0], q[2];
c[0] = measure q[1];
c[1] = measure q[2];
@timing.within 3000ns c[0]
@timing.hard
box {
    if (c[0]) {
        sx q[0];
    }
}
@timing.within 3000ns c[1]
@timing.hard
box {
    if (c[1]) {
        z q[0];
    }
}
