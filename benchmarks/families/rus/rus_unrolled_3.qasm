OPENQASM 3.0;
// rus_unrolled_3: IBM-expressible approximation: 3 fixed attempts as a `for` loop with a conditional retry (no `while`)
qubit[2] q;
bit[1] c;

for int i in [0:2] {
barrier q;
c[0] = measure q[0];
if (c[0]) {
    x q[1];
    h q[0];
}
barrier q;
}
