OPENQASM 3.0;
// rus_while_cap16: repeat-until-success loop, capped at 16 attempts
qubit[2] q;
bit[1] c;

c[0] = measure q[0];
@timing.cap 16
box {
    while (c[0]) {
        x q[1];
        h q[0];
        c[0] = measure q[0];
    }
}
