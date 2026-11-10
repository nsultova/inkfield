import numpy as np
import pytest

from inkfield.core.frame import Frame
from inkfield.core.rng import make_rng


def test_circle_contains_and_scale():
    f = Frame("circle", 100, 100, 50, 50)
    assert f.scale == 50 and f.bbox == (50, 50, 150, 150)
    assert f.contains(np.array([100, 150, 151]), np.array([100, 100, 100])).tolist() == [True, True, False]


def test_rect_contains_and_inset():
    f = Frame("rect", 105, 148.5, 89, 132.5).inset(3)
    assert (f.half_w, f.half_h) == (86, 129.5)
    assert f.contains(np.array([19.0, 18.9]), np.array([148.5, 148.5])).tolist() == [True, False]


@pytest.mark.parametrize("shape", ["circle", "rect"])
def test_sample_is_inside_and_seeded(shape):
    f = Frame(shape, 100, 100, 40, 60 if shape == "rect" else 40)
    a = f.sample(make_rng(3), 200); b = f.sample(make_rng(3), 200)
    assert a.shape == (200, 2) and np.array_equal(a, b) and f.contains(a[:, 0], a[:, 1]).all()


def test_outline_is_closed_and_on_edge():
    o = Frame("circle", 0, 0, 10, 10).outline()
    assert np.allclose(o[0], o[-1]) and np.allclose(np.hypot(o[:, 0], o[:, 1]), 10)
    assert np.hypot(*np.diff(o, axis=0).T).max() <= 0.3
