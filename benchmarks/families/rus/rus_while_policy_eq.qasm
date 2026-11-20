OPENQASM 3.0;
// rus_while_policy_eq: RUS loop with an explicit EQ policy on the loop
qubit[2] q;
bit[1] c;

c[0] = measure q[0];
@timing.cap 4
@timing.policy eq
box {
    while (c[0]) {
        x q[1];
        h q[0];
        c[0] = measure q[0];
    }
}
