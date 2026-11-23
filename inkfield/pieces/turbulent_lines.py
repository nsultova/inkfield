"""Turbulent lines: ruled lines that fray into smoke near one corner and settle into calm further away.

The picture
-----------
A page of horizontal lines, like ruled paper. Far from one corner they are perfectly straight
and single. Closer to that corner each line comes apart into a bundle of strands that swell and
cross, like smoke rising from a still surface. The change from chaos to calm is gradual.

The model
---------
Positions are measured in frame units: xn = 0 at the left edge of the frame, 1 at the right;
yn = 0 at the top, 1 at the bottom.

* **Chaos.** One number between 0 and 1 says how turbulent the page is at (xn, yn). With
  (ox, oy) the chaos origin, d the distance to it in frame units and R the reach,

      chaos(xn, yn) = (1 - min(1, d / R)) ** FALLOFF

  so it is 1 at the origin, falls off smoothly and is exactly 0 from distance R on. Everything
  below is multiplied by it, which is why the far lines come out ruler-straight.
* **Line heights.** The lines sit at evenly spaced heights, leaving a small gap (EDGE_GAP) at the
  top and bottom of the frame.
* **The master curve.** Each line gets a few control points ("bumps") spread evenly across the
  frame. Control point k gets a height offset u_k · A · chaos(k / (n - 1), yn), with u_k
  uniform in [-1, 1] and A the amplitude. The offsets are smoothed twice: each one is moved
  towards the average of its two neighbours,

      p_k  <-  (1 - s) · p_k + s · (p_{k-1} + p_{k+1}) / 2         (s = smoothing)

* **The strands.** A line near the origin is drawn as a bundle of strands. Their number is
  round(strands · chaos) with chaos read a quarter of the frame's width from the origin, towards
  the middle (at least 1). Each strand takes the master's control points, adds its own offsets
  u · A · spread · chaos, and is smoothed once more. Then:
  - it is turned into a smooth curve through its control points (Catmull–Rom: the curve
    passes through every control point, and its slope there is set by the two neighbours);
  - a small wiggle is added on top, a sum of sines,

        w(x) = sin(f x + φ) + 0.45 sin(1.9 f x + φ + 2.7) + ...

    with a random phase φ per strand and a frequency f that triples where chaos is 1, scaled by
    0.08 · A · chaos.
* **Folding** (off by default). For an organic, folded look the strands are also lifted by a
  smooth random field read at a warped position (domain warping). With w = folding · chaos,

      q  = p + w · FOLD_SHIFT · G(p)          dy = w · FOLD_HEIGHT · F(q)

  where F and G are smooth random fields (see `inkfield.core.noise`). Pushing the place where F
  is read by another field G is what bends the ripples into folds.

Every length is measured against the frame's reference length (half its shorter side), so a
square, an A4 sheet and an A3 landscape sheet all get the same look.

The controls
------------
Lines               how many horizontal lines.
Bumps per line      control points across the frame: few gives long swells, many gives tight ones.
Strands             the largest number of strands in one bundle, reached right at the origin.
Amplitude           how far a line may swing, as a fraction of the frame's reference length.
Strand spread       how far the strands stray from their line's master curve, relative to the
                    amplitude: low keeps a tight braid, high a loose fan.
Smoothing           0 keeps every bump sharp, 1 rounds them off.
Chaos across        where the chaos comes from: 0 = left edge, 1 = right edge.
Chaos down          the same downward: 0 = top edge, 1 = bottom edge.
Chaos reach         how far the turbulence spreads from its origin, in frame widths/heights.
Folding             strength of the domain-warped folding; 0 leaves it off.
"""
import math

import numpy as np

from inkfield.core.controls import Slider
from inkfield.core.noise import SmoothField
from inkfield.core.piece import Meta
from inkfield.core.stroke import Stroke

META = Meta(
    slug="turbulent-lines",
    title="Turbulent lines",
    subtitle="Smoke settling into ruled lines",
    framed_shape="rect",
    seed=3,
    info=("Horizontal lines that fray into bundles of strands near one corner. A chaos value, "
          "1 at the origin and falling to 0 at a chosen reach, scales every random offset, so "
          "lines far away stay straight. Each line is a smooth curve through randomly lifted "
          "control points; near the origin it splits into strands that each add their own "
          "offsets and a small wiggle."),
)

PARAMS = [
    Slider("lines",     "Lines",          10,   80,  1,    45),
    Slider("bumps",     "Bumps per line", 3,    60,  1,    25),
    Slider("strands",   "Strands",        1,    25,  1,    14),
    Slider("amplitude", "Amplitude",      0.01, 0.25, 0.005, 0.12),
    Slider("spread",    "Strand spread",  0.05, 1,   0.05, 0.35),
    Slider("smoothing", "Smoothing",      0,    1,   0.05, 0.5),
    Slider("origin_x",  "Chaos across",   0,    1,   0.05, 0),
    Slider("origin_y",  "Chaos down",     0,    1,   0.05, 0),
    Slider("reach",     "Chaos reach",    0.2,  2,   0.05, 0.85),
    Slider("folding",   "Folding",        0,    1,   0.01, 0),
]

FALLOFF = 2.2               # chaos falloff sharpness: higher keeps the turbulence closer to its origin
TOP_BIAS = 0.0              # > 0 packs the lines closer together towards the top
EDGE_GAP = 0.04             # empty band above the first and below the last line, in frame heights
COUNT_OFFSET = 0.25         # strand count is read this many frame widths from the origin
RESOLUTION = 350            # points per line on a square frame (more on a wider one)
RIPPLES = 3.2               # strand wiggle: waves across a square frame (prototype 0.10 rad/mm on 200 mm)
WIGGLE_LAYERS = 2           # sines summed in a strand's wiggle
WIGGLE_SIZE = 0.08          # strand wiggle height, in amplitudes
SUB_STRANDS = 0             # sub-strands per strand at full chaos (0 = off)
SUB_SPREAD = 0.20           # how far sub-strands stray from their strand, in amplitudes
SUB_DECAY = 0.6             # extra damping of the sub-strands' spread
SUB_RIPPLES = 4.8           # sub-strand wiggle: waves across a square frame (prototype 0.15 rad/mm)
SUB_WIGGLE_LAYERS = 3       # sines summed in a sub-strand's wiggle
SUB_WIGGLE_SIZE = 0.06      # sub-strand wiggle height, in amplitudes
FOLD_SIZE = 1.33            # ripple size of the folding fields, in reference lengths
FOLD_LAYERS = 3             # octaves of the folding fields
FOLD_SHIFT = 3.0            # largest warp of the place F is read, in reference lengths
FOLD_HEIGHT = 0.045         # largest lift from folding, in reference lengths


def generate(params, frame, rng) -> list[Stroke]:
    x0, y0, x1, y1 = frame.bbox
    width, height = x1 - x0, y1 - y0
    amplitude = params["amplitude"] * frame.scale
    origin = (params["origin_x"], params["origin_y"], params["reach"])

    # 1. The folding fields, drawn first so that the strands do not depend on the folding slider.
    fold = folding(frame, rng, params["folding"])

    # 2. Where along a line the points go: evenly across the frame, x measured from its left edge.
    samples = math.ceil(RESOLUTION * width / (2 * frame.scale)) + 1
    xn = np.linspace(0, 1, samples)
    x = x0 + xn * width

    strokes = []
    for y_base in line_heights(frame, params["lines"]):
        yn = (y_base - y0) / height
        # 3. This line's bundle: one height offset per strand and point.
        offsets = bundle(rng, params, amplitude, frame.scale, xn, xn * width, yn, origin)
        # 4. Fold where the chaos is, and hand the strands over.
        along = chaos(xn, yn, *origin)
        for offset in offsets:
            y = fold(x, y_base + offset, along)
            strokes.append(Stroke(np.column_stack([x, y])))
    return strokes


def chaos(xn, yn, origin_x, origin_y, reach):
    """How turbulent the page is at (xn, yn): 1 at the origin, falling to exactly 0 at `reach`."""
    distance = np.hypot(np.asarray(xn) - origin_x, yn - origin_y)
    closeness = 1 - np.minimum(1, distance / max(reach, 0.01))
    return closeness ** FALLOFF


def line_heights(frame, count) -> np.ndarray:
    """The base height of every line, evenly spaced (or packed towards the top by TOP_BIAS)."""
    _, y0, _, y1 = frame.bbox
    t = np.linspace(0, 1, count)
    if TOP_BIAS > 0:
        t = np.expm1(TOP_BIAS * t) / math.expm1(TOP_BIAS)
    gap = EDGE_GAP * (y1 - y0)
    return y0 + gap + t * (y1 - y0 - 2 * gap)


def bundle(rng, params, amplitude, scale, xn, x_mm, yn, origin):
    """Height offsets for every strand of one line, as an array (strands, points).

    Draws from rng in this order: the master's control points, then for the strands their phases
    and control offsets, then the same for the sub-strands.
    """
    n_ctrl = params["bumps"]
    smoothing = params["smoothing"]
    ctrl_chaos = chaos(np.linspace(0, 1, n_ctrl), yn, *origin)
    point_chaos = chaos(xn, yn, *origin)

    # The master curve's control points, smoothed twice.
    master = rng.uniform(-1, 1, n_ctrl) * amplitude * ctrl_chaos
    master = smooth(smooth(master, smoothing), smoothing)

    # How many strands, from the chaos a little way from the origin towards the middle.
    origin_x = origin[0]
    count_x = origin_x + COUNT_OFFSET if origin_x < 0.5 else origin_x - COUNT_OFFSET
    count_chaos = float(chaos(count_x, yn, *origin))
    n_strands = max(1, round(params["strands"] * count_chaos))

    phases = rng.uniform(0, 2 * math.pi, n_strands)
    spread = amplitude * params["spread"] * ctrl_chaos
    strand_ctrl = smooth(master + rng.uniform(-1, 1, (n_strands, n_ctrl)) * spread, smoothing)
    strands = (through_points(strand_ctrl, len(xn))
               + wiggle(x_mm, RIPPLES, WIGGLE_LAYERS, phases, point_chaos, scale)
               * WIGGLE_SIZE * amplitude * point_chaos)

    # Sub-strands: the same step once more, starting from each strand's control points.
    n_sub = round(SUB_STRANDS * count_chaos)
    if n_sub == 0:
        return strands
    parent = np.repeat(strand_ctrl, n_sub, axis=0)
    phases = rng.uniform(0, 2 * math.pi, len(parent))
    spread = amplitude * SUB_SPREAD * SUB_DECAY * ctrl_chaos
    sub_ctrl = smooth(parent + rng.uniform(-1, 1, parent.shape) * spread, smoothing)
    subs = (through_points(sub_ctrl, len(xn))
            + wiggle(x_mm, SUB_RIPPLES, SUB_WIGGLE_LAYERS, phases, point_chaos, scale)
            * SUB_WIGGLE_SIZE * amplitude * point_chaos)
    return np.vstack([strands, subs])


def smooth(values, s):
    """Move each value towards the mean of its two neighbours, by s (the end values count twice).

    Works along the last axis, so a whole set of strands is smoothed at once.
    """
    padded = np.concatenate([values[..., :1], values, values[..., -1:]], axis=-1)
    neighbours = (padded[..., :-2] + padded[..., 2:]) / 2
    return (1 - s) * values + s * neighbours


def through_points(ctrl, samples):
    """A Catmull–Rom curve through evenly spaced control points, sampled at `samples` points.

    Between control points 1 and 2 of four neighbours y0, y1, y2, y3, at fraction t:

        y(t) = ½ (2 y1 + (y2 − y0) t + (2 y0 − 5 y1 + 4 y2 − y3) t² + (3 y1 − y0 − 3 y2 + y3) t³)

    At the ends the missing neighbour is replaced by the end point itself.
    """
    n = ctrl.shape[-1]
    position = np.linspace(0, n - 1, samples)
    i = np.minimum(position.astype(int), n - 2)
    t = position - i
    y0, y1 = ctrl[..., np.maximum(i - 1, 0)], ctrl[..., i]
    y2, y3 = ctrl[..., i + 1], ctrl[..., np.minimum(i + 2, n - 1)]
    return 0.5 * (2 * y1 + (y2 - y0) * t + (2 * y0 - 5 * y1 + 4 * y2 - y3) * t**2
                  + (3 * y1 - y0 - 3 * y2 + y3) * t**3)


def wiggle(x_mm, ripples, layers, phases, point_chaos, scale):
    """A sum of sines along the line, one row per phase, each between about −1.8 and 1.8.

    The base frequency gives `ripples` waves across a square frame (2 reference lengths) and
    triples where the chaos is 1. Each further layer is 1.9 times as fast, 0.45 times as strong
    and shifted by 2.7 radians.
    """
    frequency = 2 * math.pi * ripples / (2 * scale) * (1 + 2 * point_chaos)
    phase = phases[:, None]
    total, strength = 0.0, 1.0
    for _ in range(layers):
        total = total + strength * np.sin(frequency * x_mm + phase)
        frequency, strength, phase = frequency * 1.9, strength * 0.45, phase + 2.7
    return total


def folding(frame, rng, amount):
    """fold(x, y, chaos) -> y: lift points by a smooth field read at a warped place.

    With w = amount · chaos, q = p + w · FOLD_SHIFT · G(p) and the lift is w · FOLD_HEIGHT · F(q),
    both lengths in reference lengths. Where w is 0 the points are left exactly as they were.
    """
    size = FOLD_SIZE * frame.scale
    lift = SmoothField(rng, wavelength=size, octaves=FOLD_LAYERS)
    warp = SmoothField(rng, wavelength=size, octaves=FOLD_LAYERS)

    def fold(x, y, along):
        if amount == 0:
            return y
        w = amount * along
        gx, gy = warp(x, y)
        shift = w * FOLD_SHIFT * frame.scale
        f, _ = lift(x + shift * gx, y + shift * gy)
        return y + w * FOLD_HEIGHT * frame.scale * f

    return fold
