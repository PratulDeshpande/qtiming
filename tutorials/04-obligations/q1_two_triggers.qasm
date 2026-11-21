OPENQASM 3.0;
// q1_two_triggers: written for this tutorial. Two measure-and-correct steps back to back on Q1,
// the second deadline-annotated, so the trigger network is used twice.
qubit[2] q;
bit[2] c;

c[0] = measure q[0];
@timing.policy eq
box {
    if (c[0]) {
        x q[0];
    } else {
        delay[32ns] q[0];
    }
}
c[1] = measure q[1];
@timing.policy eq
@timing.within 500ns c[1]
box {
    if (c[1]) {
        x q[1];
    } else {
        delay[32ns] q[1];
    }
}
