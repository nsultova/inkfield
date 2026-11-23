import math

import numpy as np
import pytest

from inkfield.core.controls import resolve
from inkfield.core.frame import Frame
from inkfield.core.rng import make_rng
from inkfield.pieces.mirror_shards import (BOW_POINTS, PARAMS, break_sheet, crack_bows,
                                           crack_lines, edge_key, generate, hatch, leaves_of,
                                           polygon_area, ring_chord, scatter_impacts,
                                           sheet_polygon, spoke_angles)

FRAME = Frame("rect", 105, 148.5, 85, 125)
D = resolve(PARAMS, None)
def run(seed=7, frame=FRAME, **kw): return generate({**D, **kw}, frame, make_rng(seed, "piece"))
def pts(strokes): return np.vstack([s.points for s in strokes])
def leaves(seed=7, frame=FRAME, **kw):
    rng, params = make_rng(seed, "piece"), {**D, **kw}
    sheet = sheet_polygon(frame)
    impacts = scatter_impacts(frame, rng, params["impacts"])
    return sheet, impacts, leaves_of(break_sheet(sheet, impacts, rng, params, frame.scale))
def is_convex_ccw(poly):
    turns = [(b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
             for a, b, c in zip(poly, poly[1:] + poly[:1], poly[2:] + poly[:2])]
    return all(t > -1e-9 for t in turns) and polygon_area(poly) > 0

def test_deterministic_and_seed_sensitive():
    a, b, c = run(7), run(7), run(8)
    assert len(a) == len(b) and all(np.array_equal(x.points, y.points) for x, y in zip(a, b))
    assert len(a) != len(c) or not np.array_equal(pts(a), pts(c))

def test_strokes_are_well_formed():
    for s in (run(), run(separation=0.6, glint=True), run(gap=1.5, glint=True, splinter=2, depth=7)):
        assert len(s) > 20
        assert all(x.points.ndim == 2 and x.points.shape[1] == 2 and len(x.points) >= 2 and np.isfinite(x.points).all() and x.layer == 0 for x in s)

@pytest.mark.parametrize("name,value", [("impacts", 5), ("spokes", 5), ("rings", 3), ("ring_growth", 2.0), ("splinter", 1.5), ("depth", 1), ("direction", 0.8), ("separation", 0.5), ("gap", 0.5), ("glint", True)])
def test_every_control_changes_the_picture(name, value):
    a, b = run(), run(**{name: value}); assert len(a) != len(b) or not np.array_equal(pts(a), pts(b))

@pytest.mark.parametrize("frame", [FRAME, Frame("circle", 100, 100, 80, 80), Frame("rect", 210, 148.5, 190, 130)])
def test_shards_tile_the_sheet_exactly(frame):
    # every split is refused rather than shaved, so the leaf areas add up to the sheet's area
    sheet, _, ls = leaves(frame=frame, impacts=4)
    assert abs(sum(polygon_area(s.poly) for s in ls) - polygon_area(sheet)) < 1e-6 * polygon_area(sheet)

def test_every_shard_is_convex_and_counter_clockwise():
    _, _, ls = leaves(spokes=4, splinter=2.0, depth=7)
    assert len(ls) > 100 and all(is_convex_ccw(s.poly) for s in ls)

def test_few_jittered_spokes_never_leave_a_half_turn_gap():
    for seed in range(20):
        a = spoke_angles(make_rng(seed, "piece"), 3, jitter=1.0)
        assert np.diff(a + [a[0] + 2 * math.pi]).max() < math.pi

@pytest.mark.parametrize("half_angle", [0.05, 0.7, 1.2])
@pytest.mark.parametrize("radius", [4.0, 60.0])
def test_ring_chord_meets_both_spokes_at_the_ladder_radius(half_angle, radius):
    # that is why neighbouring wedges' ring cracks join into one faceted ring
    ix, iy, mid = 30.0, 40.0, 0.9
    nx, ny, c = ring_chord(ix, iy, mid, half_angle, radius)
    for spoke in (mid - half_angle, mid + half_angle):
        dx, dy = math.cos(spoke), math.sin(spoke)
        assert abs((c - (nx * ix + ny * iy)) / (nx * dx + ny * dy) - radius) < 1e-9

def test_splinters_are_fine_near_the_impact_and_plates_large_at_the_edge():
    _, impacts, ls = leaves()
    def distance(s): return min(math.hypot(s.centroid[0] - x, s.centroid[1] - y) for x, y, _ in impacts)
    near = [polygon_area(s.poly) for s in ls if distance(s) < 0.15 * FRAME.scale]
    far = [polygon_area(s.poly) for s in ls if distance(s) > 0.6 * FRAME.scale]
    assert near and far and 20 * np.median(near) < np.median(far)

def test_separation_zero_draws_each_crack_exactly_once_in_few_strokes():
    sheet, _, ls = leaves()
    bows = crack_bows(ls, sheet, make_rng(1, "bows"))         # one per crack, none on the sheet edge
    lines = crack_lines(ls, bows)
    corners = [line[::BOW_POINTS - 1] for line in lines]       # each crack is BOW_POINTS - 1 steps
    drawn = [edge_key(a, b) for c in corners for a, b in zip(c[:-1], c[1:])]
    assert sorted(drawn) == sorted(bows) and len(lines) < len(bows) / 3

def test_glint_hatch_stays_inside_the_shard_at_its_spacing():
    lines = hatch([(0, 0), (20, 0), (20, 20), (0, 20)], angle=0.0, spacing=2.0)
    ends = np.array(lines).reshape(-1, 2)
    assert len(lines) >= 9 and (ends >= -1e-9).all() and (ends <= 20 + 1e-9).all()
    assert np.allclose(np.diff(sorted({round(y, 9) for y in ends[:, 1]})), 2.0)

def test_separation_moves_the_shards_without_breaking_them_again():
    # same shards in the same order, only moved and uniformly shrunk to fit: area ratios agree
    def areas(sep): return np.array([polygon_area([tuple(p) for p in s.points[:-1]]) for s in run(separation=sep)])
    a, b = areas(0.3), areas(0.9)
    assert len(a) == len(b) == len(leaves()[2]) and np.allclose(a / b, (a / b)[0], rtol=1e-6)
