import numpy as np
import pytest

from inkfield.core.controls import resolve
from inkfield.core.frame import Frame
from inkfield.core.rng import make_rng
from inkfield.pieces.water_droplets import (IMPACT_GAP, IMPACT_RINGS, PARAMS, SIZE_RANGE, SMALLEST_RING,
                                            SPLASH_RINGS, TILT, generate, place_drops, ring_count, ring_gap,
                                            splash_count)

FRAME = Frame("rect", 105, 148.5, 89, 132.5)      # A4 portrait, 16 mm margin
D = resolve(PARAMS, None)
CALM = dict(wobble=0, interference=0, splashes=0, size_variety=0)   # bare rings of one size, nothing else
def run(seed=7, **kw): return generate({**D, **kw}, FRAME, make_rng(seed, "piece"))
def pts(strokes): return np.vstack([s.points for s in strokes])
def drops(count, clustering=0.0, seed=7): return place_drops(FRAME, make_rng(seed, "piece"), count, clustering)
def rings_of(drop, **kw): p = {**D, **kw}; return ring_count(p["rings"], p["ring_variety"], drop.u_rings)

def test_deterministic_and_seed_sensitive():
    a, b, c = run(7), run(7), run(8)
    assert len(a) == len(b) and all(np.array_equal(x.points, y.points) for x, y in zip(a, b))
    assert len(a) != len(c) or not np.array_equal(pts(a), pts(c))

def test_strokes_are_well_formed():
    s = run(); assert len(s) > 20
    assert all(x.points.ndim == 2 and x.points.shape[1] == 2 and len(x.points) >= 2 and np.isfinite(x.points).all() and x.layer == 0 for x in s)
    assert all(np.array_equal(x.points[0], x.points[-1]) for x in s)            # every ring is closed

@pytest.mark.parametrize("name,value", [("drops", 7), ("rings", 5), ("spacing", 0.08), ("growth", 1.0), ("wobble", 0.8),
                                        ("interference", 0.4), ("squash", 0.6), ("clustering", 0.8), ("splashes", 1), ("ring_variety", 0),
                                        ("size_variety", 1), ("splash_variety", 0)])
def test_every_control_changes_the_picture(name, value):
    a, b = run(), run(**{name: value}); assert len(a) != len(b) or not np.array_equal(pts(a), pts(b))

def test_adding_a_drop_leaves_the_others_as_they_were():
    nine, ten = drops(9), drops(10)
    assert len(nine) == 9 and len(ten) == 10 and ten[:9] == nine     # position, variety numbers, phases, splashes

def test_clustering_pulls_drops_towards_the_middle():
    def spread(c): return np.mean([np.hypot(d.x - FRAME.cx, d.y - FRAME.cy) for d in drops(24, c)])
    assert spread(1.0) < 0.6 * spread(0.0)

def test_calm_drop_is_rings_growing_by_the_spread_factor():
    s = run(drops=1, squash=1.0, **CALM)
    drop, gap = drops(1)[0], D["spacing"] * FRAME.scale
    count = rings_of(drop)
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
        for k in range(rings_of(drop)):
            x = next(s).points
            dev = np.abs(np.hypot(x[:, 0] - drop.x, x[:, 1] - drop.y) - gap * D["growth"] ** k)
            assert dev.max() <= 2 * 0.3 * gap + 1e-6; largest = max(largest, dev.max())
        for _ in range(IMPACT_RINGS): next(s)
    assert largest > 0.3 * gap

@pytest.mark.parametrize("seed", range(5))
def test_rings_never_fold_through_their_centre_even_with_every_drop_and_full_interference(seed):
    # squash 1: ring point j sits at c + r(θ_j) · (cos θ_j, sin θ_j), so its push along (cos θ_j, sin θ_j) is r(θ_j)
    gap = D["spacing"] * FRAME.scale
    s = iter(run(seed, drops=24, squash=1.0, interference=0.5, wobble=1, splashes=0, size_variety=0))
    for drop in drops(24, seed=seed):
        for k in range(rings_of(drop)):
            x = next(s).points; theta = np.linspace(0, 2 * np.pi, len(x))
            r = (x[:, 0] - drop.x) * np.cos(theta) + (x[:, 1] - drop.y) * np.sin(theta)
            assert r.min() >= SMALLEST_RING * gap * D["growth"] ** k - 1e-9
        for _ in range(IMPACT_RINGS): next(s)

def test_without_variety_every_drop_has_the_same_rings_size_and_splashes():
    s = run(drops=6, rings=9, splashes=4, ring_variety=0, size_variety=0, splash_variety=0, wobble=0, interference=0, squash=1.0)
    per_drop = 9 + IMPACT_RINGS + 4 * SPLASH_RINGS; assert len(s) == 6 * per_drop
    gap = D["spacing"] * FRAME.scale
    for i, drop in enumerate(drops(6)):                               # each drop's first ripple ring has radius s
        x = s[i * per_drop].points; assert np.allclose(np.hypot(x[:, 0] - drop.x, x[:, 1] - drop.y), gap)

def test_variety_formulas_cover_their_ranges():
    assert ring_count(20, 0, 0.0) == 20 and ring_count(20, 1, 0.999) == 19 and ring_count(20, 1, 0.0) == 2 and ring_count(20, 0.5, 0.0) == 10
    assert splash_count(8, 0, 0.9) == 8 and splash_count(8, 1, 0.0) == 8 and splash_count(8, 1, 0.999) == 0 and splash_count(8, 0.5, 0.5) == 6
    assert ring_gap(10, 0, 0.9) == 10 and np.isclose(ring_gap(10, 1, 0.0), 10 * (1 - SIZE_RANGE)) and np.isclose(ring_gap(10, 1, 1.0), 10 * (1 + SIZE_RANGE))

def test_full_variety_gives_drops_that_differ():
    found = drops(24)
    assert len({ring_count(24, 1, d.u_rings) for d in found}) > 5 and len({splash_count(12, 1, d.u_splash) for d in found}) > 5
    sizes = [ring_gap(1, 1, d.u_size) for d in found]; assert max(sizes) > 1.4 and min(sizes) < 0.6
