import numpy as np
import pytest

from inkfield.core.controls import resolve
from inkfield.core.frame import Frame
from inkfield.core.rng import make_rng
from inkfield.pieces.turbulent_lines import PARAMS, chaos, generate, line_heights

FRAME = Frame("rect", 105, 148.5, 80, 120)
D = resolve(PARAMS, None)
def run(seed=7, frame=FRAME, **kw): return generate({**D, **kw}, frame, make_rng(seed, "piece"))
def pts(strokes): return np.vstack([s.points for s in strokes])

def test_deterministic_and_seed_sensitive():
    a, b, c = run(7), run(7), run(8)
    assert len(a) == len(b) and all(np.array_equal(x.points, y.points) for x, y in zip(a, b))
    assert len(a) != len(c) or not np.array_equal(pts(a), pts(c))

def test_strokes_are_well_formed():
    s = run(); assert len(s) > 45
    assert all(x.points.ndim == 2 and x.points.shape[1] == 2 and len(x.points) >= 2 and np.isfinite(x.points).all() and x.layer == 0 for x in s)

@pytest.mark.parametrize("name,value", [("lines", 30), ("bumps", 10), ("strands", 5), ("amplitude", 0.2), ("spread", 0.8),
                                        ("smoothing", 0.0), ("origin_x", 0.5), ("origin_y", 0.5), ("reach", 1.5), ("folding", 6)])
def test_every_control_changes_the_picture(name, value):
    a, b = run(), run(**{name: value}); assert len(a) != len(b) or not np.array_equal(pts(a), pts(b))

def test_lines_run_across_the_whole_frame():
    x0, _, x1, _ = FRAME.bbox
    for s in run(): assert s.points[0, 0] == x0 and s.points[-1, 0] == x1

def test_far_from_the_origin_lines_are_calm_single_and_straight():
    # chaos origin top-left, reach 0.85: the bottom lines are beyond it, so each is one ruler-straight stroke
    heights = line_heights(FRAME, D["lines"]); _, y0, _, y1 = FRAME.bbox
    calm = [h for h in heights if (h - y0) / (y1 - y0) > 0.86]
    strokes = run()
    for h in calm:
        on_line = [s for s in strokes if abs(s.points[0, 1] - h) < 1e-9]
        assert len(on_line) == 1 and np.ptp(on_line[0].points[:, 1]) == 0

def test_near_the_origin_lines_split_into_a_turbulent_bundle():
    # the top line gets round(strands · chaos(0.25, its height)) strands, each pushed off its base height
    heights = line_heights(FRAME, D["lines"]); _, y0, _, y1 = FRAME.bbox
    top = heights[0]; expected = round(D["strands"] * chaos(0.25, (top - y0) / (y1 - y0), 0, 0, D["reach"]))
    bundle = [s for s in run() if np.isclose(s.points[-1, 1], top) and np.ptp(s.points[:, 1]) > 0.5]
    assert expected >= 5 and len(bundle) == expected

def test_chaos_follows_its_origin():
    # origin top-right: at the left edge chaos is zero, so every strand starts exactly on its line's base height
    heights = line_heights(FRAME, D["lines"])
    starts = np.array([s.points[0, 1] for s in run(origin_x=1.0)])
    assert np.abs(starts[:, None] - heights[None, :]).min(axis=1).max() < 1e-9

def test_any_page_shape():
    for frame in (Frame("rect", 210, 148.5, 190, 130), Frame("rect", 100, 100, 70, 70), Frame("circle", 100, 100, 70, 70)):
        s = run(frame=frame); x0, y0, x1, y1 = frame.bbox
        p = pts(s); assert len(s) > 45 and p[:, 0].min() == x0 and p[:, 0].max() == x1
        assert y0 - 0.3 * frame.scale < p[:, 1].min() and p[:, 1].max() < y1   # bundles stay near the frame
