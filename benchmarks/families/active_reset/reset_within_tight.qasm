OPENQASM 3.0;
// reset_within_tight: reset with a 300 ns deadline: tighter than the vendor 600 ns feedforward claim
qubit[1] q;
bit[1] c;

c[0] = measure q[0];
@timing.within 300ns c[0]
box {
    if (c[0]) {
        x q[0];
    }
}
