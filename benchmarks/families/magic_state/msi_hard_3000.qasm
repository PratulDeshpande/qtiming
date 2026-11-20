OPENQASM 3.0;
// msi_hard_3000: injection with a conditional S-like fix-up inside a hard 3000 ns reaction deadline
qubit[2] q;
bit[1] c;

h q[0];
cx q[0], q[1];
c[0] = measure q[1];
@timing.within 3000ns c[0]
@timing.hard
box {
    if (c[0]) {
        sx q[0];
    }
}
