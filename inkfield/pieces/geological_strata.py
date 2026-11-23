"""Geological strata: level lines pushed up and down by folded noise, like crumpled cloth or rock.

What the picture shows
----------------------
Hundreds of thin horizontal lines, stacked closely. Each one has been lifted and lowered along
its length by a hidden landscape. Where the landscape is steep, neighbouring lines are pushed
by very different amounts, so they bunch up or even cross: dark seams, like the shadowed side
of a fold. Where it is flat they keep their even spacing: light, open bands. The folds swirl
and bend instead of running in straight ridges, which gives the look of rock strata that have
been squeezed, or of crumpled fabric seen from above.

The model
---------
Everything is measured against the frame's reference length S (half its shorter side), so the
picture keeps its proportions on any page. Only the line spacing is in millimetres, because it
sets how dark the paper gets under a real pen.

* Scan lines. Line k starts level at height y_k, the lines `spacing` mm apart from the frame's
  top edge to its bottom edge. Each line is a row of points a fixed small step apart in x.
* Gradient noise n(u, v). A smooth random hill-and-valley pattern with values between -1 and 1
  (Perlin's gradient noise): at every whole-number lattice point (i, j) a random unit arrow g_ij
  is fixed, and the value at (u, v) blends the four nearby "slopes" g_ij · ((u, v) - (i, j)),
  using the easing curve s(t) = 6t^5 - 15t^4 + 10t^3 so the blend has no visible creases.
  Which arrow sits at which lattice point comes from a shuffled table of 0..255 drawn from the
  rng: a new seed shuffles the table and so gives a new landscape.
* Fractal noise (fBm). Rough landscapes have hills on hills. Octave o (o = 0 .. detail-1) is
  the same noise at frequency 2^o and weight roughness^o:

      fbm(u, v) = Σ_o roughness^o · n(2^o u, 2^o v)  /  Σ_o roughness^o

  Dividing by the sum of the weights keeps it between -1 and 1.
* Domain warping. Before the landscape is looked up, the lookup point itself is moved by a
  second, independent noise field (its own shuffled table):

      w_u = warp · fbm_3(u / warp_size,       v / warp_size)
      w_v = warp · fbm_3(u / warp_size + 5.2, v / warp_size + 1.3)
      h(u, v) = fbm(u + w_u, v + w_v)

  fbm_3 has three octaves, and the offsets 5.2, 1.3 just make w_v a different field from w_u.
  Straight ridges get dragged sideways by different amounts in different places, so they bend
  and fold over: this is what makes the picture look geological rather than merely hilly.
* Displacement. With (u, v) = (x - x0, y_k - y0) / (fold_size · S) the page point in noise
  units, the line's point at x is drawn at

      y = y_k + relief · S · h(u, v)

* Torn edges. Close to the frame's sides the lines are broken off along a ragged edge. A point
  is d fade widths in from the nearest side (the fade width is `edge_fade` times the frame's
  width for the left and right sides, times its height for the top and bottom). It is kept
  when

      d + 0.8 · torn · fbm_3(at the point, with a third table)  >=  0.01

  so the noise nibbles a wobbly bite out of each line near the sides. The test uses the line's
  level height y_k, not its displaced one, so the tears follow the strata. Edge fade 0 switches
  the edge off.

The controls
------------
Line spacing  distance between neighbouring level lines, in mm.
Relief        how far a line can be pushed up or down, in frame reference lengths.
Fold size     the size of the largest hills, in frame reference lengths.
Detail        how many octaves of ever finer hills are added.
Roughness     how strong each finer octave is compared with the one before it.
Warp          how far the lookup point is dragged, in fold sizes: 0 gives plain hills.
Warp size     the size of the dragging pattern, in fold sizes.
Torn edges    how ragged the broken edges are.
Edge fade     how deep the band along the sides is where lines may break, as a fraction of the
              frame's width (sides) or height (top and bottom).

How the lines are drawn
-----------------------
1. Shuffle three tables from the rng: landscape, warp, edge.
2. Lay out the grid of points: one row per level line, the same x positions on every row.
3. Displace every point by the warped landscape (all rows at once, plain numpy).
4. Decide which points the torn edge keeps.
5. Each unbroken run of two or more kept points on a row becomes one stroke.
"""
import math

import numpy as np

from inkfield.core.controls import Slider
from inkfield.core.piece import Meta
from inkfield.core.stroke import Stroke

META = Meta(
    slug="geological-strata",
    title="Geological strata",
    subtitle="Folded scan lines",
    framed_shape="rect",
    seed=1,
    info=("Hundreds of level lines, each pushed up and down by a fractal noise landscape. The "
          "landscape is looked up at a point that is itself dragged around by a second noise "
          "field (domain warping), so its ridges bend and fold. On steep slopes the lines bunch "
          "into dark seams; on plateaus they keep their spacing. Near the sides the lines break "
          "off along a ragged, noisy edge."),
)

PARAMS = [
    Slider("spacing",   "Line spacing", 0.4, 3,   0.05, 1.0, " mm"),
    Slider("relief",    "Relief",       0,   1,   0.01, 0.40),
    Slider("fold_size", "Fold size",    0.2, 2.5, 0.01, 0.83),
    Slider("detail",    "Detail",       1,   8,   1,    6),
    Slider("roughness", "Roughness",    0.2, 0.8, 0.01, 0.50),
    Slider("warp",      "Warp",         0,   6,   0.1,  2.5),
    Slider("warp_size", "Warp size",    0.5, 4,   0.05, 1.5),
    Slider("torn",      "Torn edges",   0,   3,   0.05, 0.70),
    Slider("edge_fade", "Edge fade",    0,   0.3, 0.01, 0.05),
]

POINT_GAP = 0.67           # mm between points along a line (the prototype's 300 steps over 200 mm)
LACUNARITY = 2.0           # frequency multiplier from one octave to the next
WARP_OCTAVES = 3           # octaves in the warp field
WARP_OFFSET = (5.2, 1.3)   # moves the second warp component's lookup, so w_v differs from w_u
EDGE_OCTAVES = 3           # octaves in the torn-edge noise
EDGE_FREQUENCY = 2.0       # torn-edge noise frequency, per frame reference length
EDGE_WOBBLE = 0.8          # torn-edge noise reach, in fade widths, at Torn edges = 1
EDGE_KEEP = 0.01           # a point is kept when its noisy depth in fade widths reaches this
TABLE_SIZE = 256           # entries in each shuffled lattice table

# The twelve arrows a lattice point can hold: unit vectors 30 degrees apart.
GRADIENTS = np.array([(math.cos(a), math.sin(a)) for a in np.arange(12) * 2 * math.pi / 12])


def generate(params, frame, rng) -> list[Stroke]:
    fold_mm = params["fold_size"] * frame.scale
    x0, y0, x1, y1 = frame.bbox

    # 1. Three independent shuffles, always drawn in this order.
    landscape, warp_table, edge_table = (rng.permutation(TABLE_SIZE) for _ in range(3))

    # 2. One row per level line, the same x positions on every row.
    x, y_level = scan_grid(frame.bbox, params["spacing"])

    # 3. Each point moved up or down by the warped landscape.
    u, v = (x - x0) / fold_mm, (y_level - y0) / fold_mm
    height = warped_fbm(u, v, landscape, warp_table, params["detail"], params["roughness"],
                        params["warp"], params["warp_size"])
    y = y_level + params["relief"] * frame.scale * height

    # 4 and 5. Break the rows along the torn edge and keep the unbroken runs.
    keep = torn_edge_keeps(x, y_level, frame, edge_table, params["torn"], params["edge_fade"])
    strokes = []
    for row in range(x.shape[0]):
        points = np.column_stack([x[row], y[row]])
        strokes += [Stroke(run) for run in kept_runs(points, keep[row])]
    return strokes


def scan_grid(bbox, spacing):
    """x and level height of every point: arrays of shape (lines, points per line).

    The level lines run from the top edge to the bottom edge, about `spacing` mm apart (exactly
    evenly spread over the height); points along a line are at most POINT_GAP mm apart.
    """
    x0, y0, x1, y1 = bbox
    rows = np.linspace(y0, y1, round((y1 - y0) / spacing) + 1)
    columns = np.linspace(x0, x1, math.ceil((x1 - x0) / POINT_GAP) + 1)
    return np.meshgrid(columns, rows)


def gradient_noise(u, v, table):
    """Perlin gradient noise at (u, v), between -1 and 1 (in fact within ±0.71); 0 on the lattice.

    The arrow at lattice point (i, j) is GRADIENTS[t[t[i] + j] mod 12], with t the table repeated
    twice so that t[i] + j never runs off the end.
    """
    t = np.concatenate([table, table])
    i, j = np.floor(u), np.floor(v)
    fu, fv = u - i, v - j                            # where we are inside the lattice cell, 0..1
    i, j = i.astype(np.int64) & 255, j.astype(np.int64) & 255

    def slope(di, dj):
        """The corner (i + di, j + dj)'s arrow dotted with the offset from that corner."""
        g = GRADIENTS[t[t[i + di] + j + dj] % 12]
        return g[..., 0] * (fu - di) + g[..., 1] * (fv - dj)

    su, sv = ease(fu), ease(fv)
    bottom = slope(0, 0) + su * (slope(1, 0) - slope(0, 0))
    top = slope(0, 1) + su * (slope(1, 1) - slope(0, 1))
    return bottom + sv * (top - bottom)


def ease(t):
    """s(t) = 6t^5 - 15t^4 + 10t^3: 0 at 0, 1 at 1, flat at both ends."""
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def fbm(u, v, table, octaves, roughness=0.5):
    """Fractal noise: octave o has frequency LACUNARITY^o and weight roughness^o; within -1..1."""
    total = np.zeros(np.shape(u))
    weight, frequency, weights = 1.0, 1.0, 0.0
    for _ in range(octaves):
        total += weight * gradient_noise(u * frequency, v * frequency, table)
        weights += weight
        weight *= roughness
        frequency *= LACUNARITY
    return total / weights


def warped_fbm(u, v, landscape, warp_table, detail, roughness, warp, warp_size):
    """h(u, v) = fbm(u + w_u, v + w_v), the lookup point dragged by a second noise field first."""
    wu = warp * fbm(u / warp_size, v / warp_size, warp_table, WARP_OCTAVES)
    wv = warp * fbm(u / warp_size + WARP_OFFSET[0], v / warp_size + WARP_OFFSET[1],
                    warp_table, WARP_OCTAVES)
    return fbm(u + wu, v + wv, landscape, detail, roughness)


def torn_edge_keeps(x, y_level, frame, edge_table, torn, edge_fade):
    """True where a point survives the ragged edge (see "Torn edges" in the module docstring)."""
    if edge_fade == 0:
        return np.ones(x.shape, dtype=bool)
    x0, y0, x1, y1 = frame.bbox
    across, down = edge_fade * (x1 - x0), edge_fade * (y1 - y0)   # fade widths, mm
    depth = np.minimum.reduce([(x - x0) / across, (x1 - x) / across,
                               (y_level - y0) / down, (y1 - y_level) / down])
    if torn > 0:
        f = EDGE_FREQUENCY / frame.scale
        wobble = fbm((x - x0) * f, (y_level - y0) * f, edge_table, EDGE_OCTAVES)
        depth = depth + EDGE_WOBBLE * torn * wobble
    return depth >= EDGE_KEEP


def kept_runs(points, keep):
    """The unbroken stretches of `points` where `keep` is True, each with at least two points."""
    edges = np.flatnonzero(np.diff(np.concatenate([[0], keep.astype(np.int8), [0]])))
    starts, ends = edges[::2], edges[1::2]               # each run is points[start:end]
    return [points[s:e] for s, e in zip(starts, ends) if e - s >= 2]
