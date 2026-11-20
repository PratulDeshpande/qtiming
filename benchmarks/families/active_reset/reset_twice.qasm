OPENQASM 3.0;
// reset_twice: two rounds of active reset on one qubit (the second result reads a fresh bit)
qubit[1] q;
bit[2] c;

c[0] = measure q[0];
if (c[0]) {
    x q[0];
}
c[1] = measure q[0];
if (c[1]) {
    x q[0];
}
