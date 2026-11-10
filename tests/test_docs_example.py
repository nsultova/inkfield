"""The example piece in docs/adding-a-piece.md must really work, exactly as printed."""
import re
from pathlib import Path

from inkfield.core.piece import discover
from inkfield.render import render


def test_documented_example_piece_runs(tmp_path, monkeypatch):
    text = Path("docs/adding-a-piece.md").read_text()
    code = re.search(r"```python\n(\"\"\".*?)```", text, re.S).group(1)     # the first block that starts with a docstring
    pkg = tmp_path / "docpieces"; pkg.mkdir(); (pkg / "__init__.py").write_text(""); (pkg / "rings.py").write_text(code)
    monkeypatch.syspath_prepend(str(tmp_path))
    pieces = discover("docpieces"); slug = next(iter(pieces))
    r = render(pieces, slug, seed=1); assert r.stats["strokes"] >= 3
