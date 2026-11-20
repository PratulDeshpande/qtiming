OPENQASM 3.0;
// artiq_two_ions: two channels measured and corrected independently with explicit slack
// synthetic ARTIQ-style kernel written by the qtiming authors, NOT external code (not from the ARTIQ project); exposed-timeline (EXP) form
qubit[2] q;
bit[2] c;

c[0] = measure q[0];
c[1] = measure q[1];
delay[800ns] q[0];
delay[800ns] q[1];
@timing.policy exp
box {
    if (c[0]) {
        x q[0];
    }
    if (c[1]) {
        x q[1];
    }
}
