OPENQASM 3.0;
// rus_while_cap8: repeat-until-success loop, capped at 8 attempts
qubit[2] q;
bit[1] c;

c[0] = measure q[0];
@timing.cap 8
box {
    while (c[0]) {
        x q[1];
        h q[0];
        c[0] = measure q[0];
    }
}
