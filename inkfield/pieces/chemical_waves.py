"""Chemical waves: target rings, spirals and cusped seams, as in the Belousov–Zhabotinsky reaction.

What the photographs show
-------------------------
A thin layer of the Belousov–Zhabotinsky mixture in a petri dish. Here and there a speck of dust
or a bubble sets off a chemical wave: a thin bright front that runs outward at a steady speed.
Once the medium behind a front has recovered, the same spot fires again, so each spot sends out
ring after ring, evenly spaced: a "target". Where a front is broken, its free end curls up and
keeps turning, which gives a spiral. Where two waves collide they wipe each other out, because
the medium behind each front cannot react again yet; the meeting line is a seam with sharp cusps.

The model
---------
This is geometry, not a chemistry simulation. Everything is measured in millimetres, and time is
measured in millimetres too: waves move at speed 1 everywhere, so "time" means "distance a wave
has travelled".

* A number of pacemakers P_i sit at random places. Pacemaker i starts after its own delay d_i.
* Its first wave reaches a point q at

      arrival_i(q) = d_i + |q - P_i|

  The point belongs to whichever pacemaker reaches it first. Lines that would cross into a
  neighbour's territory are stopped exactly where the neighbour's wave arrives sooner: that
  border is the seam.
* At the moment of the picture, the elapsed time T, the point has seen

      base_i(q) = (T - arrival_i(q)) / wavelength

  waves go by. Call this number the phase. **Pen lines are where the phase is a whole number:**
  phase 0 is the outermost front, phase 1 the front one wavelength behind it, and so on. Points
  not yet reached (base below 0) get no lines.
* A spiral adds a twist. With a_i the angle of q around its core (atan2, from -π to π), turn_i
  = +1 or -1 for the direction it winds, and o_i a random offset that rotates the arm,

      phase_i(q) = base_i(q) + turn_i · a_i / 2π + o_i

  Going once around the core adds exactly one to the phase, so each ring is opened up and joined
  to the next: an Archimedean spiral. Close to the core the angle changes faster than the grid
  can follow, so arms stop cleanly at a small core radius, 0.35 wavelengths.
* Seams: two ring systems with the same wavelength reach every seam point at the same time, so
  their lines arrive there with the same phase and meet in pairs, forming the cusps.
* Uneven medium: real dishes are not perfectly uniform, so rings come out a little lumpy. Before
  any distance is measured, each point p is moved to

      q = p + strength · F(p),   strength = min(unevenness · 1.2 · wavelength, 0.08 · W)

  where F is a smooth random field (see `inkfield.core.noise`) whose ripples have size
  W = 0.9 · the frame's reference length. The cap 0.08 · W is there because pushing points
  further than that, over ripples that short, would bend space so hard that it folds over
  itself: two nearby page points would swap places, and rings would cross themselves. Below the
  cap neighbouring points always keep their order. All formulas above use q.

The controls
------------
Pacemakers         how many wave sources.
Spiral share       the chance that a source is a spiral rather than a target.
Wavelength         the distance between successive fronts, in mm.
Elapsed time       how far waves have travelled, as a multiple of the frame's reference length
                   (half its shorter side): small values leave empty medium between blobs,
                   large ones fill the frame.
Start stagger      how spread out the start delays are, as a fraction of the elapsed time.
                   Late starters get small territories hemmed in by early ones.
Medium unevenness  how strongly the medium is distorted, relative to the wavelength.

How the lines are drawn
-----------------------
1. Place the pacemakers and give each its delay, kind, direction and offset.
2. Sample a grid over the frame's bounding box, with cells at most wavelength / 8 wide (and at
   most 0.5 mm), so neighbouring grid points differ in phase by about an eighth at most (a little
   more near a spiral core or where the medium is stretched): fine enough for clean tracing.
3. Go through the pacemakers once, keeping only two grids: the earliest arrival seen so far and
   which pacemaker it came from. That says who owns each grid point.
4. For each pacemaker, trace the whole-number lines of its own phase (marching squares, see
   `inkfield.core.contours`), only in grid cells it owns at least one corner of and that its
   wave has (nearly) reached. Its own phase is smooth everywhere, so its lines are smooth too,
   and they run a little past the seam.
5. Cut each line back exactly at the seam, by asking at the line's own points, not at grid
   points, whether this pacemaker's wave arrives no later than every other. Spiral arms are also
   cut where the wave has not arrived yet and at the core.
"""
import math
from dataclasses import dataclass

import numpy as np

from inkfield.core.contours import trace_whole_numbers
from inkfield.core.controls import Slider
from inkfield.core.noise import SmoothField
from inkfield.core.piece import Meta
from inkfield.core.polyline import keep_where
from inkfield.core.stroke import Stroke

META = Meta(
    slug="chemical-waves",
    title="Chemical waves",
    subtitle="Belousov–Zhabotinsky",
    framed_shape="circle",
    info=("Each pacemaker starts emitting waves at its own moment. A point in the dish is claimed "
          "by whichever wave reaches it first, so the medium is described by one field: "
          "arrival(x) = min(delay + distance). Pen lines are the level curves of that field, one "
          "per wavelength. Spirals add a twist proportional to the angle around their core. Where "
          "two wave systems meet they cancel, which gives the cusped seams."),
)

PARAMS = [
    Slider("sources",    "Pacemakers",        1,    24,  1,    9),
    Slider("spirals",    "Spiral share",      0,    1,   0.01, 0.30),
    Slider("wavelength", "Wavelength",        2,    14,  0.1,  5.5, " mm"),
    Slider("elapsed",    "Elapsed time",      0.08, 2,   0.01, 0.42),
    Slider("stagger",    "Start stagger",     0,    1,   0.01, 0.70),
    Slider("uneven",     "Medium unevenness", 0,    1,   0.01, 0.20),
]

PLACEMENT_SHRINK = 0.92     # pacemakers stay off the outer 8 % of the frame
UNEVEN_REACH = 1.2          # at full unevenness, points move up to 1.2 wavelengths
UNEVEN_SIZE = 0.9           # size of the medium's ripples, in frame reference lengths
UNEVEN_LIMIT = 0.08         # largest push, in ripple sizes: more would fold space over itself
LARGEST_CELL = 0.5          # grid cell size limit, mm
CELLS_PER_WAVELENGTH = 8
CORE_RADIUS = 0.35          # spiral arms stop this many wavelengths from the core


@dataclass(frozen=True)
class Pacemaker:
    x: float
    y: float
    delay: float          # mm of wave travel before it starts
    is_spiral: bool
    turn: int             # +1 or -1: which way a spiral winds
    phase_offset: float   # rotates a spiral's arm about its core


def generate(params, frame, rng) -> list[Stroke]:
    wavelength = params["wavelength"]
    elapsed_mm = params["elapsed"] * frame.scale

    # 1. The sources, and the slightly uneven medium their waves travel through.
    pacemakers = place_pacemakers(frame, rng, params["sources"], params["spirals"],
                                  params["stagger"], elapsed_mm)
    measure = uneven_medium(frame, rng, params["uneven"], wavelength)

    # 2. A grid over the frame, every grid point moved into the uneven medium once.
    cell = min(LARGEST_CELL, wavelength / CELLS_PER_WAVELENGTH)
    xs, ys = grid_over(frame.bbox, cell)
    qx, qy = measure(*np.meshgrid(xs, ys))

    # 3. Who reaches each grid point first.
    owner = first_to_arrive(pacemakers, qx, qy)

    strokes = []
    for i, pacemaker in enumerate(pacemakers):
        # 4. This pacemaker's own lines, near its territory ...
        lines = trace_own_lines(i, pacemaker, owner, xs, ys, qx, qy, elapsed_mm, wavelength)
        # 5. ... cut exactly where another wave gets there first.
        inside = own_territory(i, pacemakers, measure, elapsed_mm, wavelength)
        for line in lines:
            strokes += [Stroke(part) for part in keep_where(line, inside)]
    return strokes


def place_pacemakers(frame, rng, count, spiral_share, stagger, elapsed_mm) -> list[Pacemaker]:
    """Random positions inside the frame, then four numbers per pacemaker, always in this order.

    delay is uniform in [0, stagger · elapsed); a pacemaker is a spiral with probability
    spiral_share; it winds one way or the other with equal chance; its arm offset is uniform.
    """
    positions = frame.sample(rng, count, shrink=PLACEMENT_SHRINK)
    draws = rng.random((count, 4))
    return [Pacemaker(x=float(x), y=float(y),
                      delay=float(u_delay * stagger * elapsed_mm),
                      is_spiral=bool(u_kind < spiral_share),
                      turn=1 if u_turn < 0.5 else -1,
                      phase_offset=float(u_offset))
            for (x, y), (u_delay, u_kind, u_turn, u_offset) in zip(positions, draws)]


def uneven_medium(frame, rng, unevenness, wavelength):
    """measure(x, y) -> (qx, qy): where each page point lies in the uneven medium.

    q = p + strength · F(p), with F a smooth random field whose ripples are about as large as the
    frame. The strength grows with unevenness and wavelength but is capped at UNEVEN_LIMIT ripple
    sizes so that space never folds. With strength 0 the medium is even and q is simply p.
    """
    ripple_size = UNEVEN_SIZE * frame.scale
    field = SmoothField(rng, wavelength=ripple_size)
    strength = min(unevenness * UNEVEN_REACH * wavelength, UNEVEN_LIMIT * ripple_size)

    def measure(x, y):
        if strength == 0:
            return x, y
        dx, dy = field(x, y)
        return x + strength * dx, y + strength * dy

    return measure


def grid_over(bbox, cell):
    """Grid coordinates xs, ys spanning the box, with gaps no wider than `cell`."""
    x0, y0, x1, y1 = bbox
    xs = np.linspace(x0, x1, math.ceil((x1 - x0) / cell) + 1)
    ys = np.linspace(y0, y1, math.ceil((y1 - y0) / cell) + 1)
    return xs, ys


def arrival_time(pacemaker, qx, qy):
    """When this pacemaker's first wave reaches q: its delay plus the distance travelled."""
    return pacemaker.delay + np.hypot(qx - pacemaker.x, qy - pacemaker.y)


def waves_passed(pacemaker, qx, qy, elapsed_mm, wavelength):
    """base = (elapsed − arrival) / wavelength: how many fronts have gone by; negative = not yet."""
    return (elapsed_mm - arrival_time(pacemaker, qx, qy)) / wavelength


def phase(pacemaker, qx, qy, elapsed_mm, wavelength):
    """The number whose whole values are the pen lines: base, plus a twist for a spiral."""
    base = waves_passed(pacemaker, qx, qy, elapsed_mm, wavelength)
    if not pacemaker.is_spiral:
        return base
    angle = np.arctan2(qy - pacemaker.y, qx - pacemaker.x)
    return base + pacemaker.turn * angle / (2 * math.pi) + pacemaker.phase_offset


def first_to_arrive(pacemakers, qx, qy):
    """For every grid point, the index of the pacemaker whose wave gets there first.

    One pass over the pacemakers, keeping only the earliest arrival seen so far and whose it was.
    """
    earliest = np.full(qx.shape, np.inf)
    owner = np.full(qx.shape, -1)
    for i, pacemaker in enumerate(pacemakers):
        arrival = arrival_time(pacemaker, qx, qy)
        sooner = arrival < earliest
        earliest[sooner] = arrival[sooner]
        owner[sooner] = i
    return owner


def trace_own_lines(i, pacemaker, owner, xs, ys, qx, qy, elapsed_mm, wavelength):
    """Whole-number lines of pacemaker i's phase, in the cells next to or inside its territory.

    A cell is traced when i owns at least one of its corners (so the lines run a little past the
    seam, ready to be cut there exactly) and its wave has nearly reached all four corners
    (base > −0.5, so the outermost front, base = 0, is traced and nothing beyond it). Only the
    rectangle of grid points around the territory is computed.
    """
    owned = owner == i
    rows = np.flatnonzero(owned.any(axis=1))
    cols = np.flatnonzero(owned.any(axis=0))
    if len(rows) == 0:
        return []
    top, bottom = max(rows[0] - 1, 0), min(rows[-1] + 1, len(ys) - 1) + 1
    left, right = max(cols[0] - 1, 0), min(cols[-1] + 1, len(xs) - 1) + 1
    window = (slice(top, bottom), slice(left, right))

    owned = owned[window]
    reached = waves_passed(pacemaker, qx[window], qy[window], elapsed_mm, wavelength) > -0.5
    owns_a_corner = owned[:-1, :-1] | owned[:-1, 1:] | owned[1:, 1:] | owned[1:, :-1]
    reached_all = reached[:-1, :-1] & reached[:-1, 1:] & reached[1:, 1:] & reached[1:, :-1]
    own_phase = phase(pacemaker, qx[window], qy[window], elapsed_mm, wavelength)
    return trace_whole_numbers(own_phase, xs[left:right], ys[top:bottom],
                               cells=owns_a_corner & reached_all)


def own_territory(i, pacemakers, measure, elapsed_mm, wavelength):
    """inside(x, y): where pacemaker i's lines may be drawn, tested exactly at the given points.

    A point qualifies when i's wave arrives no later than every other pacemaker's. For a spiral it
    must also have been reached already (base >= 0) and lie outside the core.
    """
    own = pacemakers[i]
    others = [p for k, p in enumerate(pacemakers) if k != i]
    other_x = np.array([p.x for p in others])[:, None]       # one row per other pacemaker
    other_y = np.array([p.y for p in others])[:, None]
    other_delay = np.array([p.delay for p in others])[:, None]

    def inside(x, y):
        qx, qy = measure(x, y)
        arrival = arrival_time(own, qx, qy)
        keep = np.ones(arrival.shape, dtype=bool)
        if others:
            first_other = (other_delay + np.hypot(qx - other_x, qy - other_y)).min(axis=0)
            keep &= arrival <= first_other
        if own.is_spiral:
            keep &= waves_passed(own, qx, qy, elapsed_mm, wavelength) >= 0
            keep &= np.hypot(qx - own.x, qy - own.y) >= CORE_RADIUS * wavelength
        return keep

    return inside
