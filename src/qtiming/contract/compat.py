"""Policy-compatibility relation (Section 7.6): program policy x backend branch class."""

from __future__ import annotations

from dataclasses import dataclass

POLICIES = ("eq", "sync", "exp")
CLASSES = ("predicated", "equalized", "resync", "exposed", "restricted")


@dataclass(frozen=True, slots=True)
class Compat:
    kind: str  # native | native_if_matched | pad | delays | reject
    note: str

    @property
    def accepted(self) -> bool:
        return self.kind != "reject"


_T: dict[tuple[str, str], Compat] = {
    ("eq", "predicated"): Compat(
        "native_if_matched",
        "native only when arms match per RT instruction (set_cond waits else_time per skipped "
        "instruction); otherwise EqualizeBranches rewrites arms to equal count and durations"),
    ("eq", "equalized"): Compat("native", "backend equalises arms natively"),
    ("eq", "resync"): Compat(
        "pad", "via padding pass: delay before the branch up to hi, arms padded"),
    ("eq", "exposed"): Compat("delays", "via explicit delays written by the programmer"),
    ("eq", "restricted"): Compat(
        "pad", "via padding pass; only for a single, non-nested if/else"),
    ("sync", "predicated"): Compat(
        "reject", "cannot express a join gap bound; the RT core never resynchronises"),
    ("sync", "equalized"): Compat("reject", "cannot express a join gap bound"),
    ("sync", "resync"): Compat("native", "backend resynchronises at the join"),
    ("sync", "exposed"): Compat("delays", "via explicit resync delay"),
    ("sync", "restricted"): Compat(
        "native", "native for a single if_test; join behaviour is a calibrated parameter"),
    ("exp", "predicated"): Compat("reject", "no exposed timeline on a predicated backend"),
    ("exp", "equalized"): Compat("reject", "no exposed timeline on an equalized backend"),
    ("exp", "resync"): Compat(
        "reject", "implicit aligns remove the exposed cursor"),
    ("exp", "exposed"): Compat("native", "the programmer owns the cursor"),
    ("exp", "restricted"): Compat("reject", "restricted backend has no exposed timeline"),
}


def compat(policy: str, klass: str) -> Compat:
    return _T[(policy, klass)]
