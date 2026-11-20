OPENQASM 3.0;
// msi_hard_1000: same, with a 1000 ns hard deadline (above the 600 ns vendor claim)
qubit[2] q;
bit[1] c;

h q[0];
cx q[0], q[1];
c[0] = measure q[1];
@timing.within 1000ns c[0]
@timing.hard
box {
    if (c[0]) {
        sx q[0];
    }
}
