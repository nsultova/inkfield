"""Tools for polylines: measuring, refining, cutting and thinning them.

A polyline is an (N, 2) array of points in millimetres; the pen travels from each point to the
next in a straight line. A closed polyline repeats its first point at the end.
"""
import math

import numpy as np


def length(points) -> float:
    """Total distance the pen travels: the sum of the lengths of all segments."""
    points = np.asarray(points, dtype=np.float64)
    return float(np.hypot(*np.diff(points, axis=0).T).sum())


def densify(points, max_step: float) -> np.ndarray:
    """The same line with extra points inserted so that no segment is longer than max_step.

    A segment of length L is split into n = ceil(L / max_step) equal pieces (at least one), by
    adding the points at fractions 1/n, 2/n, … (n-1)/n of the way along it. The original points
    all stay where they are; the shape of the line does not change.
    """
    points = np.asarray(points, dtype=np.float64)
    if len(points) < 2:
        return points.copy()
    steps = np.diff(points, axis=0)
    pieces = np.maximum(1, np.ceil(np.hypot(*steps.T) / max_step)).astype(int)

    # One row per output point (except the very last): which segment it lies on, and how far
    # along that segment it is, as a fraction 0, 1/n, 2/n, … (n-1)/n.
    segment = np.repeat(np.arange(len(pieces)), pieces)
    first_of_segment = np.repeat(np.cumsum(pieces) - pieces, pieces)
    fraction = (np.arange(pieces.sum()) - first_of_segment) / pieces[segment]

    inner = points[segment] + fraction[:, None] * steps[segment]
    return np.vstack([inner, points[-1:]])


def keep_where(points, inside, tol: float = 0.01) -> list[np.ndarray]:
    """The parts of the polyline that lie inside a region, as a list of polylines.

    `inside(x, y)` answers, for whole arrays of coordinates at once, which points are in the
    region. It is asked about every point of the line; each unbroken run of inside points becomes
    one part.

    Where a run ends, the segment to the next point crosses the region's boundary somewhere.
    That crossing is found by bisection: keep one end known to be inside and one known to be
    outside, test the midpoint, and replace whichever end has the same answer. Each test halves
    the gap, so after a handful of rounds the two ends are within tol of each other and the
    boundary lies between them; the part is extended to their midpoint. All crossings of the line
    are bisected together, so each round costs one call to `inside`.

    Only the given points are tested: a segment whose two ends are both outside is dropped even
    if it dips into the region in between, so densify first when the region has fine detail.
    Parts with fewer than 2 points are dropped.
    """
    points = np.asarray(points, dtype=np.float64)
    if len(points) < 2:
        return []
    is_in = np.asarray(inside(points[:, 0], points[:, 1]), dtype=bool)
    if is_in.all():
        return [points]
    if not is_in.any():
        return []

    # Segment i joins point i to point i+1; it crosses the boundary when exactly one end is in.
    crossing = np.flatnonzero(is_in[:-1] != is_in[1:])
    starts_inside = is_in[crossing]
    near = np.where(starts_inside[:, None], points[crossing], points[crossing + 1])   # inside end
    far = np.where(starts_inside[:, None], points[crossing + 1], points[crossing])    # outside end

    gap = np.hypot(*(far - near).T).max()
    rounds = math.ceil(math.log2(gap / tol)) if gap > tol else 0   # gap / 2**rounds <= tol
    for _ in range(rounds):
        middle = (near + far) / 2
        middle_in = np.asarray(inside(middle[:, 0], middle[:, 1]), dtype=bool)[:, None]
        near = np.where(middle_in, middle, near)
        far = np.where(middle_in, far, middle)
    cut_at = dict(zip(crossing.tolist(), (near + far) / 2))   # segment index -> boundary point

    # Each run of inside points, from its first index to its last, plus the cut points that
    # close it off on either side.
    run_starts = np.flatnonzero(is_in & np.concatenate([[True], ~is_in[:-1]]))
    run_ends = np.flatnonzero(is_in & np.concatenate([~is_in[1:], [True]]))
    parts = []
    for first, last in zip(run_starts.tolist(), run_ends.tolist()):
        part = [points[first:last + 1]]
        if first > 0:
            part.insert(0, cut_at[first - 1][None, :])
        if last < len(points) - 1:
            part.append(cut_at[last][None, :])
        part = np.vstack(part)
        if len(part) >= 2:
            parts.append(part)
    return parts


def simplify(points, tol: float) -> np.ndarray:
    """Fewer points, same look: drop every point that lies within tol of the simplified line.

    This is the Ramer–Douglas–Peucker method. Draw a straight segment from the first point to the
    last and find the point furthest from it. If that point is within tol, the segment is a good
    enough stand-in and everything between can go. Otherwise keep that point and repeat on the
    two halves on either side of it.

    The first and last points are always kept, so a closed line stays closed. (For a closed line
    the first "segment" has zero length; distance to it is just distance to that point, so the
    furthest point of the loop is kept and the halves proceed as usual.)
    """
    points = np.asarray(points, dtype=np.float64)
    if len(points) < 3:
        return points.copy()
    keep = np.zeros(len(points), dtype=bool)
    keep[0] = keep[-1] = True
    pending = [(0, len(points) - 1)]
    while pending:
        first, last = pending.pop()
        if last - first < 2:
            continue
        between = points[first + 1:last]
        distance = _distance_to_segment(between, points[first], points[last])
        furthest = int(np.argmax(distance))
        if distance[furthest] > tol:
            split = first + 1 + furthest
            keep[split] = True
            pending += [(first, split), (split, last)]
    return points[keep]


def _distance_to_segment(p, a, b) -> np.ndarray:
    """Distance from each point in p to the segment from a to b (not the infinite line).

    Project each point onto the line through a and b, as a fraction t of the way from a to b,
    clamp t to [0, 1] so the foot stays on the segment, and measure to that foot.
    """
    ab = b - a
    ab_squared = ab @ ab
    if ab_squared == 0:
        t = np.zeros(len(p))
    else:
        t = np.clip((p - a) @ ab / ab_squared, 0, 1)
    foot = a + t[:, None] * ab
    return np.hypot(*(p - foot).T)
