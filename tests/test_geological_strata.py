import numpy as np
import pytest

from inkfield.core.controls import resolve
from inkfield.core.frame import Frame
from inkfield.core.rng import make_rng
from inkfield.pieces.geological_strata import PARAMS, generate, gradient_noise

FRAME = Frame("rect", 105, 148.5, 80, 110)
D = resolve(PARAMS, None)
def run(seed=7, **kw): return generate({**D, **kw}, FRAME, make_rng(seed, "piece"))
def pts(strokes): return np.vstack([s.points for s in strokes])

def test_deterministic_and_seed_sensitive():
    a, b, c = run(7), run(7), run(8)
    assert len(a) == len(b) and all(np.array_equal(x.points, y.points) for x, y in zip(a, b))
    assert len(a) != len(c) or not np.array_equal(pts(a), pts(c))

def test_strokes_are_well_formed():
    s = run(); assert len(s) > 50
    assert all(x.points.ndim == 2 and x.points.shape[1] == 2 and len(x.points) >= 2 and np.isfinite(x.points).all() and x.layer == 0 for x in s)

@pytest.mark.parametrize("name,value", [("spacing", 2.0), ("relief", 0.2), ("fold_size", 1.5), ("detail", 3),
                                        ("roughness", 0.7), ("warp", 0.5), ("warp_size", 3.0),
                                        ("torn", 0.0), ("edge_fade", 0.15)])
def test_every_control_changes_the_picture(name, value):
    a, b = run(), run(**{name: value}); assert len(a) != len(b) or not np.array_equal(pts(a), pts(b))

def test_no_relief_gives_flat_evenly_spaced_lines():
    s = run(relief=0, torn=0, edge_fade=0, spacing=2.0)
    ys = np.array([x.points[0, 1] for x in s])
    assert all(np.all(x.points[:, 1] == x.points[0, 1]) for x in s)      # every line is level
    assert len(s) == 111 and np.allclose(np.diff(ys), 2.0)               # 220 mm tall, 2 mm apart

def test_clean_edges_give_one_full_width_line_per_strip():
    s = run(torn=0, edge_fade=0)
    x0, _, x1, _ = FRAME.bbox
    assert len(s) == 221                                                  # 220 mm tall, 1 mm apart
    assert all(np.isclose(x.points[0, 0], x0) and np.isclose(x.points[-1, 0], x1) for x in s)
    assert all(np.all(np.diff(x.points[:, 0]) > 0) for x in s)          # lines only move up and down

def test_relief_bounds_the_displacement():
    flat = run(relief=0, torn=0, edge_fade=0)
    hilly = run(relief=0.3, torn=0, edge_fade=0)
    dy = np.abs(pts(hilly)[:, 1] - pts(flat)[:, 1])
    assert dy.max() <= 0.3 * FRAME.scale and dy.max() > 0.05 * FRAME.scale   # fbm rarely nears ±1

def test_gradient_noise_is_zero_on_the_lattice_and_bounded():
    perm = make_rng(1, "t").permutation(256)
    i, j = np.meshgrid(np.arange(-5, 6), np.arange(-5, 6))
    assert np.allclose(gradient_noise(i.astype(float), j.astype(float), perm), 0)
    x, y = make_rng(2, "t").uniform(-50, 50, (2, 20000))
    n = gradient_noise(x, y, perm)
    assert np.abs(n).max() <= 1 and n.std() > 0.1
