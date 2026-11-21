"""Turn a percent-format script (`# %%`, `# %% [markdown]`) into an .ipynb: `python _nb.py src.py out.ipynb`."""
import sys
from pathlib import Path

import nbformat as nbf


def convert(src: Path, out: Path) -> None:
    cells, kind, buf = [], None, []

    def flush() -> None:
        if kind is None:
            return
        text = "\n".join(buf).strip("\n")
        if kind == "md":
            text = "\n".join(ln[2:] if ln.startswith("# ") else ln.lstrip("#") for ln in text.splitlines())
            cells.append(nbf.v4.new_markdown_cell(text))
        elif text:
            cells.append(nbf.v4.new_code_cell(text))

    for line in src.read_text(encoding="utf-8").splitlines():
        if line.startswith("# %%"):
            flush()
            kind, buf = ("md" if "[markdown]" in line else "code"), []
        else:
            buf.append(line)
    flush()
    nb = nbf.v4.new_notebook(cells=cells)
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    nbf.write(nb, out)


if __name__ == "__main__":
    convert(Path(sys.argv[1]), Path(sys.argv[2]))
