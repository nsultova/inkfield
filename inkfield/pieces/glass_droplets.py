"""Glass droplets: a rain-covered window, every drop drawn as a set of concentric rings.

What a wet window shows
-----------------------
After rain, a window pane is covered in two kinds of drops. Most are small beads that stay where
they landed: surface tension holds them to the glass. A few have grown heavy enough to slide.
A sliding drop does not glide smoothly. The glass holds on to its edge until enough weight builds
up, then lets go, so the drop moves in small lurches ("stick-slip"), and tiny bumps in the glass
nudge it sideways. It stretches into a teardrop with its tail behind it, leaves a clean track
above, and the thin film it leaves behind breaks up into a line of tiny beads. Here and there a
small satellite drop sits beside the track.

The pane
--------
Everything is worked out on a "pane" whose shorter half-side is 105 units long, the half-width of
the A4 page the prototype was drawn on (1 unit = 1 mm there). The pane has the frame's shape,
and at the end every point is scaled by unit = frame.scale / 105 and placed on the frame. So the
picture keeps its proportions on any page, and the numbers below are the prototype's own.
x grows to the right and y downward, so "down the glass" is +y.

The rings
---------
A drop of radius r at centre c is drawn as `rings` closed lines, ring k (k = 1 … rings) of radius

    r_k = r · k / rings

A ring is traced by the angle θ from 0 to 2π, in a frame turned to the drop's direction of
motion: u = cos θ runs across the motion, v = sin θ along it (v > 0 ahead, v < 0 behind).

    radius      ρ(θ) = r_k + warp · 0.25 · r_k · Σ sin(f θ + φ_f),   f = 2, 3, 5
    behind      v' = v · (1 + |v| · (e − 1))        (v < 0: the tail is stretched e times)
    ahead       v' = v · (1 − 0.05 v)               (v ≥ 0: the front is pressed 5 % flatter)
    point       c + ρ u · across + ρ v' · along

The phases φ_f are random for every ring. A drop at rest "moves" straight down with e = 1, so a
resting bead is round on top and slightly flattened below. A sliding drop's stretch comes from its
speed s (pane units per step) and how runny it is:

    e = 1 + s · max(0, 1.5 − 1.2 · viscosity)

The slide
---------
A sliding drop is followed step by step (Euler steps of dt = 0.5) with velocity (vx, vy):

    with chance 0.04 · stick_slip:  v ← 0.05 v          (the glass catches the drop)
    vy ← vy + g dt,                  g = 0.08 · size / 5   (gravity: heavier drops pull harder)
    vx ← vx + N(0, 0.10 · roughness) dt                    (bumps in the glass)
    vy ← vy + N(0, 0.015 · roughness) dt
    v  ← v · (0.85 + 0.12 · viscosity)                     (drag: syrup slows more than water)
    |v| is capped at 1.5 · (1 − 0.6 · viscosity)
    position ← position + v dt

It stops after 5 · trail steps, or at the bottom 3 % of the pane. Its path is smoothed (each inner
point moved to ¼ previous + ½ itself + ¼ next, four times) and drawn as the track; the drop's
rings sit at the end of it, turned to the direction of the last five steps.

Drop sizes
----------
Resting beads: r is exponential with mean size / 2.5, kept between 0.3 and 0.6 · size.
Sliding drops: r = exp(N(0.4, 0.45)) · size / 5, kept between 1 and size.

The controls
------------
Drops              how many drops on the pane. Adding one leaves the others as they were.
Sliding share      the chance that a drop slides rather than rests.
Drop size          the prototype's "heaviness": larger drops, and sliding drops fall faster.
Trail length       how long a sliding drop is followed (5 · trail steps), so roughly the length
                   of its track in pane units, unless it reaches the bottom first.
Viscosity          0 is water (fast, long tails), 1 is syrup (slow, round).
Surface roughness  how much the bumps in the glass push a sliding drop sideways.
Stick-slip         how often the glass catches a sliding drop: a jerkier track.
Rings per drop     how many concentric rings draw each drop.
Ring warp          0 gives smooth ovals; higher values make lumpy, organic rings.
Trail beads        how many tiny beads a sliding drop leaves along its track.

How the lines are drawn
-----------------------
1. Measure the frame in pane units.
2. Give every drop its own random stream, so the drops do not depend on each other.
3. For each drop: decide whether it slides, choose its size and starting place, and draw it:
   a resting bead is just its rings; a sliding drop is its track, the beads along the track, its
   rings at the end of the track, and its satellites.
4. Scale every line from the pane onto the frame.
"""
import math

import numpy as np

from inkfield.core.controls import Slider
from inkfield.core.piece import Meta
from inkfield.core.stroke import Stroke

META = Meta(
    slug="glass-droplets",
    title="Glass droplets",
    subtitle="Rain on a window",
    framed_shape="rect",
    seed=3,
    info=("A window pane after rain. Most drops rest where they landed, drawn as concentric rings. "
          "Heavier ones slide down in stick-slip lurches, stretched into teardrops, leaving a track "
          "with a line of tiny beads behind them and a satellite drop or two beside it."),
)

PARAMS = [
    Slider("drops",      "Drops",             1,  80,  1,    50),
    Slider("sliding",    "Sliding share",     0,  1,   0.01, 0.25),
    Slider("size",       "Drop size",         1,  30,  0.5,  8),
    Slider("trail",      "Trail length",      10, 200, 5,    60),
    Slider("viscosity",  "Viscosity",         0,  1,   0.01, 0.30),
    Slider("roughness",  "Surface roughness", 0,  1,   0.01, 0.15),
    Slider("stick_slip", "Stick-slip",        0,  1,   0.01, 0.25),
    Slider("rings",      "Rings per drop",    1,  10,  1,    6),
    Slider("warp",       "Ring warp",         0,  2,   0.05, 0),
    Slider("beads",      "Trail beads",       0,  16,  1,    12),
]
# The prototype allowed up to 150 drops, 20 rings and 60 beads. These maxima keep the heaviest
# drawing (every drop sliding) near 3000 strokes, which renders in under 3 s.

MAX_DROPS = next(int(control.max) for control in PARAMS if control.name == "drops")
PANE_SCALE = 105.0          # the pane's shorter half-side, in pane units (the prototype's A4 half-width)
DT = 0.5                    # time step of the slide
STEPS_PER_TRAIL = 5         # a slide lasts at most STEPS_PER_TRAIL · trail steps
BOTTOM = 0.97               # a sliding drop stops at this fraction of the pane's height
SMOOTHING = 4               # passes of ¼ ½ ¼ smoothing over a slide's path
WARP_FREQUENCIES = (2, 3, 5)        # bumps per ring for the ring warp
DISTORTION = 0.0                    # fine ripple on top of the warp (0 = off), in ring radii / 10
DISTORTION_FREQUENCIES = (6, 9, 13) # ripples per ring for the distortion
FRONT_FLATTENING = 0.05     # how much flatter a drop's leading side is
BEAD_RINGS = 1              # rings per trail bead
BEAD_SCATTER = 1.2          # sideways spread of trail beads, in parent radii · 0.8
BEAD_RANDOMNESS = 0.30      # 0 = beads evenly spaced along the track, 1 = fully random
BEAD_SIZE = 0.65            # trail bead size, relative to the parent drop
SATELLITE_DEPTH = 1         # generations of satellite drops beside a track (0 = none)


def generate(params, frame, rng) -> list[Stroke]:
    # 1. The frame in pane units.
    x0, y0, x1, y1 = frame.bbox
    unit = frame.scale / PANE_SCALE
    pane = ((x1 - x0) / unit, (y1 - y0) / unit)

    # 2. One random stream per drop. They are split off for MAX_DROPS drops whatever the count,
    #    so adding a drop leaves the others as they were.
    drop_streams = rng.spawn(MAX_DROPS)[:params["drops"]]

    strokes = []
    for drop_rng in drop_streams:
        # 3. The drop's lines on the pane ...
        for line in one_drop(drop_rng, pane, params):
            # 4. ... scaled onto the frame.
            strokes.append(Stroke(np.column_stack([x0 + line[:, 0] * unit, y0 + line[:, 1] * unit])))
    return strokes


def one_drop(rng, pane, params) -> list[np.ndarray]:
    """All lines of one drop, on the pane. The random numbers are drawn in a fixed order."""
    width, height = pane
    size = params["size"]
    if rng.random() >= params["sliding"]:
        radius = min(max(rng.exponential(size / 2.5), 0.3), 0.6 * size)
        x = rng.uniform(0.03 * width, 0.97 * width)
        y = rng.uniform(0.03 * height, 0.97 * height)
        return drop_rings(rng, x, y, radius, math.pi / 2, 0.0, params["rings"], params["warp"],
                          params["viscosity"])

    radius = min(max(math.exp(rng.normal(0.4, 0.45)) * size / 5, 1.0), size)
    x = rng.uniform(0.05 * width, 0.95 * width)
    y = rng.uniform(0.03 * height, 0.55 * height)
    return sliding_drop(rng, x, y, radius, pane, params)


def sliding_drop(rng, x, y, radius, pane, params) -> list[np.ndarray]:
    """The track, the beads along it, the drop's rings at its end, and the satellites."""
    path = slide_down(rng, x, y, pane, params["trail"], params["size"], params["viscosity"],
                      params["roughness"], params["stick_slip"])
    if len(path) < 4:
        return []
    path = smooth(path, SMOOTHING)
    track = path[:-2] if len(path) > 4 else path

    lines = [track]
    lines += trail_beads(rng, track, radius, params["beads"], params["warp"], params["viscosity"])

    look_back = min(5, len(path) - 1)
    dx, dy = path[-1] - path[-1 - look_back]
    angle = math.atan2(dy, dx)
    speed = math.hypot(dx, dy) / look_back
    lines += drop_rings(rng, *path[-1], radius, angle, speed, params["rings"], params["warp"],
                        params["viscosity"])

    lines += satellites(rng, track, radius, SATELLITE_DEPTH, params)
    return lines


def slide_down(rng, x, y, pane, trail, size, viscosity, roughness, stick_slip) -> np.ndarray:
    """The path of a drop sliding down the glass from (x, y), as an (N, 2) array (see docstring)."""
    width, height = pane
    steps = int(trail * STEPS_PER_TRAIL)
    catch = rng.random(steps)                  # all random numbers first, in a fixed order
    bumps = rng.normal(size=(steps, 2)).tolist()
    gravity = 0.08 * size / 5
    drag = 0.85 + 0.12 * viscosity
    top_speed = 1.5 * (1 - 0.6 * viscosity)

    vx, vy = 0.0, 0.05
    path = [(x, y)]
    for step in range(steps):
        if catch[step] < 0.04 * stick_slip:     # the glass catches the drop
            vx, vy = 0.05 * vx, 0.05 * vy
        vy += gravity * DT
        vx += bumps[step][0] * 0.10 * roughness * DT
        vy += bumps[step][1] * 0.015 * roughness * DT
        vx, vy = vx * drag, vy * drag
        speed = math.hypot(vx, vy)
        if speed > top_speed:
            vx, vy = vx / speed * top_speed, vy / speed * top_speed
        x, y = x + vx * DT, y + vy * DT
        if y > BOTTOM * height or x < -0.1 * width or x > 1.1 * width:
            break
        path.append((x, y))
    return np.array(path)


def smooth(path, passes) -> np.ndarray:
    """Move each inner point to ¼ previous + ½ itself + ¼ next, `passes` times; ends stay put."""
    path = path.copy()
    for _ in range(passes):
        path[1:-1] = 0.25 * path[:-2] + 0.5 * path[1:-1] + 0.25 * path[2:]
    return path


def drop_rings(rng, cx, cy, radius, angle, speed, count, warp, viscosity) -> list[np.ndarray]:
    """`count` concentric closed rings of a drop moving in direction `angle` (see docstring)."""
    stretch = 1 + speed * max(0.0, 1.5 - 1.2 * viscosity)
    along = np.array([math.cos(angle), math.sin(angle)])
    across = np.array([-math.sin(angle), math.cos(angle)])
    phases = rng.uniform(0, 2 * math.pi, (count, len(WARP_FREQUENCIES) + len(DISTORTION_FREQUENCIES)))

    rings = []
    for k in range(1, count + 1):
        t = k / count
        ring_radius = radius * t
        steps = max(24, int(72 * t))                             # more points on the outer rings
        theta = 2 * math.pi * np.arange(steps) / steps
        warp_phases, distortion_phases = np.split(phases[k - 1], [len(WARP_FREQUENCIES)])
        rho = (ring_radius
               + warp * 0.25 * ring_radius * bumps(theta, WARP_FREQUENCIES, warp_phases)
               + DISTORTION * 0.10 * ring_radius * bumps(theta, DISTORTION_FREQUENCIES, distortion_phases))
        u, v = np.cos(theta), np.sin(theta)
        v = np.where(v < 0, v * (1 + np.abs(v) * (stretch - 1)), v * (1 - FRONT_FLATTENING * v))
        points = np.array([cx, cy]) + (rho * u)[:, None] * across + (rho * v)[:, None] * along
        rings.append(np.vstack([points, points[:1]]))           # close the ring
    return rings


def bumps(theta, frequencies, phases) -> np.ndarray:
    """Σ sin(f θ + φ) over the given frequencies: a smooth wobble around the ring."""
    return sum(np.sin(f * theta + phase) for f, phase in zip(frequencies, phases))


def sideways(track, index) -> np.ndarray:
    """The unit vector across the track at point `index` (to the right of its direction)."""
    if index + 1 >= len(track):
        return np.array([1.0, 0.0])
    dx, dy = track[index + 1] - track[index]
    length = math.hypot(dx, dy) or 1.0
    return np.array([-dy, dx]) / length


def trail_beads(rng, track, radius, count, warp, viscosity) -> list[np.ndarray]:
    """Tiny beads left along the track, from evenly spaced (BEAD_RANDOMNESS 0) to random (1)."""
    lines = []
    for i in range(count):
        even = (i + 0.5) / count
        t = min(max(even * (1 - BEAD_RANDOMNESS) + rng.random() * BEAD_RANDOMNESS, 0.0), 0.999)
        index = int(t * (len(track) - 1))
        offset = rng.normal(0, BEAD_SCATTER * radius * 0.8)
        cx, cy = track[index] + sideways(track, index) * offset
        bead_radius = max(0.15, radius * BEAD_SIZE * rng.uniform(0.10, 0.30))
        lines += drop_rings(rng, cx, cy, bead_radius, math.pi / 2, 0.0, BEAD_RINGS, warp, viscosity)
    return lines


def satellites(rng, track, parent_radius, depth, params) -> list[np.ndarray]:
    """One or a few small resting drops beside the track; deeper generations sit beside those."""
    if depth <= 0 or len(track) == 0:
        return []
    lines = []
    for _ in range(rng.integers(1, SATELLITE_DEPTH + 2)):
        index = rng.integers(0, max(0, len(track) - 3) + 1)
        radius = parent_radius * rng.uniform(0.15, 0.45) / depth
        if radius < 0.2:
            continue
        side = 1 if rng.random() > 0.5 else -1
        distance = parent_radius * rng.uniform(0.8, 2.5)
        cx, cy = (track[index] + sideways(track, index) * distance * side
                  + [rng.normal(0, 0.3 * radius), rng.normal(0, 0.2 * radius)])
        count = max(2, params["rings"] - (SATELLITE_DEPTH - depth + 1))
        lines += drop_rings(rng, cx, cy, radius, math.pi / 2, 0.0, count, params["warp"],
                            params["viscosity"])
        if depth > 1 and rng.random() < 0.4:
            lines += satellites(rng, np.array([[cx, cy]]), radius, depth - 1, params)
    return lines
