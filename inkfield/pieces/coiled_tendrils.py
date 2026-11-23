"""Coiled tendrils: a tight central coil with ribbed, wandering tendrils sprouting from it.

What the picture shows
----------------------
A sculpture bent from coiled wire: one flat spiral of thick, ribbed tubing in the middle, and a
bundle of the same tubing running out of its outer turns in slow, organic curves. The tubes are
never outlined. Each is drawn only by its ribs, short pen lines laid across it close together,
the way the turns of a coiled spring catch the light. The eye joins the rib ends into the
tube's edges.

The model
---------
Every line in the picture is a rib across a tube, and every tube is a spine (a centre line) with
a width. Two kinds of spine are made:

* The coil is an Archimedean spiral around a centre c, a little left of and below the middle:

      r(θ) = spacing · θ / 2π,   θ from 0 to 2π · turns,   point = c + r(θ) · (cos θ, sin θ)

  Each full turn adds exactly one arm spacing to the radius, so neighbouring arms are evenly
  spaced. The coil's tube is 0.7 times as wide as the tendrils'.

* A tendril starts at a random point on the outer 60 % of the coil (by angle) and sets off along
  the coil's tangent there, turned by a random angle of up to ± fan-out. It is a random walk of
  small equal steps h whose heading drifts:

      heading_k = start angle + curl · (n_1 + n_2 + ... + n_k)
      point_k   = point_(k-1) + h · (cos heading_k, sin heading_k)

  where n is uniform random noise in [-1, 1] smoothed by a moving average over ± smoothness
  steps. Smoothing makes neighbouring steps turn the same way for a while, so the tendril curls
  gently in one direction, then the other, instead of jittering. Each tendril's length is the
  slider value times a random factor from 0.5 to 1.5, and its width the slider value times a
  random factor from 1 - variation to 1 + variation.

Ribs. Walk along a spine and lay a rib every `rib spacing` millimetres of arc length: a straight
line through the spine point, perpendicular to the spine there, as long as the tube is wide. The
width tapers to nothing over the first and last 15 % of the spine (never below 5 % of the full
width), so tubes start and end in points.

Sizes. The prototype was drawn on a bare 210 × 297 mm sheet. Here, every size in the picture
(arm spacing, tube width, tendril length, the walk's step) is a number of the prototype's
millimetres, multiplied by size = frame reference length / 105 (the reference length is half
the frame's shorter side; 105 mm was the prototype's). So the picture keeps its proportions on
any page. The rib spacing is the exception: it decides how dark the ink gets with a given pen,
so it stays in real millimetres.

The controls
------------
Spiral turns      how many times the coil winds round.
Arm spacing       the distance between neighbouring turns of the coil (prototype mm).
Tendrils          how many tendrils sprout from the coil. Adding one leaves the others as they
                  were.
Tendril length    the average tendril length (prototype mm); each one is 0.5 to 1.5 times this.
                  A longer setting extends each tendril along the path it was already taking.
Curl              how fast a tendril's heading drifts: radians per step for a full-strength push.
Smoothness        how many steps either side the curl noise is averaged over; higher gives
                  longer, calmer bends.
Fan-out           the largest angle, in radians, between a tendril's start and the coil's
                  tangent.
Tube width        the average tendril width (prototype mm).
Width variation   how much tendril widths differ, as a fraction of the average.
Rib spacing       the distance between neighbouring ribs along a tube, in real mm. (The
                  prototype asked for 0.6 but could only place ribs on its 0.5 mm walk steps,
                  so its tendrils were ribbed every 1 mm; 0.8 sits between, chosen by eye. For
                  the same reason its ribs were never closer than 0.5 mm, which is this slider's
                  lowest value: closer ribs also cost many more pen lifts.)

How the lines are drawn
-----------------------
1. Work out the size factor and the coil's centre.
2. Make the coil's spine and lay its ribs.
3. Draw every tendril's random numbers, walk its spine, and lay its ribs.
"""
import math

import numpy as np

from inkfield.core.controls import Slider
from inkfield.core.piece import Meta
from inkfield.core.stroke import Stroke

META = Meta(
    slug="coiled-tendrils",
    title="Coiled tendrils",
    subtitle="Ribbed wire tubes",
    framed_shape="rect",
    seed=6,
    info=("A flat Archimedean spiral, r = spacing · θ / 2π, with tendrils sprouting from its outer "
          "turns. Each tendril is a random walk whose heading drifts by smoothed noise, so it curls "
          "slowly one way, then the other. Nothing is outlined: every tube is drawn only by short "
          "ribs laid across it at a fixed spacing, like the turns of a coiled spring."),
)

PARAMS = [
    Slider("turns",           "Spiral turns",    2,    15,   1,     7),
    Slider("arm_spacing",     "Arm spacing",     1,    6,    0.1,   2.8),
    Slider("tendrils",        "Tendrils",        1,    30,   1,     14),
    Slider("length",          "Tendril length",  40,   400,  5,     180),
    Slider("curl",            "Curl",            0.01, 0.12, 0.005, 0.04),
    Slider("smoothness",      "Smoothness",      2,    30,   1,     12),
    Slider("fan",             "Fan-out",         0.1,  2,    0.05,  0.6),
    Slider("tube_width",      "Tube width",      1,    15,   0.5,   5),
    Slider("width_variation", "Width variation", 0,    0.8,  0.05,  0.4),
    Slider("rib_gap",         "Rib spacing",     0.5,  2,    0.05,  0.8, " mm"),
]


def _slider_max(name):
    return next(control.max for control in PARAMS if control.name == name)


PROTOTYPE_SCALE = 105.0     # the prototype sheet's reference length (half of 210 mm), mm
CENTRE_X = 0.45             # coil centre, as a fraction of the frame's width from its left edge
CENTRE_Y = 0.62             # ... and of its height from its top edge
COIL_ANGLE_STEP = 0.02      # angle between neighbouring points of the coil's spine, radians
COIL_WIDTH = 0.7            # the coil's tube width, as a fraction of the tendrils' average
SPROUT_FROM = 0.4           # tendrils sprout from the coil beyond this fraction of its angle
LENGTH_RANGE = (0.5, 1.5)   # each tendril's length is the slider value times a factor in here
WALK_STEP = 0.5             # length of one step of a tendril's walk, prototype mm
TAPER = 0.15                # tubes narrow to a point over this fraction of their spine at each end
THINNEST = 0.05             # ... but never below this fraction of their full width
MAX_TENDRILS = int(_slider_max("tendrils"))
MAX_STEPS = math.ceil(LENGTH_RANGE[1] * _slider_max("length") / WALK_STEP)


def generate(params, frame, rng) -> list[Stroke]:
    # 1. The prototype's millimetres in this frame's millimetres, and where the coil sits.
    size = frame.scale / PROTOTYPE_SCALE
    x0, y0, x1, y1 = frame.bbox
    centre = (x0 + CENTRE_X * (x1 - x0), y0 + CENTRE_Y * (y1 - y0))
    rib_gap = params["rib_gap"]

    # 2. The coil, a slightly thinner tube, tapered by how far round it has wound.
    coil, theta = spiral_spine(centre, params["turns"], params["arm_spacing"] * size)
    coil_width = COIL_WIDTH * params["tube_width"] * size
    strokes = ribbed_tube(coil, coil_width / 2 * taper(theta / theta[-1]), rib_gap)

    # 3. The tendrils, tapered by how far along their own spine they are.
    for spine, width in tendril_spines(rng, coil, theta, params, size):
        progress = np.linspace(0, 1, len(spine))
        strokes += ribbed_tube(spine, width / 2 * taper(progress), rib_gap)
    return strokes


def spiral_spine(centre, turns, spacing):
    """The coil's centre line: points c + r(θ)(cos θ, sin θ), r = spacing · θ / 2π, and their θ."""
    theta_end = 2 * math.pi * turns
    theta = np.linspace(0, theta_end, math.ceil(theta_end / COIL_ANGLE_STEP) + 1)
    radius = spacing * theta / (2 * math.pi)
    points = np.column_stack([centre[0] + radius * np.cos(theta),
                              centre[1] + radius * np.sin(theta)])
    return points, theta


def tendril_spines(rng, coil, theta, params, size):
    """Each tendril's centre line and its full width (mm), as a list of (points, width).

    The random numbers are drawn for MAX_TENDRILS tendrils of the longest possible walk, always
    in this order: four numbers per tendril (where it sprouts, its angle, length and width), then
    the walk's noise. Only the first `tendrils` tendrils and the steps each one needs are used,
    so the rng is used the same way for any setting: adding a tendril leaves the others as they
    were, and lengthening one extends it along the path it was already taking.
    """
    sprout, turn, stretch, thickness = rng.random((MAX_TENDRILS, 4)).T
    noise = rng.uniform(-1, 1, (MAX_TENDRILS, MAX_STEPS))
    low, high = LENGTH_RANGE
    spines = []
    for k in range(params["tendrils"]):
        # Where on the coil it sprouts, and the coil's direction there.
        at = theta[-1] * (SPROUT_FROM + (1 - SPROUT_FROM) * sprout[k])
        start = np.interp(at, theta, coil[:, 0]), np.interp(at, theta, coil[:, 1])
        heading = spiral_tangent_angle(at)
        heading += params["fan"] * (2 * turn[k] - 1)

        steps = int(params["length"] * (low + (high - low) * stretch[k]) / WALK_STEP)
        bends = params["curl"] * moving_average(noise[k], params["smoothness"])[:steps]
        spine = random_walk(start, heading, bends, WALK_STEP * size)
        width = params["tube_width"] * size * (1 + params["width_variation"] * (2 * thickness[k] - 1))
        spines.append((spine, width))
    return spines


def spiral_tangent_angle(theta):
    """Direction of travel along r = spacing · θ / 2π at angle θ (towards larger θ).

    The velocity is (dr/dθ · cos θ - r · sin θ, dr/dθ · sin θ + r · cos θ). With dr/dθ = spacing
    / 2π and r = θ · dr/dθ, the common factor dr/dθ drops out of the direction, leaving
    (cos θ - θ sin θ, sin θ + θ cos θ): the direction does not depend on the spacing.
    """
    return math.atan2(math.sin(theta) + theta * math.cos(theta),
                      math.cos(theta) - theta * math.sin(theta))


def moving_average(values, half_window):
    """Each value replaced by the mean of itself and up to `half_window` neighbours on each side.

    Near the ends fewer neighbours exist, and the mean is taken over those there are. A running
    total makes every window's sum one subtraction.
    """
    total = np.concatenate([[0.0], np.cumsum(values)])
    i = np.arange(len(values))
    lo = np.maximum(0, i - half_window)
    hi = np.minimum(len(values), i + half_window + 1)
    return (total[hi] - total[lo]) / (hi - lo)


def random_walk(start, heading, bends, step):
    """Points of a walk from `start`: before step k the heading turns by bends[k], then moves `step`."""
    headings = heading + np.cumsum(bends)
    moves = step * np.column_stack([np.cos(headings), np.sin(headings)])
    return np.vstack([start, start + np.cumsum(moves, axis=0)])


def taper(progress):
    """Width factor along a spine: rises from 0 to 1 over the first TAPER, falls over the last.

    `progress` runs from 0 at the spine's start to 1 at its end. The factor never drops below
    THINNEST, so the very tips keep a short rib.
    """
    rise = np.minimum(progress, 1 - progress) / TAPER
    return np.clip(rise, THINNEST, 1.0)


def ribbed_tube(spine, half_widths, gap) -> list[Stroke]:
    """Ribs across a tube: one straight line every `gap` mm along the spine, perpendicular to it.

    `half_widths` gives the tube's half-width at each spine point. A rib at arc length s sits at
    the spine point there, points along the spine's normal there, and reaches half_width(s) to
    either side. Positions, directions and widths between spine points are interpolated.
    """
    step = np.hypot(*np.diff(spine, axis=0).T)
    along = np.concatenate([[0.0], np.cumsum(step)])
    stations = np.arange(gap, along[-1], gap)
    if len(stations) == 0:
        return []

    # Direction of the spine at each point (from its two neighbours), then at each rib.
    direction = np.gradient(spine, axis=0)
    tx = np.interp(stations, along, direction[:, 0])
    ty = np.interp(stations, along, direction[:, 1])
    norm = np.hypot(tx, ty)
    normal = np.column_stack([-ty, tx]) / norm[:, None]

    centre = np.column_stack([np.interp(stations, along, spine[:, 0]),
                              np.interp(stations, along, spine[:, 1])])
    reach = np.interp(stations, along, half_widths)[:, None] * normal
    return [Stroke(np.array([a, b])) for a, b in zip(centre + reach, centre - reach)]
