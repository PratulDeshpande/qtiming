"""Pin the non-Python files that must ship in the wheel (no build is run here: too slow)."""

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "src" / "qtiming"
REQUIRED = [
    "py.typed",
    "contract/instances/artiq.toml",
    "contract/instances/ibm_heron.toml",
    "contract/instances/ibm_heron_snapshot.json",
    "contract/instances/q1.toml",
    "contract/instances/qua.toml",
]


def test_required_data_files_exist() -> None:
    missing = [f for f in REQUIRED if not (PKG / f).is_file()]
    assert not missing, missing


def test_hatch_includes_them() -> None:
    cfg = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    wheel = cfg["tool"]["hatch"]["build"]["targets"]["wheel"]
    assert wheel["packages"] == ["src/qtiming"]
    inc = set(wheel["include"])
    assert {"src/qtiming/py.typed", "src/qtiming/contract/instances/*.toml",
            "src/qtiming/contract/instances/*.json"} <= inc


def test_entry_points_unchanged() -> None:
    cfg = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert cfg["project"]["scripts"]["qtiming"] == "qtiming.cli.main:main"
