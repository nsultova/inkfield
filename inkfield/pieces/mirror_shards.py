"""Mirror shards: a sheet of glass broken at a few impact points, and its shards pulled apart.

What real impact glass shows
----------------------------
Hit a pane hard at one point and it breaks in a recognisable pattern: straight radial cracks
("spokes") run out from the impact, ring cracks ("hoops") join neighbouring spokes at distances
that grow outward, and close to the impact, where the stress was highest, the pieces between them
shatter again into fine splinters. Far away only a few large calm plates remain. When the pane is
struck in several places, a crack from one impact stops where it meets a crack field from another,
because a crack cannot run across a surface that is already broken.

The model
---------
Everything is built from one operation: cut a convex polygon in two along a straight line. Each
piece of a convex polygon cut by a line is convex again, and the two pieces add up exactly to the
whole, so every shard is exact and the shards tile the sheet without gaps or overlaps. The cuts
are made in four stages, each one cutting the pieces of the stage before, which gives a tree:
sheet → territories → wedges → rings → splinters.

1. Territories. Impact i sits at P_i with energy e_i. Between impacts i and j the dividing line
   is perpendicular to the segment from P_i to P_j, at distance

       t = (d² + (e_i − e_j) · w) / (2d)          (d = |P_j − P_i|, w = reach²)

   from P_i (the "radical axis" of a power diagram). Equal energies split the segment in the
   middle; a stronger impact claims more of the sheet. These lines are the cracks where two
   fracture fields met; every later crack stays inside its own territory.
2. Spokes. n = round(spokes · √e_i) lines through P_i at evenly spaced, slightly jittered angles
   cut the territory into wedges. A wedge must span less than half a turn to stay convex, so any
   wider gap between spokes is halved until it is narrow enough.
3. Rings. Radii r_k = r_0 · growth^k (k = 0, 1, ...), each jittered once per territory. In a
   wedge of half-angle h around the direction m, the ring crack is the line perpendicular to m
   at distance r_k · cos h from P_i: the chord of the circle of radius r_k between the two
   spokes. Its ends lie at exactly r_k on both spokes, so the chords of neighbouring wedges meet
   and each ring reads as one faceted polygon.
4. Splinters. A ring piece whose centroid is r from its impact has stress

       stress = e_i · ((r_0 + ε) / (r + ε))^α        (1 at the first ring, ε keeps it finite)

   and splits with probability min(1, splintering · stress), along a line through (near) its
   centroid. Each half may split again, with the probability multiplied by 0.7 per level, until
   the depth limit or a smallest area is reached. Fine splinters near the impact, big plates far.

Separation
----------
At separation 0 the picture is the crack pattern itself: every crack is collected once (shards
on both sides of a crack share it) and the cracks are chained into long pen strokes. Above 0 each
leaf shard is drawn as its own closed outline, moved by the sum of three pushes. With s the
separation, a shard at tree level L of the deepest level L_max starts moving at
s_L = 0.35 · (1 − L / L_max) and has its own time τ = (s − s_L) / (1 − s_L), clamped to [0, 1], so
fine splinters part first and the big plates last.

  bloom     the sum, over the shard and all its ancestors, of (own centroid − parent's centroid)
            · τ of that level: gaps open at every scale at once.
  spray     straight away from its impact, with speed J / area, J = e_i / (r + ε): equal kicks
            on unequal masses, so small splinters near the impact fly furthest. Bent a little
            along a smooth random flow.
  dissolve  along the smooth random flow, by τ^(1 − r / 2 r_max): straight out near the impact,
            a slower random-walk spread (√τ) at the rim.

Each push is scaled so that its median over the shards is 0.47 frame reference lengths at
separation 1 (bloom at weight 1, spray at 0.35, dissolve at 0.25). Finally the whole drawing is
shrunk about the frame centre, if needed, so that it still fits the frame.

Cracks are drawn as gentle curves: each straight edge bows sideways by up to 3 % of its length,
the same way for both shards that share it, so the seams stay shut at separation 0. With Gap
above 0 the shards are shrunk to new corners that no crack bow belongs to, so their outlines are
drawn straight.

The controls
------------
Impacts             how many places the glass was struck.
Spokes              radial cracks per impact (more for a harder impact).
Rings               how many ring cracks around each impact.
Ring spacing growth how much further apart each next ring is.
Splintering         how readily ring pieces shatter further (scales the split probability).
Splinter depth      how many times a piece may split again.
Splinter direction  −1: splinter cracks run towards the impact; +1: across it; 0: any way.
Separation          how far the shards are pulled apart.
Gap                 shrinks every shard by this many mm, leaving even white channels between them.
Mirror glint        hatches the shards that face the light, as if catching a reflection.
"""
import math

import numpy as np

from inkfield.core.controls import Slider, Toggle
from inkfield.core.noise import SmoothField
from inkfield.core.piece import Meta
from inkfield.core.stroke import Stroke

META = Meta(
    slug="mirror-shards",
    title="Mirror shards",
    subtitle="Impact fracture in glass",
    framed_shape="rect",
    seed=1,
    info=("A sheet of glass struck at a few points. Around each impact, radial cracks, ring "
          "cracks and a cascade of splinters that is finest where the stress was highest; cracks "
          "from one impact stop at another's territory. Every shard is a convex polygon cut by "
          "straight lines. Separation pulls the shards apart: fine splinters first, big plates "
          "last."),
)

PARAMS = [
    Slider("impacts",     "Impacts",             1,   8,   1,    3),
    Slider("spokes",      "Spokes",              3,   24,  1,    9),
    Slider("rings",       "Rings",               0,   10,  1,    6),
    Slider("ring_growth", "Ring spacing growth", 1.1, 2.5, 0.01, 1.55),
    Slider("splinter",    "Splintering",         0,   2,   0.01, 0.75),
    Slider("depth",       "Splinter depth",      0,   7,   1,    4),
    Slider("direction",   "Splinter direction",  -1,  1,   0.01, 0),
    Slider("separation",  "Separation",          0,   1,   0.01, 0),
    Slider("gap",         "Gap",                 0,   1.5, 0.05, 0, " mm"),
    Toggle("glint",       "Mirror glint",        False),
]

MAX_IMPACTS = next(int(control.max) for control in PARAMS if control.name == "impacts")
# Lengths marked "ref" are in frame reference lengths (frame.scale, half the shorter side).
IMPACT_SHRINK = 0.7        # impacts stay off the outer 15 % of the frame on each side
ENERGY_SPREAD = 0.4        # impact energies are 1 ± 40 %
REACH = 0.79               # ref; turns energy differences into territory size (the w above)
SPOKE_JITTER = 0.35        # spokes move up to this share of half their spacing
FIRST_RING = 0.122         # ref; radius r_0 of the first ring
RING_JITTER = 0.2          # each ring radius varies by up to ±20 %
STRESS_FALLOFF = 0.85      # α: how fast stress falls with distance from the impact
STRESS_EPS = 0.011         # ref; the ε in the stress and spray formulas
SPLINTER_FALLOFF = 0.7     # the split probability is multiplied by this per level
SMALLEST_AREA = 2e-4       # ref²; pieces smaller than this are not split further
SPLIT_TURN = 0.3           # radians; how far a directed splinter crack may turn
SHARD_CAP = 20000          # no more shards than this, however the sliders are set
AREA_EPS = 1e-4            # mm²; a cut leaving a piece smaller than this is refused
STAGGER = 0.35             # how much later the big plates start moving than the splinters
SPREAD = 0.47              # ref; median push of each kind at separation 1 and weight 1
BLOOM, SPRAY, DISSOLVE = 1.0, 0.35, 0.25   # weights of the three pushes
SPRAY_CAP = 4.0            # no shard sprays faster than this many times the median speed
SWIRL = 0.2                # how much the spray bends along the flow
FLOW_SIZE = 0.44           # ref; size of the swirls of the random flow
TILT = 0.0                 # squash shards along a random axis, as if tipped out of plane
CRACK_BOW = 0.06           # sideways bend of a crack, as a share of its length (± half this)
BOW_POINTS = 5             # points per bent crack
SNAP = 0.15                # mm; crack ends closer than this count as the same point
LIGHT = math.radians(135)  # direction the light comes from, for the glint
GLINT_SHARE = 0.55         # a shard glints when cos(facing − light) is above this
FACING_SPREAD = math.pi    # how much a shard's facing varies around "away from the impact"
HATCH_ANGLE = math.radians(30)
HATCH_SPACING = 0.8        # mm between glint hatch lines


class Shard:
    """One convex piece of glass: a node in the tree of cuts."""

    def __init__(self, poly, level, impact, parent=None, depth=0):
        self.poly, self.level, self.impact, self.parent, self.depth = poly, level, impact, parent, depth
        self.children = []
        self.centroid = polygon_centroid(poly)
        self.area = polygon_area(poly)
        if parent is not None:
            parent.children.append(self)


def generate(params, frame, rng) -> list[Stroke]:
    # 1. The sheet and where it was struck.
    sheet = sheet_polygon(frame)
    impacts = scatter_impacts(frame, rng, params["impacts"])

    # 2. Break it: the tree of shards. Nothing after this step changes the shards themselves.
    leaves = leaves_of(break_sheet(sheet, impacts, rng, params, frame.scale))

    # 3. Random looks, drawn the same way whatever the separation: crack bows, per-shard numbers
    #    (tilt axis, tilt amount, which way the shard faces), and the flow.
    bows = crack_bows(leaves, sheet, rng)
    tilt_axis, tilt_amount, facing = rng.random((3, len(leaves)))
    flow = SmoothField(rng, wavelength=FLOW_SIZE * frame.scale)

    # 4. Draw the cracks once, or every shard on its own, moved.
    if params["separation"] == 0 and params["gap"] == 0:
        strokes = [Stroke(line) for line in crack_lines(leaves, bows)]
        def place(i, points): return points
    else:
        moves = disperse(leaves, impacts, params["separation"], frame.scale, flow)
        place = placer(leaves, moves, 2 * math.pi * tilt_axis, TILT * tilt_amount, frame)
        strokes = []
        for i, shard in enumerate(leaves):
            poly = erode(shard.poly, params["gap"])
            if poly:
                strokes.append(Stroke(place(i, outline(poly, bows))))

    # 5. Glint: hatch the shards that face the light.
    if params["glint"]:
        for i, shard in enumerate(leaves):
            x, y, _ = impacts[shard.impact]
            away = math.atan2(shard.centroid[1] - y, shard.centroid[0] - x)
            if math.cos(away + (facing[i] - 0.5) * FACING_SPREAD - LIGHT) > GLINT_SHARE:
                for line in hatch(erode(shard.poly, params["gap"])):
                    strokes.append(Stroke(place(i, np.array(line))))
    return strokes


# ── Convex polygons ──────────────────────────────────────────────────────────
# A polygon is a list of (x, y), counter-clockwise (positive area). A line is (nx, ny, c) with
# (nx, ny) of length 1; it keeps the half-plane nx·x + ny·y <= c.

def polygon_area(poly) -> float:
    """Shoelace formula: half the sum of x_k · y_k+1 − x_k+1 · y_k."""
    return 0.5 * sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]))


def polygon_centroid(poly):
    """The balance point of the polygon's area."""
    sx = sy = 0.0
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        cross = x0 * y1 - x1 * y0
        sx, sy = sx + (x0 + x1) * cross, sy + (y0 + y1) * cross
    area = polygon_area(poly)
    return np.array([sx, sy]) / (6 * area)


def clip(poly, line):
    """The part of the polygon on the kept side of the line, or [] if that part is (nearly) empty.

    Walk round the polygon (Sutherland–Hodgman): keep every corner on the kept side, and add the
    crossing point wherever an edge crosses the line.
    """
    nx, ny, c = line
    out = []
    for (ax, ay), (bx, by) in zip(poly, poly[1:] + poly[:1]):
        da, db = nx * ax + ny * ay - c, nx * bx + ny * by - c
        if da <= 0:
            out.append((ax, ay))
        if (da < 0 < db) or (db < 0 < da):
            t = da / (da - db)
            out.append((ax + t * (bx - ax), ay + t * (by - ay)))
    out = [p for k, p in enumerate(out) if math.dist(p, out[k - 1]) > 1e-9]   # drop repeats
    return out if len(out) >= 3 and polygon_area(out) >= AREA_EPS else []


def split(poly, line):
    """Both halves (kept side first), or None if either would be empty: the cut is then refused
    and the polygon stays whole, so no sliver of area is ever lost."""
    nx, ny, c = line
    inside, outside = clip(poly, line), clip(poly, (-nx, -ny, -c))
    return (inside, outside) if inside and outside else None


def erode(poly, d):
    """Move every edge inward by d mm; [] if nothing is left."""
    if d <= 0:
        return poly
    for (ax, ay), (bx, by) in edges_of(poly):                       # the original edges
        length = math.hypot(bx - ax, by - ay)
        nx, ny = (by - ay) / length, (ax - bx) / length              # outward normal
        poly = clip(poly, (nx, ny, nx * ax + ny * ay - d))
        if not poly:
            return []
    return poly


def edges_of(poly):
    """Each edge of a polygon as (start, end), including the one that closes it."""
    return zip(poly, poly[1:] + poly[:1])


def ring_chord(x, y, mid, half_angle, radius):
    """The line across a wedge (around direction `mid`) that meets both spokes at `radius`."""
    mx, my = math.cos(mid), math.sin(mid)
    return (mx, my, mx * x + my * y + radius * math.cos(min(half_angle, math.pi / 2 - 1e-6)))


def left_of_ray(x, y, angle):
    """The half-plane counter-clockwise of the ray from (x, y) at `angle`."""
    nx, ny = math.sin(angle), -math.cos(angle)
    return (nx, ny, nx * x + ny * y)


# ── Breaking the sheet ───────────────────────────────────────────────────────

def sheet_polygon(frame):
    """The frame as a counter-clockwise polygon: four corners, or 128 points round a circle."""
    if frame.shape == "rect":
        x0, y0, x1, y1 = frame.bbox
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return [(frame.cx + frame.half_w * math.cos(a), frame.cy + frame.half_w * math.sin(a))
            for a in np.linspace(0, 2 * math.pi, 128, endpoint=False)]


def scatter_impacts(frame, rng, count):
    """(x, y, energy) for each impact. Drawn for MAX_IMPACTS and the first `count` kept, so adding
    an impact leaves the others where they were."""
    places = frame.sample(rng, MAX_IMPACTS, shrink=IMPACT_SHRINK)
    energies = 1 + ENERGY_SPREAD * rng.uniform(-1, 1, MAX_IMPACTS)
    return [(float(x), float(y), float(e)) for (x, y), e in zip(places[:count], energies[:count])]


def break_sheet(sheet, impacts, rng, params, scale) -> Shard:
    """The tree of shards: territories, then wedges, rings and splinters inside each."""
    root = Shard(sheet, level=0, impact=-1)
    made = [0]                                                  # shards made, against SHARD_CAP
    first_ring, eps = FIRST_RING * scale, STRESS_EPS * scale

    def splinter(cell, chance):
        if made[0] >= SHARD_CAP or cell.depth >= params["depth"]:
            return
        if cell.area < SMALLEST_AREA * scale**2 or rng.random() > chance:
            return
        halves = split(cell.poly, splinter_line(cell, impacts, rng, params["direction"]))
        for half in halves or []:
            made[0] += 1
            splinter(Shard(half, cell.level + 1, cell.impact, cell, cell.depth + 1),
                     chance * SPLINTER_FALLOFF)

    for i, (x, y, energy) in enumerate(impacts):
        poly = territory(sheet, impacts, i, REACH * scale)
        if not poly:
            continue
        land = Shard(poly, 1, i, root)
        angles = spoke_angles(rng, max(3, round(params["spokes"] * math.sqrt(energy))), SPOKE_JITTER)
        radii = ring_radii(rng, params["rings"], params["ring_growth"], first_ring)
        for a0, a1 in zip(angles, angles[1:] + [angles[0] + 2 * math.pi]):
            nx, ny, c = left_of_ray(x, y, a1)
            poly = clip(land.poly, left_of_ray(x, y, a0))             # left of this spoke ...
            if poly:
                poly = clip(poly, (-nx, -ny, -c))                     # ... right of the next
            if not poly:
                continue
            wedge = Shard(poly, 2, i, land)
            rings, outer = [], poly
            for r in radii:
                halves = split(outer, ring_chord(x, y, (a0 + a1) / 2, (a1 - a0) / 2, r))
                if halves:
                    inner, outer = halves
                    rings.append(inner)
            for poly in rings + [outer]:
                made[0] += 1
                ring = Shard(poly, 3, i, wedge)
                r = math.hypot(ring.centroid[0] - x, ring.centroid[1] - y)
                stress = energy * ((first_ring + eps) / (r + eps)) ** STRESS_FALLOFF
                splinter(ring, min(1.0, stress * params["splinter"]))
    return root


def territory(sheet, impacts, i, reach):
    """The sheet cut by the dividing line against every other impact (the power-diagram cell)."""
    xi, yi, ei = impacts[i]
    poly = sheet
    for j, (xj, yj, ej) in enumerate(impacts):
        d = math.hypot(xj - xi, yj - yi)
        if j == i or d < 1e-9:
            continue
        ux, uy = (xj - xi) / d, (yj - yi) / d
        t = (d * d + (ei - ej) * reach**2) / (2 * d)
        poly = clip(poly, (ux, uy, ux * xi + uy * yi + t))
        if not poly:
            return []
    return poly


def spoke_angles(rng, count, jitter):
    """`count` sorted, jittered spoke angles, with every gap of half a turn or more halved."""
    step = 2 * math.pi / count
    start = rng.uniform(0, 2 * math.pi)
    angles = sorted(start + k * step + rng.uniform(-1, 1) * jitter * step / 2 for k in range(count))
    while True:
        gaps = zip(angles, angles[1:] + [angles[0] + 2 * math.pi])
        middles = [(a0 + a1) / 2 for a0, a1 in gaps if a1 - a0 >= 0.9 * math.pi]
        if not middles:
            return angles
        angles = sorted(angles + middles)


def ring_radii(rng, count, growth, first):
    """r_k = first · growth^k, each jittered by up to ±RING_JITTER, sorted."""
    radii = [first * growth**k * (1 + RING_JITTER * rng.uniform(-1, 1)) for k in range(count)]
    return sorted(r for r in radii if r > 0)


def splinter_line(cell, impacts, rng, direction):
    """A cut near the centroid. With chance |direction| it is aimed (across the line to the impact
    for direction > 0, along it for < 0, give or take SPLIT_TURN); otherwise any angle."""
    x, y, _ = impacts[cell.impact]
    cx, cy = cell.centroid
    if rng.random() < abs(direction):
        angle = math.atan2(cy - y, cx - x) + (0 if direction > 0 else math.pi / 2)
        angle += rng.uniform(-1, 1) * SPLIT_TURN
    else:
        angle = rng.uniform(0, math.pi)
    nx, ny = math.cos(angle), math.sin(angle)                        # the cut's normal
    return (nx, ny, nx * cx + ny * cy + rng.uniform(-1, 1) * 0.25 * math.sqrt(cell.area))


def leaves_of(root):
    """The shards that were not cut further, in a fixed order."""
    out, stack = [], [root]
    while stack:
        shard = stack.pop()
        if shard.children:
            stack.extend(reversed(shard.children))
        else:
            out.append(shard)
    return out


# ── Pulling the shards apart ─────────────────────────────────────────────────

def disperse(leaves, impacts, separation, scale, flow):
    """The (dx, dy) push of every leaf shard: bloom + spray + dissolve (see the docstring)."""
    deepest = max(shard.level for shard in leaves)
    def local_time(level):
        start = STAGGER * (1 - level / deepest)
        return min(1.0, max(0.0, (separation - start) / (1 - start)))

    centroids = np.array([shard.centroid for shard in leaves])
    sources = np.array([impacts[shard.impact] for shard in leaves])
    areas = np.array([max(shard.area, 1e-6) for shard in leaves])
    times = np.array([local_time(shard.level) for shard in leaves])
    spread = SPREAD * scale

    # Bloom: every ancestor's step away from its own parent, each at its level's time. At time 1
    # the steps add up to (leaf centroid − sheet centroid); its median sets the scale.
    bloom, reach = np.zeros_like(centroids), np.zeros(len(leaves))
    for i, shard in enumerate(leaves):
        node = shard
        while node.parent is not None:
            bloom[i] += (node.centroid - node.parent.centroid) * local_time(node.level)
            node = node.parent
        reach[i] = np.hypot(*(shard.centroid - node.centroid))
    bloom *= BLOOM * spread / np.median(reach[reach > 0])

    # The flow direction at each shard.
    fx, fy = flow(centroids[:, 0], centroids[:, 1])
    flow_dir = np.column_stack([fx, fy]) / np.maximum(np.hypot(fx, fy), 1e-12)[:, None]

    # Spray: away from the impact, speed J / area, capped.
    offset = centroids - sources[:, :2]
    r = np.maximum(np.hypot(*offset.T), 1e-9)
    speed = sources[:, 2] / (r + STRESS_EPS * scale) / areas
    median_speed = np.median(speed)
    speed = np.minimum(speed, SPRAY_CAP * median_speed)
    heading = (offset / r[:, None]) * (1 - SWIRL) + flow_dir * SWIRL
    heading /= np.maximum(np.hypot(*heading.T), 1e-12)[:, None]
    spray = heading * (SPRAY * spread * speed / median_speed * times)[:, None]

    # Dissolve: along the flow, ballistic near the impact, random-walk-like at the rim.
    power = 1 - 0.5 * np.minimum(1, r / r.max())
    dissolve = flow_dir * (DISSOLVE * spread * times**power)[:, None]
    return bloom + spray + dissolve


def placer(leaves, moves, axes, squashes, frame):
    """place(i, points): shard i's points squashed, pushed, then shrunk about the frame centre
    just enough that every pushed shard fits in the frame (never enlarged)."""
    def moved(i, points):
        v = np.asarray(points, dtype=np.float64) - leaves[i].centroid
        axis = np.array([math.cos(axes[i]), math.sin(axes[i])])
        v -= np.outer(v @ axis, axis) * squashes[i]
        return leaves[i].centroid + v + moves[i]

    corners = np.vstack([moved(i, shard.poly) for i, shard in enumerate(leaves)])
    x0, y0, x1, y1 = frame.bbox
    span = corners.max(axis=0) - corners.min(axis=0)
    shrink = min(1.0, (x1 - x0) / max(span[0], 1e-9), (y1 - y0) / max(span[1], 1e-9))
    centre = np.array([frame.cx, frame.cy])
    return lambda i, points: centre + (moved(i, points) - centre) * shrink


# ── Drawing ──────────────────────────────────────────────────────────────────

def point_key(p):
    """Points closer than about SNAP get the same key."""
    return (round(float(p[0]) / SNAP), round(float(p[1]) / SNAP))


def edge_key(a, b):
    """The same key for a crack whichever shard (and direction) it is seen from."""
    ka, kb = point_key(a), point_key(b)
    return (ka, kb) if ka <= kb else (kb, ka)


def on_edge_of(sheet, point):
    """True if the point lies on the sheet's outline."""
    px, py = point
    for (ax, ay), (bx, by) in edges_of(sheet):
        ex, ey = bx - ax, by - ay
        t = min(1.0, max(0.0, ((px - ax) * ex + (py - ay) * ey) / max(ex * ex + ey * ey, 1e-18)))
        if math.hypot(px - ax - t * ex, py - ay - t * ey) <= 1e-6:
            return True
    return False


def crack_bows(leaves, sheet, rng):
    """One random number in [0, 1) per crack, in the order the cracks are first met.

    Edges along the sheet's own outline are not cracks and get none (the sheet is convex, so an
    edge lies along its outline exactly when the edge's middle does), nor do edges shorter than
    SNAP, too short to see.
    """
    bows = {}
    for shard in leaves:
        for a, b in edges_of(shard.poly):
            key = edge_key(a, b)
            middle = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            if key[0] != key[1] and key not in bows and not on_edge_of(sheet, middle):
                bows[key] = rng.random()
    return bows


_S = np.linspace(0, 1, BOW_POINTS)[:, None]
BEZIER = np.hstack([(1 - _S)**2, 2 * (1 - _S) * _S, _S**2])   # weights of start, middle, end


def bent(a, b, bows):
    """The crack from a to b as a gentle curve: a quadratic Bézier through its middle, moved
    sideways (at right angles to the crack) by 2 · CRACK_BOW · length · (bow − ½). "Sideways" is
    measured from the key's first end, so both shards bend a shared crack alike. Edges without a
    bow stay straight."""
    key = edge_key(a, b)
    (ax, ay), (bx, by) = a, b
    if key not in bows:
        return np.array([a, b], dtype=np.float64)
    side = 1 if point_key(a) == key[0] else -1
    push = side * 2 * CRACK_BOW * (bows[key] - 0.5)      # (ay − by, bx − ax) is length × normal
    middle = ((ax + bx) / 2 + push * (ay - by), (ay + by) / 2 + push * (bx - ax))
    return BEZIER @ np.array([a, middle, b], dtype=np.float64)


def outline(poly, bows):
    """A shard's closed outline, every crack bent. A shard shrunk by the gap has new edges with
    no bow, so its outline comes out straight."""
    parts = [bent(a, b, bows)[:-1] for a, b in edges_of(poly)]
    return np.vstack(parts + [parts[0][:1]])


def crack_lines(leaves, bows):
    """Every crack once, chained into as few strokes as possible.

    A chain must start or end where an odd number of cracks meet, so start walking there first,
    then anywhere; follow unused cracks until stuck.
    """
    where, meeting, seen = {}, {}, set()      # point key -> point; point key -> cracks there
    for shard in leaves:
        for a, b in edges_of(shard.poly):
            key = edge_key(a, b)
            if key in bows and key not in seen:
                seen.add(key)
                where.setdefault(point_key(a), a)
                where.setdefault(point_key(b), b)
                meeting.setdefault(key[0], []).append(key)
                meeting.setdefault(key[1], []).append(key)
    used, lines = set(), []
    for start in [p for p, cracks in meeting.items() if len(cracks) % 2] + list(meeting):
        while any(key not in used for key in meeting[start]):
            here, line = start, [np.array([where[start]])]
            while (key := next((k for k in meeting[here] if k not in used), None)) is not None:
                used.add(key)
                there = key[1] if key[0] == here else key[0]
                line.append(bent(where[here], where[there], bows)[1:])
                here = there
            lines.append(np.vstack(line))
    return lines


def hatch(poly, angle=HATCH_ANGLE, spacing=HATCH_SPACING):
    """Parallel lines `spacing` apart across a convex polygon, as [start, end] pairs.

    Line k is every point whose distance across (along n) is k · spacing; it enters and leaves
    the polygon where it crosses two of its edges.
    """
    if not poly:
        return []
    d = np.array([math.cos(angle), math.sin(angle)])              # along the lines
    n = np.array([-d[1], d[0]])                                    # across them
    corners = np.array(poly, dtype=np.float64).reshape(-1, 2)
    across = corners @ n
    lines = []
    for k in range(math.ceil(across.min() / spacing), math.floor(across.max() / spacing) + 1):
        crossings = []
        for (a, b), (da, db) in zip(edges_of(list(corners)), edges_of(list(across - k * spacing))):
            if (da <= 0 < db) or (db <= 0 < da):
                crossings.append((a + da / (da - db) * (b - a)) @ d)
        if len(crossings) >= 2 and max(crossings) - min(crossings) > spacing / 4:
            lines.append([n * k * spacing + d * min(crossings), n * k * spacing + d * max(crossings)])
    return lines
