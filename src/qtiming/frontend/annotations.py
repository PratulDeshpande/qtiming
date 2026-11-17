"""`timing.*` Qiskit annotations (requires qiskit). One namespace per kind: `timing.<kind>`.

With one namespace per kind, Qiskit renders `@timing.policy eq`, exactly the documented text
form, and a single handler registered under the prefix "timing" serves them all.
"""

from __future__ import annotations

from collections.abc import Iterable

from qiskit.circuit.annotation import Annotation


class TimingAnnotation(Annotation):  # type: ignore[misc]
    kind: str = ""

    def __init__(self, payload: str = "") -> None:
        self.payload = payload

    @property
    def namespace(self) -> str:
        return f"timing.{self.kind}"

    def __eq__(self, other: object) -> bool:
        return (
            type(self) is type(other) and self.payload == other.payload  # type: ignore[attr-defined]
        )

    def __hash__(self) -> int:
        return hash((self.kind, self.payload))

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.payload!r})"


class Policy(TimingAnnotation):
    kind = "policy"


class Within(TimingAnnotation):
    kind = "within"

    def __init__(
        self, duration: str | int | float = "", unit: str = "ns", anchor: str | None = None
    ) -> None:
        # Within(3000, unit="ns", anchor="c[1]") is shorthand for Within("3000ns c[1]")
        super().__init__(str(duration) if anchor is None else f"{duration}{unit} {anchor}")


class Cap(TimingAnnotation):
    kind = "cap"


class PMin(TimingAnnotation):
    kind = "pmin"


class DeclaredIdle(TimingAnnotation):
    kind = "declared_idle"


class Call(TimingAnnotation):
    kind = "call"


class Hard(TimingAnnotation):
    kind = "hard"


class Cut(TimingAnnotation):
    kind = "cut"


CLASSES: dict[str, type[TimingAnnotation]] = {
    c.kind: c for c in (Policy, Within, Cap, PMin, DeclaredIdle, Call, Hard, Cut)
}


def timing_annotations(annotations: Iterable[Annotation]) -> tuple[tuple[str, str], ...]:
    """The (kind, payload) pairs of our namespace, in the order given; others are ignored."""
    return tuple((a.kind, a.payload) for a in annotations if isinstance(a, TimingAnnotation))
