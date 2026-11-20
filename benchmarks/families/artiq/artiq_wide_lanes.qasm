OPENQASM 3.0;
// artiq_wide_lanes: ten channels pulsed together, then one measured and fed back (more events than the 8 SED lanes)
// synthetic ARTIQ-style kernel written by the qtiming authors, NOT external code (not from the ARTIQ project); exposed-timeline (EXP) form
qubit[10] q;
bit[2] c;

x q[0];
x q[1];
x q[2];
x q[3];
x q[4];
x q[5];
x q[6];
x q[7];
x q[8];
x q[9];
c[0] = measure q[0];
delay[800ns] q[1];
@timing.policy exp
box {
    if (c[0]) {
        x q[1];
    }
}
