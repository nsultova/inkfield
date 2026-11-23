"""Water droplets: ripples spreading on a puddle where a few drops have just fallen.

What the picture shows
----------------------
A puddle seen a little from the side. A handful of drops have landed in it. Around each impact
there is a tight knot of small circles where the drop went in, a set of wavy rings spreading out
from it, and a few tiny splash drops thrown out to the side, each with its own little rings.
Where the ripples of two drops overlap, each one bends the other's rings. A wobbly outline or two
marks the edge of the puddle.

The model
---------
This is drawing, not fluid physics. Every ring is a closed curve around a centre c, written in
polar form: a radius r(θ) for each direction θ from 0 to 2π.

* The drops. Each drop sits at a random place in the middle 70 % of the frame and has an age a,
  uniform between 0.4 and 1. A young drop has made fewer rings: it has

      n = max(2, int(rings · a))

  ripple rings. With clustering above 0 the drops are instead scattered around the frame's
  centre like a bell curve whose width shrinks to 30 % at full clustering.
* The gap. All ripple sizes are measured in one length, the first ring gap

      s = spacing · L

  where L is the frame's reference length (half its shorter side). So the same settings give
  the same picture on any paper.
* Ripple ring k (k = 0, 1, ..., n − 1) starts as a circle of radius

      r_k = s · g^k

  with g the ring spread: g = 1 gives evenly spaced rings, larger g lets the outer rings drift
  apart, as real ripples do.
* Wobble. Three sine waves, with 3, 7 and 13 bumps around the ring and a random start φ_f per
  drop, make the ring uneven. They grow a little with every ring:

      wobble_k(θ) = (w · s · (1 + 0.05 · k) / 3) · Σ_f sin(f · θ + φ_f),    f = 3, 7, 13

* Interference. Each other drop d sends out waves of wavelength λ = 2.4 · s. At the point p of
  the plain circle in direction θ, every other drop pushes the ring in or out by

      interference_k(θ) = i · s · Σ_d cos(2π · |p − d| / λ)

  so where two ripple systems overlap the rings take on the other's rhythm. With more than three
  other drops the sum is scaled by 3 / (number of other drops): the push never grows past what
  three drops' waves could do, so a crowded puddle is not shaken harder than a quiet one.
* The ring is then r(θ) = r_k + wobble_k(θ) + interference_k(θ), kept at least 0.2 · r_k so a
  strong push flattens the ring instead of folding it through its centre, and placed at
  c + r(θ) · (cos θ, sin θ).
* The oblique view. Seen from the side, a circle on the water looks like an ellipse. Every
  ripple ring is squeezed by the factor `squash` along an axis tilted 0.15 radians (about 9°)
  from the horizontal: turn the ring by −0.15, multiply its x by squash, turn it back.
* The impact. Three small circles of radius j · 0.22 · s (j = 1, 2, 3) at the centre.
* Splashes. A few tiny drops are thrown out: each lands at a random direction and at a random
  distance between 0.7 · s and 4.8 · s, and has three circles of radius j · 0.225 · s.
* The puddle edge. One or more ellipses around the frame's centre, with half-axes 0.88 of the
  frame's half-width and half-height, each next one 4 % smaller, wobbling by 0.019 · L with
  five bumps around: x = c_x + (0.88 · W · (1 − 0.04 · m) + wobble(θ)) · cos θ, and likewise y.

The controls
------------
Drops           how many drops hit the water. Adding one leaves the others as they were.
Rings per drop  the most ripple rings a drop can have; younger drops have fewer.
Ring spacing    the first ring gap s, as a fraction of the frame's reference length.
Ring spread     g, how much each ring's radius grows over the one inside it (1 = even gaps).
Wobble          w, how uneven the rings are, in ring gaps.
Interference    i, how far each other drop's waves push a ring in or out, in ring gaps
                (with more than three other drops, their sum is scaled down to three drops' worth).
Squash          the oblique view: 1 = seen from straight above, smaller = from lower down.
Clustering      0 = drops spread evenly over the middle of the frame, 1 = bunched near its centre.
Splashes        how many tiny splash drops each drop throws out.
Puddle edge     how many outlines mark the edge of the puddle (0 = none).

How the lines are drawn
-----------------------
1. Draw all random numbers in a fixed order: the puddle's wobble start, then everything for
   every possible drop (place, age, wobble starts, splashes).
2. Draw the puddle edge.
3. For each drop: its ripple rings from the inside out, then the impact circles, then the
   splashes.
"""
import math
from dataclasses import dataclass

import numpy as np

from inkfield.core.controls import Slider
from inkfield.core.piece import Meta
from inkfield.core.stroke import Stroke

META = Meta(
    slug="water-droplets",
    title="Water droplets",
    subtitle="Ripples on a puddle",
    framed_shape="rect",
    seed=15,
    info=("Each drop sends out wavy rings whose radii grow by a fixed factor, r_k = s · g^k. "
          "Three sine waves make each ring uneven, and every other drop's waves push it in and "
          "out, so overlapping ripples bend each other. The rings are squashed into ellipses as "
          "if the puddle were seen from the side. Small circles mark the impact, tiny splash "
          "drops land nearby, and a wobbly outline marks the puddle's edge."),
)

PARAMS = [
    Slider("drops",        "Drops",          1,    24,   1,     4),
    Slider("rings",        "Rings per drop", 2,    24,   1,     11),
    Slider("spacing",      "Ring spacing",   0.02, 0.12, 0.005, 0.05),
    Slider("growth",       "Ring spread",    1,    1.2,  0.01,  1.11),
    Slider("wobble",       "Wobble",         0,    1,    0.01,  0.35),
    Slider("interference", "Interference",   0,    0.5,  0.01,  0.16),
    Slider("squash",       "Squash",         0.5,  1,    0.01,  0.85),
    Slider("clustering",   "Clustering",     0,    1,    0.01,  0),
    Slider("splashes",     "Splashes",       0,    12,   1,     5),
    Slider("puddle",       "Puddle edge",    0,    4,    1,     2),
]

MAX_DROPS = next(int(control.max) for control in PARAMS if control.name == "drops")
MAX_SPLASHES = next(int(control.max) for control in PARAMS if control.name == "splashes")

DROP_SPREAD = 0.7              # drops land within this share of the frame's half-sizes
YOUNGEST, OLDEST = 0.4, 1.0    # range of a drop's age: the share of its rings made so far
CLUSTER_PULL = 0.7             # full clustering narrows the bell curve by this share
WOBBLE_FREQS = (3, 7, 13)      # bumps around a ring, one sine wave each
WOBBLE_GROWTH = 0.05           # the wobble grows by this share with every ring
INTERFERENCE_WAVELENGTH = 2.4  # wavelength of other drops' waves, in ring gaps
INTERFERENCE_DROPS = 3         # waves of up to this many other drops add up in full; more are
                               # scaled down to this many drops' worth
SMALLEST_RING = 0.2            # a ripple ring's radius never goes below this share of its plain radius
TILT = 0.15                    # radians: the squash axis, measured from the horizontal
IMPACT_RINGS = 3               # small circles at the impact point
IMPACT_GAP = 0.22              # their spacing, in ring gaps
SPLASH_NEAR = 0.7              # splash drops land at least this many ring gaps away ...
SPLASH_FAR = 4.8               # ... and at most this many
SPLASH_RINGS = 3               # circles around each splash drop
SPLASH_GAP = 0.225             # their spacing, in ring gaps
SPLASH_WOBBLE = 0.0            # unevenness of splash rings, in ring gaps (0 = true circles)
SPLASH_WOBBLE_FREQ = 5         # bumps around a splash ring
SPLASH_WOBBLE_GROWTH = 0.1     # splash wobble grows by this share per ring
PUDDLE_SIZE = 0.88             # puddle half-axes, as a share of the frame's half-sizes
PUDDLE_STEP = 0.04             # each further puddle outline is this share smaller
PUDDLE_WOBBLE = 0.019          # puddle edge wobble, in frame reference lengths
PUDDLE_BUMPS = 5               # bumps around the puddle edge
RING_POINTS = 200              # fewest points on a ripple ring or puddle outline
SPLASH_POINTS = 70             # fewest points on a splash ring
IMPACT_POINTS = 32             # fewest points on an impact circle
POINT_GAP = 0.5                # largest distance between neighbouring points on a curve, mm


@dataclass(frozen=True)
class Drop:
    x: float
    y: float
    age: float          # YOUNGEST to OLDEST: the share of the rings this drop has made
    phases: tuple       # where each wobble sine wave starts, one per WOBBLE_FREQS
    splashes: tuple     # MAX_SPLASHES draws of (direction, distance, phase, phase), each in [0, 1)


def generate(params, frame, rng) -> list[Stroke]:
    gap = params["spacing"] * frame.scale

    # 1. All random numbers, in a fixed order.
    puddle_phase = rng.uniform(0, 2 * math.pi)
    drops = place_drops(frame, rng, params["drops"], params["clustering"])

    # 2. The edge of the puddle.
    strokes = [Stroke(edge) for edge in puddle_edge(frame, params["puddle"], puddle_phase)]

    # 3. Each drop: ripples from the inside out, the impact, the splashes.
    for drop in drops:
        others = [other for other in drops if other is not drop]
        for k in range(ring_count(params["rings"], drop.age)):
            strokes.append(Stroke(ripple_ring(drop, k, gap, params, others)))
        strokes += [Stroke(ring) for ring in impact_rings(drop, gap)]
        strokes += [Stroke(ring) for ring in splash_rings(drop, gap, params["splashes"])]
    return strokes


def place_drops(frame, rng, count, clustering) -> list[Drop]:
    """Where the drops land, how old they are, and the random numbers for their rings.

    Everything is drawn for MAX_DROPS drops (and MAX_SPLASHES splashes each) and only the first
    `count` are used, so the rng is left in the same state for any count and any number of
    splashes: adding a drop leaves the others as they were.

    A drop's offset from the frame's centre is measured in DROP_SPREAD half-sizes. Without
    clustering it is uniform in [-1, 1]; with clustering c it is a bell curve of width
    1 − 0.7 · c, held inside [-1, 1].
    """
    bell = rng.standard_normal((MAX_DROPS, 2))
    even = rng.uniform(-1, 1, (MAX_DROPS, 2))
    ages = rng.uniform(YOUNGEST, OLDEST, MAX_DROPS)
    phases = rng.uniform(0, 2 * math.pi, (MAX_DROPS, len(WOBBLE_FREQS)))
    splashes = rng.random((MAX_DROPS, MAX_SPLASHES, 4))

    if clustering > 0:
        offset = np.clip(bell * (1 - CLUSTER_PULL * clustering), -1, 1)
    else:
        offset = even
    xs = frame.cx + offset[:, 0] * DROP_SPREAD * frame.half_w
    ys = frame.cy + offset[:, 1] * DROP_SPREAD * frame.half_h
    return [Drop(x=float(xs[i]), y=float(ys[i]), age=float(ages[i]),
                 phases=tuple(float(p) for p in phases[i]),
                 splashes=tuple(tuple(float(u) for u in draw) for draw in splashes[i]))
            for i in range(count)]


def ring_count(rings, age):
    """n = max(2, int(rings · age)): a young drop has made fewer rings."""
    return max(2, int(rings * age))


def angles(radius, fewest):
    """Directions θ from 0 to 2π, enough of them that points are at most POINT_GAP apart."""
    steps = max(fewest, math.ceil(2 * math.pi * radius / POINT_GAP))
    return np.linspace(0, 2 * math.pi, steps + 1)


def closed_curve(cx, cy, theta, r):
    """The points c + r(θ) · (cos θ, sin θ), with the last point set exactly onto the first."""
    points = np.column_stack([cx + r * np.cos(theta), cy + r * np.sin(theta)])
    points[-1] = points[0]
    return points


def puddle_edge(frame, count, phase):
    """`count` wobbly ellipses around the frame's centre, each PUDDLE_STEP smaller than the last."""
    edges = []
    for m in range(count):
        size = PUDDLE_SIZE * (1 - PUDDLE_STEP * m)
        theta = angles(size * max(frame.half_w, frame.half_h), RING_POINTS)
        wobble = PUDDLE_WOBBLE * frame.scale * np.sin(PUDDLE_BUMPS * theta + phase)
        points = np.column_stack([
            frame.cx + (size * frame.half_w + wobble) * np.cos(theta),
            frame.cy + (size * frame.half_h + wobble) * np.sin(theta),
        ])
        points[-1] = points[0]
        edges.append(points)
    return edges


def ripple_ring(drop, k, gap, params, others):
    """Ripple ring k of a drop: r(θ) = r_k + wobble_k(θ) + interference_k(θ), then squashed.

    r(θ) is kept at least 0.2 · r_k, so a strong push flattens the ring instead of folding it
    through its own centre.
    """
    radius = gap * params["growth"] ** k
    theta = angles(radius, RING_POINTS)
    r = (radius
         + wobble(drop, k, gap, params["wobble"], theta)
         + interference(drop, radius, gap, params["interference"], others, theta))
    r = np.maximum(r, SMALLEST_RING * radius)
    return squashed(closed_curve(drop.x, drop.y, theta, r), drop, params["squash"])


def wobble(drop, k, gap, strength, theta):
    """(w · s · (1 + 0.05 · k) / 3) · Σ_f sin(f · θ + φ_f): three sine waves around the ring."""
    amplitude = strength * gap * (1 + WOBBLE_GROWTH * k) / len(WOBBLE_FREQS)
    return sum(amplitude * np.sin(f * theta + phase) for f, phase in zip(WOBBLE_FREQS, drop.phases))


def interference(drop, radius, gap, strength, others, theta):
    """i · s · Σ_d cos(2π · |p − d| / λ), with p on the plain circle and λ = 2.4 · s.

    With more than three other drops the sum is scaled by 3 / (number of other drops), so a ring
    is never pushed further than three drops' waves could push it, however many drops there are.
    """
    if not others or strength == 0:
        return 0.0
    px = drop.x + radius * np.cos(theta)
    py = drop.y + radius * np.sin(theta)
    other_x = np.array([d.x for d in others])[:, None]       # one row per other drop
    other_y = np.array([d.y for d in others])[:, None]
    distance = np.hypot(px - other_x, py - other_y)
    wavelength = INTERFERENCE_WAVELENGTH * gap
    share = min(1.0, INTERFERENCE_DROPS / len(others))      # 1 for a few drops, less for many
    return strength * gap * share * np.cos(2 * math.pi * distance / wavelength).sum(axis=0)


def squashed(points, drop, squash):
    """The oblique view: squeeze the ring by `squash` along an axis tilted by TILT.

    Around the drop's centre: turn by −TILT, multiply x by squash, turn back by +TILT.
    """
    cos_t, sin_t = math.cos(TILT), math.sin(TILT)
    dx, dy = points[:, 0] - drop.x, points[:, 1] - drop.y
    along = (dx * cos_t + dy * sin_t) * squash
    across = -dx * sin_t + dy * cos_t
    return np.column_stack([drop.x + along * cos_t - across * sin_t,
                            drop.y + along * sin_t + across * cos_t])


def impact_rings(drop, gap):
    """Small plain circles of radius j · 0.22 · s at the point where the drop went in."""
    rings = []
    for j in range(1, IMPACT_RINGS + 1):
        radius = j * IMPACT_GAP * gap
        theta = angles(radius, IMPACT_POINTS)
        rings.append(closed_curve(drop.x, drop.y, theta, np.full(theta.shape, radius)))
    return rings


def splash_rings(drop, gap, count):
    """The rings of the first `count` splash drops this drop threw out.

    A splash lands in direction 2π · u0 at a distance between 0.7 · s and 4.8 · s. Its ring j has
    radius j · 0.225 · s, plus a wobble a · sin(5θ + φ0) + 0.4 · a · sin(10.5θ + φ1) that is zero
    while SPLASH_WOBBLE is 0.
    """
    rings = []
    for u_dir, u_dist, u_ph0, u_ph1 in drop.splashes[:count]:
        direction = 2 * math.pi * u_dir
        distance = gap * (SPLASH_NEAR + u_dist * (SPLASH_FAR - SPLASH_NEAR))
        sx = drop.x + distance * math.cos(direction)
        sy = drop.y + distance * math.sin(direction)
        ph0, ph1 = 2 * math.pi * u_ph0, 2 * math.pi * u_ph1
        for j in range(1, SPLASH_RINGS + 1):
            radius = j * SPLASH_GAP * gap
            amplitude = SPLASH_WOBBLE * gap * (1 + SPLASH_WOBBLE_GROWTH * (j - 1))
            theta = angles(radius, SPLASH_POINTS)
            r = (radius
                 + amplitude * np.sin(SPLASH_WOBBLE_FREQ * theta + ph0)
                 + 0.4 * amplitude * np.sin(2.1 * SPLASH_WOBBLE_FREQ * theta + ph1))
            rings.append(closed_curve(sx, sy, theta, r))
    return rings
