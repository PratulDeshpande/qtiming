import pytest

from qtiming.contract.compat import CLASSES, POLICIES, compat

# (policy, class) -> kind. One test per cell (Section 7.6).
EXPECTED = {
    ("eq", "predicated"): "native_if_matched",
    ("eq", "equalized"): "native",
    ("eq", "resync"): "pad",
    ("eq", "exposed"): "delays",
    ("eq", "restricted"): "pad",
    ("sync", "predicated"): "reject",
    ("sync", "equalized"): "reject",
    ("sync", "resync"): "native",
    ("sync", "exposed"): "delays",
    ("sync", "restricted"): "native",
    ("exp", "predicated"): "reject",
    ("exp", "equalized"): "reject",
    ("exp", "resync"): "reject",
    ("exp", "exposed"): "native",
    ("exp", "restricted"): "reject",
}


@pytest.mark.parametrize(("policy", "klass"), sorted(EXPECTED))
def test_cell(policy: str, klass: str) -> None:
    r = compat(policy, klass)
    assert r.kind == EXPECTED[(policy, klass)]
    assert r.note
    assert r.accepted == (r.kind != "reject")


def test_table_is_exhaustive() -> None:
    assert {(p, c) for p in POLICIES for c in CLASSES} == set(EXPECTED)


def test_unknown_inputs_raise() -> None:
    with pytest.raises(KeyError):
        compat("bogus", "exposed")
