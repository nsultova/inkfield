from inkfield.core.piece import discover

FAKE_PIECE_SOURCE = '''
import numpy as np

from inkfield.core.controls import Slider
from inkfield.core.piece import Meta
from inkfield.core.stroke import Stroke

META = Meta(slug="dots", title="Dots", subtitle="A test piece", framed_shape="circle",
            info="One short line.")
PARAMS = [Slider("count", "Count", 1, 10, 1, 3)]


def generate(params, frame, rng):
    return [Stroke(np.array([[0.0, 0.0], [1.0, 1.0]]))]
'''


def test_discovers_a_dropped_in_file(tmp_path, monkeypatch):
    pkg = tmp_path / "fakepieces"; pkg.mkdir(); (pkg / "__init__.py").write_text("")
    (pkg / "dots.py").write_text(FAKE_PIECE_SOURCE)      # META slug "dots", one Slider, generate returns one Stroke
    (pkg / "_hidden.py").write_text("raise RuntimeError")
    monkeypatch.syspath_prepend(str(tmp_path))
    pieces = discover("fakepieces")
    assert list(pieces) == ["dots"] and pieces["dots"].meta.title == "Dots"
