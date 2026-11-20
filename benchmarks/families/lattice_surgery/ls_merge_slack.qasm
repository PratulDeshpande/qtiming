OPENQASM 3.0;
// ls_merge_slack: patch B is busy longer than patch A before the merge; a barrier restores the join (patch-sync slack)
qubit[4] q;
bit[1] c;

delay[400ns] q[3];
barrier q;
h q[0];
h q[3];
cx q[0], q[2];
cx q[3], q[2];
c[0] = measure q[2];
if (c[0]) {
    z q[0];
    z q[3];
}
