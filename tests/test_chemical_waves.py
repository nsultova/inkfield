import numpy as np
import pytest

from inkfield.core.controls import resolve
from inkfield.core.frame import Frame
from inkfield.core.rng import make_rng
from inkfield.pieces.chemical_waves import PARAMS, generate, place_pacemakers, uneven_medium

FRAME = Frame("circle", 105, 148.5, 86, 86)
D = resolve(PARAMS, None)
def run(seed=7, **kw): return generate({**D, **kw}, FRAME, make_rng(seed, "piece"))
def pts(strokes): return np.vstack([s.points for s in strokes])

def test_deterministic_and_seed_sensitive():
    a, b, c = run(7), run(7), run(8)
    assert len(a) == len(b) and all(np.array_equal(x.points, y.points) for x, y in zip(a, b))
    assert len(a) != len(c) or not np.array_equal(pts(a), pts(c))

def test_strokes_are_well_formed():
    s = run(); assert len(s) > 5
    assert all(x.points.ndim == 2 and x.points.shape[1] == 2 and len(x.points) >= 2 and np.isfinite(x.points).all() and x.layer == 0 for x in s)

@pytest.mark.parametrize("name,value", [("sources", 3), ("spirals", 1.0), ("wavelength", 9), ("elapsed", 1.0), ("stagger", 0.1), ("uneven", 0.8)])
def test_every_control_changes_the_picture(name, value):
    a, b = run(), run(**{name: value}); assert len(a) != len(b) or not np.array_equal(pts(a), pts(b))

def test_adding_a_pacemaker_leaves_the_others_as_they_were():
    def place(count): return place_pacemakers(FRAME, make_rng(7, "piece"), count, 0.5, 0.7, 40.0)
    nine, ten = place(9), place(10)
    assert len(nine) == 9 and len(ten) == 10 and ten[:9] == nine   # position, delay, kind, turn, offset

def test_single_target_gives_concentric_rings_one_wavelength_apart():
    s = run(sources=1, spirals=0, uneven=0, stagger=0, elapsed=0.5, wavelength=5)
    centre = FRAME.sample(make_rng(7, "piece"), 1, shrink=0.92)[0]     # same draw order as generate
    radii = sorted(float(np.hypot(*(x.points - centre).T).mean()) for x in s)
    assert len(radii) == 9                            # elapsed 43 mm: fronts at 43, 38, …, 3
    assert np.allclose(np.diff(radii), 5, atol=0.05) and abs(radii[-1] - 43) < 0.05
    for x in s: r = np.hypot(*(x.points - centre).T); assert r.max() - r.min() < 0.05

def test_rings_are_smooth():
    s = run(sources=1, spirals=0, uneven=0, stagger=0, elapsed=0.5, wavelength=5)
    for x in s:
        d = np.diff(x.points, axis=0); a = np.arctan2(d[:, 1], d[:, 0])
        turn = np.abs((np.diff(a) + np.pi) % (2 * np.pi) - np.pi)
        assert np.degrees(turn.max()) < 20

def test_lines_meet_at_the_seam():
    # two targets, no delay: the seam is the perpendicular bisector; ends must lie within 0.3 mm of it
    s = run(sources=2, spirals=0, uneven=0, stagger=0, elapsed=1.2)
    P = FRAME.sample(make_rng(7, "piece"), 2, shrink=0.92)      # same draw order as generate
    ends = np.array([e for x in s for e in (x.points[0], x.points[-1]) if not np.allclose(x.points[0], x.points[-1])])
    x0, y0, x1, y1 = FRAME.bbox                                  # ends where the grid stops are not seam ends
    ends = ends[np.minimum.reduce([ends[:, 0] - x0, x1 - ends[:, 0], ends[:, 1] - y0, y1 - ends[:, 1]]) > 0.5]
    gap = np.abs(np.hypot(*(ends - P[0]).T) - np.hypot(*(ends - P[1]).T))
    assert len(ends) > 0 and (gap < 0.3).mean() > 0.9           # the rest are ends at the outer reach

def test_spiral_has_a_clean_core():
    s = run(sources=1, spirals=1.0, uneven=0, stagger=0, elapsed=0.6, wavelength=6)
    P = FRAME.sample(make_rng(7, "piece"), 1, shrink=0.92)[0]
    assert np.hypot(*(pts(s) - P).T).min() >= 0.35 * 6 - 0.05

def test_uneven_medium_never_folds_space():
    # strongest unevenness at the longest wavelength: every small cell of the page must map to a
    # cell the same way round in the medium (positive Jacobian determinant), or rings would cross
    x0, y0, x1, y1 = FRAME.bbox
    xs, ys = np.linspace(x0, x1, 861), np.linspace(y0, y1, 861)
    for seed in range(5):
        qx, qy = uneven_medium(FRAME, make_rng(seed, "piece"), 1.0, 14)(*np.meshgrid(xs, ys))
        qx_x, qy_x = np.diff(qx, axis=1)[:-1], np.diff(qy, axis=1)[:-1]       # change along x
        qx_y, qy_y = np.diff(qx, axis=0)[:, :-1], np.diff(qy, axis=0)[:, :-1]  # change along y
        assert (qx_x * qy_y - qy_x * qx_y).min() > 0
