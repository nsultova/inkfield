import numpy as np
import pytest

from inkfield.core.controls import resolve
from inkfield.core.frame import Frame
from inkfield.core.rng import make_rng
from inkfield.pieces.glass_droplets import PARAMS, SATELLITE_DEPTH, generate, drop_rings, satellites, slide_down

FRAME = Frame("rect", 105, 148.5, 86, 129)
D = resolve(PARAMS, None)
def run(seed=7, **kw): return generate({**D, **kw}, FRAME, make_rng(seed, "piece"))
def pts(strokes): return np.vstack([s.points for s in strokes])
def closed(s): return np.allclose(s.points[0], s.points[-1])

def test_deterministic_and_seed_sensitive():
    a, b, c = run(7), run(7), run(8)
    assert len(a) == len(b) and all(np.array_equal(x.points, y.points) for x, y in zip(a, b))
    assert len(a) != len(c) or not np.array_equal(pts(a), pts(c))

def test_strokes_are_well_formed():
    s = run(); assert len(s) > 50
    assert all(x.points.ndim == 2 and x.points.shape[1] == 2 and len(x.points) >= 2 and np.isfinite(x.points).all() and x.layer == 0 for x in s)

@pytest.mark.parametrize("name,value", [("drops", 20), ("sliding", 0.8), ("size", 14), ("trail", 120), ("viscosity", 0.9),
                                        ("roughness", 0.8), ("stick_slip", 0.9), ("rings", 3), ("warp", 0.5), ("beads", 4)])
def test_every_control_changes_the_picture(name, value):
    a, b = run(), run(**{name: value}); assert len(a) != len(b) or not np.array_equal(pts(a), pts(b))

def test_same_rng_state_gives_the_same_strokes():
    # two generators from the same seed, and one generator set back to the state it started in
    def same(a, b): return len(a) == len(b) and all(np.array_equal(x.points, y.points) for x, y in zip(a, b))
    assert same(generate(D, FRAME, make_rng(7, "piece")), generate(D, FRAME, make_rng(7, "piece")))
    rng = make_rng(7, "piece"); start = rng.bit_generator.state
    first = generate(D, FRAME, rng); rng.bit_generator.state = start
    assert same(first, generate(D, FRAME, rng))

def test_adding_a_drop_leaves_the_others_as_they_were():
    ten, eleven = run(drops=10), run(drops=11)
    assert len(eleven) > len(ten) and all(np.array_equal(x.points, y.points) for x, y in zip(ten, eleven))

def test_full_ring_warp_keeps_every_ring_on_its_own_side_of_the_centre():
    # with no motion a ring point sits at c + ρ · (−cos θ, v'), v' of the sign of sin θ: ρ > 0 means it points that way
    for seed in range(20):
        for ring in drop_rings(make_rng(seed, "t"), 50, 50, 10, np.pi / 2, speed=0, count=6, warp=2, viscosity=0.3):
            theta = 2 * np.pi * np.arange(len(ring) - 1) / (len(ring) - 1)
            x, y = (ring[:-1] - 50).T
            assert (-x * np.cos(theta) + y * np.sin(theta) > 0).all()

def test_satellites_follow_the_rings_slider():
    track = np.column_stack([np.full(40, 50.0), np.linspace(20, 60, 40)])
    for seed in range(10):
        count = make_rng(seed, "t").integers(1, SATELLITE_DEPTH + 2)        # how many satellites (drawn first)
        lines = satellites(make_rng(seed, "t"), track, 5.0, SATELLITE_DEPTH, {**D, "rings": 1})
        assert len(lines) == count                                           # one ring each

def test_a_resting_bead_is_concentric_rings_evenly_spaced():
    s = run(drops=1, sliding=0, rings=6, warp=0)
    assert len(s) == 6 and all(closed(x) for x in s)
    half_width = np.array([np.ptp(x.points[:, 0]) / 2 for x in s])
    centre_x = np.array([(x.points[:, 0].max() + x.points[:, 0].min()) / 2 for x in s])
    centre_y = np.array([x.points[:, 1].min() for x in s]) + half_width     # the top is a full radius up
    assert np.allclose(centre_x, centre_x[0]) and np.allclose(centre_y, centre_y[0])
    assert np.allclose(half_width / half_width[-1], np.arange(1, 7) / 6)
    bottom = np.array([x.points[:, 1].max() for x in s]) - centre_y        # the lower side sags 5 % flatter
    assert np.allclose(bottom, 0.95 * half_width)

def test_a_moving_drop_is_a_teardrop_with_its_tail_behind():
    # moving straight down the page (angle π/2): the tail points up, the front is a little flattened
    ring = drop_rings(make_rng(1, "t"), 50, 50, 10, np.pi / 2, speed=0.3, count=1, warp=0, viscosity=0.3)[0]
    x, y = ring.T
    assert 50 - y.min() > 10.2 and y.max() - 50 < 10 and np.isclose(x.max() - 50, 10, atol=0.05)

def test_sliding_drops_run_down_and_stop_at_the_bottom():
    paths = [slide_down(make_rng(seed, "t"), 50, 20, pane=(210, 297), trail=60, size=8, viscosity=0.3, roughness=0.15, stick_slip=0.25)
             for seed in range(20)]
    for path in paths:
        assert path[-1, 1] > path[0, 1] + 20 and path[:, 1].max() <= 297 * 0.97
    long = slide_down(make_rng(0, "t"), 50, 100, pane=(210, 297), trail=200, size=8, viscosity=0.3, roughness=0.15, stick_slip=0.25)
    assert long[-1, 1] > 280                                              # a long trail reaches the bottom
