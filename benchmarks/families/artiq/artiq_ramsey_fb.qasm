OPENQASM 3.0;
// artiq_ramsey_fb: Ramsey sequence with a feedback correction after a free-evolution delay
// synthetic ARTIQ-style kernel written by the qtiming authors, NOT external code (not from the ARTIQ project); exposed-timeline (EXP) form
qubit[1] q;
bit[1] c;

h q[0];
delay[2000ns] q[0];
h q[0];
c[0] = measure q[0];
delay[800ns] q[0];
@timing.policy exp
box {
    if (c[0]) {
        x q[0];
    }
}
