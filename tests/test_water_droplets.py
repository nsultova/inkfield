import numpy as np
import pytest

from inkfield.core.controls import resolve
from inkfield.core.frame import Frame
from inkfield.core.rng import make_rng
from inkfield.pieces.water_droplets import (IMPACT_GAP, IMPACT_RINGS, PARAMS, PUDDLE_SIZE, TILT,
                                            generate, place_drops)

FRAME = Frame("rect", 105, 148.5, 89, 132.5)      # A4 portrait, 16 mm margin
D = resolve(PARAMS, None)
CALM = dict(wobble=0, interference=0, splashes=0, puddle=0)   # bare rings, nothing else
def run(seed=7, **kw): return generate({**D, **kw}, FRAME, make_rng(seed, "piece"))
def pts(strokes): return np.vstack([s.points for s in strokes])
def drops(count, clustering=0.0, seed=7):
    rng = make_rng(seed, "piece"); rng.uniform(0, 2 * np.pi)     # same draw order as generate
    return place_drops(FRAME, rng, count, clustering)

def test_deterministic_and_seed_sensitive():
    a, b, c = run(7), run(7), run(8)
    assert len(a) == len(b) and all(np.array_equal(x.points, y.points) for x, y in zip(a, b))
    assert len(a) != len(c) or not np.array_equal(pts(a), pts(c))

def test_strokes_are_well_formed():
    s = run(); assert len(s) > 20
    assert all(x.points.ndim == 2 and x.points.shape[1] == 2 and len(x.points) >= 2 and np.isfinite(x.points).all() and x.layer == 0 for x in s)
    assert all(np.array_equal(x.points[0], x.points[-1]) for x in s)            # every ring is closed

@pytest.mark.parametrize("name,value", [("drops", 7), ("rings", 5), ("spacing", 0.08), ("growth", 1.0), ("wobble", 0.8),
                                        ("interference", 0.4), ("squash", 0.6), ("clustering", 0.8), ("splashes", 1), ("puddle", 0)])
def test_every_control_changes_the_picture(name, value):
    a, b = run(), run(**{name: value}); assert len(a) != len(b) or not np.array_equal(pts(a), pts(b))

def test_adding_a_drop_leaves_the_others_as_they_were():
    nine, ten = drops(9), drops(10)
    assert len(nine) == 9 and len(ten) == 10 and ten[:9] == nine     # position, age, phases, splashes

def test_clustering_pulls_drops_towards_the_middle():
    def spread(c): return np.mean([np.hypot(d.x - FRAME.cx, d.y - FRAME.cy) for d in drops(24, c)])
    assert spread(1.0) < 0.6 * spread(0.0)

def test_calm_drop_is_rings_growing_by_the_spread_factor():
    s = run(drops=1, squash=1.0, **CALM)
    drop, gap = drops(1)[0], D["spacing"] * FRAME.scale
    count = max(2, int(D["rings"] * drop.age))
    ripples = [gap * D["growth"] ** k for k in range(count)]
    impacts = [i * IMPACT_GAP * gap for i in range(1, IMPACT_RINGS + 1)]
    radii = sorted(float(np.hypot(x.points[:, 0] - drop.x, x.points[:, 1] - drop.y).mean()) for x in s)
    assert len(s) == count + IMPACT_RINGS and np.allclose(radii, sorted(ripples + impacts), atol=0.01)
    for x in s: r = np.hypot(x.points[:, 0] - drop.x, x.points[:, 1] - drop.y); assert r.max() - r.min() < 1e-6

def test_squash_makes_ellipses_along_the_tilted_axis():
    s = run(drops=1, squash=0.6, **CALM)
    drop, gap = drops(1)[0], D["spacing"] * FRAME.scale
    for k, x in enumerate(s[:2]):                                     # the first two ripple rings
        dx, dy = x.points[:, 0] - drop.x, x.points[:, 1] - drop.y
        u = dx * np.cos(TILT) + dy * np.sin(TILT); v = -dx * np.sin(TILT) + dy * np.cos(TILT)
        r = gap * D["growth"] ** k
        assert abs(u.max() - 0.6 * r) < 0.01 and abs(v.max() - r) < 0.01

def test_interference_bends_rings_by_at_most_its_strength_per_other_drop():
    gap = D["spacing"] * FRAME.scale
    s = iter(run(drops=3, squash=1.0, **{**CALM, "interference": 0.3}))
    largest = 0.0
    for drop in drops(3):                        # strokes come drop by drop: its ripples, then impacts
        for k in range(max(2, int(D["rings"] * drop.age))):
            x = next(s).points
            dev = np.abs(np.hypot(x[:, 0] - drop.x, x[:, 1] - drop.y) - gap * D["growth"] ** k)
            assert dev.max() <= 2 * 0.3 * gap + 1e-6; largest = max(largest, dev.max())
        for _ in range(IMPACT_RINGS): next(s)
    assert largest > 0.3 * gap

def test_puddle_edge_is_an_ellipse_inside_the_frame():
    s = run(puddle=1); t = run(puddle=0)
    assert len(s) == len(t) + 1
    edge = s[0].points
    assert abs(edge[:, 0].max() - FRAME.cx - PUDDLE_SIZE * FRAME.half_w) < 0.03 * FRAME.scale
    assert abs(edge[:, 1].max() - FRAME.cy - PUDDLE_SIZE * FRAME.half_h) < 0.03 * FRAME.scale
