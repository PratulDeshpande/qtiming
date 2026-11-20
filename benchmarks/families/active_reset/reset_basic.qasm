OPENQASM 3.0;
// reset_basic: simplest conditional: measure, flip if 1
qubit[1] q;
bit[1] c;

c[0] = measure q[0];
if (c[0]) {
    x q[0];
}
