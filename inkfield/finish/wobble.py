"""Hand wobble: nudge every point a little, so lines look drawn by hand rather than by machine.

The nudge comes from a smooth random field (see `inkfield.core.noise`): neighbouring points are
pushed almost the same way, so a line bends gently instead of turning jagged. The field ripples
on a scale of WAVELENGTH, and each of its two components lies in [-1, 1], so a point moves at
most amount × REACH along x and along y. The field has its own random stream, so turning the
wobble up or down never changes the picture the piece draws.
"""
import numpy as np

from inkfield.core.noise import SmoothField
from inkfield.core.rng import make_rng
from inkfield.core.stroke import Stroke

REACH = 1.1        # largest push along each axis at full wobble, mm
WAVELENGTH = 9     # size of the wobble's ripples, mm


def wobble(strokes, amount: float, seed) -> list[Stroke]:
    if amount == 0 or not strokes:
        return list(strokes)
    field = SmoothField(make_rng(seed, "wobble"), wavelength=WAVELENGTH)

    # Push all points of all strokes at once, then cut the result back into strokes.
    points = np.vstack([s.points for s in strokes])
    dx, dy = field(points[:, 0], points[:, 1])
    moved = points + amount * REACH * np.column_stack([dx, dy])
    stroke_ends = np.cumsum([len(s.points) for s in strokes])[:-1]
    return [Stroke(part, s.layer) for part, s in zip(np.split(moved, stroke_ends), strokes)]
