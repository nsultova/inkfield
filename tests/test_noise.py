import numpy as np

from inkfield.core.noise import SmoothField
from inkfield.core.rng import make_rng


def test_smooth_field_is_seeded_bounded_and_smooth():
    f = SmoothField(make_rng(1), 80); g = SmoothField(make_rng(1), 80)
    x = np.linspace(0, 300, 500); y = np.zeros(500)
    dx, dy = f(x, y)
    assert np.array_equal(dx, g(x, y)[0]) and np.abs(dx).max() <= 1.0001 and np.abs(dy).max() <= 1.0001
    assert np.abs(np.diff(dx)).max() < 0.2 and dx.std() > 0.1
