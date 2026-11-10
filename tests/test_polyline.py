import numpy as np

from inkfield.core.polyline import densify, keep_where, length, simplify


def test_length():   assert length(np.array([[0, 0], [3, 4], [3, 10]])) == 11
def test_densify():  d = densify(np.array([[0., 0], [10, 0]]), 1.0); assert len(d) == 11 and np.allclose(d[:, 0], np.arange(11))


def test_keep_where_cuts_on_the_boundary():
    line = np.array([[-20., 0], [20, 0]])
    parts = keep_where(densify(line, 1.0), lambda x, y: np.hypot(x, y) <= 10)
    assert len(parts) == 1
    assert abs(parts[0][0, 0] + 10) <= 0.01 and abs(parts[0][-1, 0] - 10) <= 0.01


def test_keep_where_splits_into_several_parts():
    zig = np.array([[0., 0], [0, 5], [0, 15], [0, 25]])
    parts = keep_where(zig, lambda x, y: (y <= 8) | (y >= 20))
    assert len(parts) == 2 and abs(parts[0][-1, 1] - 8) <= 0.01 and abs(parts[1][0, 1] - 20) <= 0.01


def test_keep_where_all_inside_returns_input_unchanged():
    p = np.array([[0., 0], [1, 1]]); out = keep_where(p, lambda x, y: np.ones_like(x, bool))
    assert len(out) == 1 and np.array_equal(out[0], p)


def test_simplify_drops_collinear_keeps_corners():
    p = np.array([[0., 0], [1, 0.001], [2, 0], [2, 2]]); assert simplify(p, 0.01).tolist() == [[0, 0], [2, 0], [2, 2]]
