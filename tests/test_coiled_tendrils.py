import numpy as np
import pytest

from inkfield.core.controls import resolve
from inkfield.core.frame import Frame
from inkfield.core.rng import make_rng
from inkfield.pieces.coiled_tendrils import (PARAMS, generate, ribbed_tube, spiral_spine,
                                             tendril_spines)

FRAME = Frame("rect", 105, 148.5, 89, 132.5)
D = resolve(PARAMS, None)
def run(seed=7, frame=FRAME, **kw): return generate({**D, **kw}, frame, make_rng(seed, "piece"))
def pts(strokes): return np.vstack([s.points for s in strokes])

def test_deterministic_and_seed_sensitive():
    a, b, c = run(7), run(7), run(8)
    assert len(a) == len(b) and all(np.array_equal(x.points, y.points) for x, y in zip(a, b))
    assert len(a) != len(c) or not np.array_equal(pts(a), pts(c))

def test_strokes_are_well_formed():
    s = run(); assert len(s) > 100
    assert all(x.points.ndim == 2 and x.points.shape[1] == 2 and len(x.points) >= 2 and np.isfinite(x.points).all() and x.layer == 0 for x in s)

@pytest.mark.parametrize("name,value", [("turns", 4), ("arm_spacing", 4), ("tendrils", 5), ("length", 300), ("curl", 0.08),
                                        ("smoothness", 4), ("fan", 1.5), ("tube_width", 9), ("width_variation", 0), ("rib_gap", 1.5)])
def test_every_control_changes_the_picture(name, value):
    a, b = run(), run(**{name: value}); assert len(a) != len(b) or not np.array_equal(pts(a), pts(b))

def test_ribs_cross_the_spine_at_right_angles_and_span_the_tube():
    spine = np.column_stack([np.linspace(0, 50, 101), np.zeros(101)])      # straight, along x
    ribs = ribbed_tube(spine, np.full(101, 2.0), 0.8)
    a, b = np.array([r.points[0] for r in ribs]), np.array([r.points[1] for r in ribs])
    assert np.allclose(a[:, 0], b[:, 0])                                   # perpendicular to the spine
    assert np.allclose(np.abs(a[:, 1] - b[:, 1]), 4.0)                     # 2 x half-width
    assert np.allclose(np.diff(a[:, 0]), 0.8) and len(ribs) == 62          # one rib every 0.8 mm

def test_centre_coil_is_archimedean():
    # radius grows by one arm spacing per turn, so neighbouring arms stay that far apart
    points, theta = spiral_spine((0.0, 0.0), 7, 2.8)
    assert np.allclose(np.hypot(*points.T), 2.8 * theta / (2 * np.pi))
    assert np.isclose(theta[-1], 7 * 2 * np.pi)

def test_adding_or_lengthening_a_tendril_keeps_the_others():
    coil, theta = spiral_spine((105.0, 148.5), 7, 2.8)
    def spines(count, length):
        return tendril_spines(make_rng(7, "piece"), coil, theta, {**D, "tendrils": count, "length": length}, 1.0)
    nine, ten, longer = spines(9, 180), spines(10, 180), spines(9, 260)
    assert len(nine) == 9 and len(ten) == 10
    assert all(np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1]) for a, b in zip(nine, ten))
    assert all(len(b[0]) > len(a[0]) and np.allclose(b[0][:len(a[0])], a[0]) for a, b in zip(nine, longer))

def test_picture_keeps_its_proportions_on_a_bigger_frame():
    # spines scale with the frame; only the rib spacing (a pen distance) stays in millimetres
    big = Frame("rect", 210, 297, 178, 265)
    a, b = run(rib_gap=0.5), run(frame=big, rib_gap=1.0)
    assert len(a) == len(b) and np.allclose(2 * pts(a), pts(b))
