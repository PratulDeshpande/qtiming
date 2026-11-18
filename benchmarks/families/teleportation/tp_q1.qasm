OPENQASM 3.0;
// Teleportation for a predicated backend (Q1): the two arms hold one RT instruction of the same
// duration, so the EQ policy is satisfiable (equal counts and durations; see plan 8.5).
qubit[3] q;
bit[2] c;

h q[1];
cx q[1], q[2];
cx q[0], q[1];
h q[0];
c[0] = measure q[0];
c[1] = measure q[1];
delay[400ns] q[2];

@timing.policy eq
box {
    if (c[1]) {
        x q[2];
    } else {
        delay[32ns] q[2];
    }
}
