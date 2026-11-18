import pytest

pytest.importorskip("openqasm3")

from qtiming.core.ast import Box, For, Measure  # noqa: E402
from qtiming.core.errors import QtError  # noqa: E402
from qtiming.frontend import from_qasm3  # noqa: E402
from qtiming.frontend.qasm3_fe import TIMING_KINDS  # noqa: E402

HEAD = "OPENQASM 3.0;\nqubit[2] q;\nbit[2] c;\n"


def code(text: str) -> str:
    with pytest.raises(QtError) as ei:
        from_qasm3(HEAD + text)
    return ei.value.code


def test_kinds_match_the_qiskit_annotation_classes() -> None:
    pytest.importorskip("qiskit")
    from qtiming.frontend.annotations import CLASSES

    assert set(CLASSES) == TIMING_KINDS


@pytest.mark.parametrize("rng, n", [("[0:3]", 4), ("[0:2:6]", 4), ("[3:-1:0]", 4),
                                    ("{1, 5, 9}", 3)])
def test_for_ranges_are_inclusive(rng: str, n: int) -> None:
    p = from_qasm3(HEAD + f"for int i in {rng} {{ }}\n")
    (loop,) = p.body.stmts
    assert isinstance(loop, For) and loop.n == n


def test_source_locations_and_other_namespaces() -> None:
    p = from_qasm3(HEAD + "c[0] = measure q[0];\n@other.thing x\n@timing.hard\nbox { }\n",
                   filename="f.qasm")
    m, box = p.body.stmts
    assert isinstance(m, Measure) and (m.loc.file, m.loc.line) == ("f.qasm", 4)
    assert isinstance(box, Box) and box.annotations == (("hard", ""),)


@pytest.mark.parametrize("text, want", [
    ("h q[0]\n", "E-FE-PARSE"),
    ("h q;\n", "E-FE-UNSUPPORTED"),  # register broadcast
    ("ctrl @ x q[0], q[1];\n", "E-FE-UNSUPPORTED"),
    ("int[8] n = 3;\n", "E-FE-UNSUPPORTED"),
    ("x $0;\n", "E-FE-UNSUPPORTED"),
    ("x q[5];\n", "E-FE-INDEX"),
    ("if (c[0]) { x q[0]; }\n", "E-FE-BIT-UNWRITTEN"),
    ("c[0] = measure q[0];\nif (c[0] / 2) { }\n", "E-FE-EXPR-UNSUPPORTED"),
    ("c[0] = measure q[0];\nwhile (c[0]) { }\n", "E-FE-UNBOUNDED-WHILE"),
    ("@timing.policy eq\nx q[0];\n", "E-FE-ANNOT-PLACEMENT"),
    ("@timing.policy eq\ndelay[4dt] q[0];\n", "E-FE-ANNOT-PLACEMENT"),
    ("@timing.bogus 1\nbox { }\n", "E-FE-ANNOT-PAYLOAD"),
    ("@timing.within 10ns d[0]\nbox { }\n", "E-FE-ANNOT-BIT"),
    ("box[100ns] { }\n", "E-FE-UNSUPPORTED"),
    ("delay[40ns] q[0];\n", "E-FE-NO-DT"),  # no contract, so no dt
])
def test_refusals(text: str, want: str) -> None:
    assert code(text) == want
