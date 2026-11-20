OPENQASM 3.0;
// msi_eq_hard: injection under an explicit EQ policy and a hard deadline
qubit[2] q;
bit[1] c;

h q[0];
cx q[0], q[1];
c[0] = measure q[1];
@timing.policy eq
@timing.within 3000ns c[0]
@timing.hard
box {
    if (c[0]) {
        sx q[0];
    }
}
