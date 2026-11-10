import numpy as np

from inkfield.core.frame import Frame
from inkfield.core.polyline import length
from inkfield.core.rng import make_rng
from inkfield.core.stroke import Stroke
from inkfield.finish import apply, inner_frame
from inkfield.finish.clip import clip
from inkfield.finish.order import order
from inkfield.finish.tidy import tidy
from inkfield.finish.wobble import wobble

OUTER = Frame("circle", 100, 100, 50, 50)
def S(*p): return Stroke(np.array(p, float))

def test_clip_cuts_exactly_and_keeps_inside():
    out = clip([S((0, 100), (200, 100))], OUTER)
    assert len(out) == 1 and abs(out[0].points[0, 0] - 50) <= 0.01 and abs(out[0].points[-1, 0] - 150) <= 0.01
    p = np.vstack([s.points for s in out]); assert (np.hypot(p[:, 0] - 100, p[:, 1] - 100) <= 50.011).all()

def test_wobble_zero_is_identity_and_nonzero_is_seeded():
    s = [S((0, 0), (50, 0), (100, 0))]
    assert np.array_equal(wobble(s, 0, 1)[0].points, s[0].points)
    a, b = wobble(s, 1, 1)[0].points, wobble(s, 1, 1)[0].points
    assert np.array_equal(a, b) and not np.array_equal(a, s[0].points) and np.abs(a - s[0].points).max() <= 1.1 * 1.0001

def test_tidy_joins_drops_and_simplifies():
    out = tidy([S((0, 0), (5, 0)), S((10, 0), (5.05, 0)), S((50, 50), (50.5, 50))])
    assert len(out) == 1 and np.allclose(out[0].points[[0, -1]], [[0, 0], [10, 0]], atol=0.06) and len(out[0].points) <= 3

def test_order_keeps_the_same_strokes_and_shortens_travel():
    rng = make_rng(1); strokes = [S(*rng.uniform(0, 200, (2, 2))) for _ in range(60)]
    out = order(strokes)
    key = lambda s: tuple(sorted(map(tuple, np.round(s.points, 6).tolist())))
    assert sorted(map(key, out)) == sorted(map(key, strokes))
    travel = lambda ss: sum(np.hypot(*(b.points[0] - a.points[-1])) for a, b in zip(ss, ss[1:]))
    assert travel(out) < 0.5 * travel(strokes)

def test_apply_with_border_on_and_off():
    line = [S((0, 100), (200, 100))]
    on = {"wobble": 0, "border": True}; off = {"wobble": 0, "border": False}
    inner = inner_frame(OUTER, on); assert inner.half_w == 50 - 0.035 * 50 and inner_frame(OUTER, off) == OUTER
    a = apply(line, inner, OUTER, on, 1); b = apply(line, OUTER, OUTER, off, 1)
    assert len(a) == 3 and len(b) == 1
    assert max(length(s.points) for s in a) > 2 * np.pi * 49

def test_apply_on_nothing():
    assert apply([], OUTER, OUTER, {"wobble": 0.5, "border": False}, 1) == []
