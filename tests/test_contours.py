import numpy as np

from inkfield.core.contours import trace_whole_numbers, trace_zero
from inkfield.core.polyline import length

xs = ys = np.arange(0, 100.01, 0.5); X, Y = np.meshgrid(xs, ys)


def test_circle():
    lines = trace_zero(np.hypot(X - 50, Y - 50) - 20, xs, ys)
    assert len(lines) == 1
    p = lines[0]; r = np.hypot(p[:, 0] - 50, p[:, 1] - 50)
    assert np.allclose(p[0], p[-1]) and np.abs(r - 20).max() < 0.02
    assert abs(length(p) - 2 * np.pi * 20) < 0.005 * 2 * np.pi * 20


def test_open_line_runs_edge_to_edge():
    lines = trace_zero(X - 30.25, xs, ys)
    assert len(lines) == 1 and np.allclose(lines[0][:, 0], 30.25)
    assert sorted([lines[0][0, 1], lines[0][-1, 1]]) == [0, 100]


def test_two_separate_loops():
    f = np.minimum(np.hypot(X - 25, Y - 25), np.hypot(X - 75, Y - 75)) - 10
    assert len(trace_zero(f, xs, ys)) == 2


def test_cells_mask_and_nan():
    f = np.hypot(X - 50, Y - 50) - 20
    assert trace_zero(f, xs, ys, cells=np.zeros((len(ys) - 1, len(xs) - 1), bool)) == []
    g = f.copy(); g[:, X[0] > 50] = np.nan
    assert all((ln[:, 0] <= 50).all() for ln in trace_zero(g, xs, ys))


def test_whole_numbers_gives_one_ring_per_wavelength():
    lines = trace_whole_numbers(np.hypot(X - 50, Y - 50) / 5.0, xs, ys)
    closed = [ln for ln in lines if np.allclose(ln[0], ln[-1])]
    radii = sorted(round(float(np.hypot(ln[:, 0] - 50, ln[:, 1] - 50).mean())) for ln in closed)
    assert radii == [5, 10, 15, 20, 25, 30, 35, 40, 45, 50]
    for ln in closed:
        r = np.hypot(ln[:, 0] - 50, ln[:, 1] - 50); assert r.max() - r.min() < 0.05
