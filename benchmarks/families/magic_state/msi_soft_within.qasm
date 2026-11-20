OPENQASM 3.0;
// msi_soft_within: same fix-up with a soft (non-hard) deadline of 3000 ns
qubit[2] q;
bit[1] c;

h q[0];
cx q[0], q[1];
c[0] = measure q[1];
@timing.within 3000ns c[0]
box {
    if (c[0]) {
        sx q[0];
    }
}
