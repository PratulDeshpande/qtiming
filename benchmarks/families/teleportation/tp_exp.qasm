OPENQASM 3.0;
// Teleportation for an exposed-timeline backend (ARTIQ): the programmer owns the cursor, so the
// slack after reading the result is restored with explicit delays (plan A.7).
qubit[3] q;
bit[2] c;

delay[2000ns] q[0];
h q[1];
cx q[1], q[2];
cx q[0], q[1];
h q[0];
c[0] = measure q[0];
c[1] = measure q[1];
delay[800ns] q[2];

@timing.policy exp
box {
    if (c[1]) {
        x q[2];
    }
}
