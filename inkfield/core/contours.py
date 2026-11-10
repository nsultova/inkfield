r"""Contour tracing: the lines along which a sampled field is exactly zero (marching squares).

We know the field only at the points of a grid: field[j, i] is its value at (xs[i], ys[j]). The
grid cuts the page into small rectangular cells, each with four corners. Call a corner positive
when its value is >= 0 (zero counts as positive, so a value that is exactly zero never makes a
line of its own). A zero line must pass between a positive corner and one that is not, so:

1. Mark every grid point positive or not and give every cell a case number from its corners:
   1 for the top-left corner, 2 for top-right, 4 for bottom-right, 8 for bottom-left, added up for
   the corners that are positive. Case 0 (all below zero) and 15 (all at or above) hold no line.
   This is done for the whole grid at once with numpy; only the cells left over are looked at
   one by one, so the work grows with the length of the lines, not with the size of the grid.

2. In each remaining cell the line enters through one edge and leaves through another. The 16
   cases (+ positive corner, . not positive; y grows downward, so the top row is the smaller y):

       0       1       2       3       4       5       6       7
     .---.   +---.   .---+   +---+   .---.   +---.   .---+   +---+
     |   |   |/  |   |  \|   |---|   |  /|   |/ /|   | | |   |\  |
     .---.   .---.   .---.   .---.   .---+   .---+   .---+   .---+

       8       9      10      11      12      13      14      15
     .---.   +---.   .---+   +---+   .---.   +---.   .---+   +---+
     |\  |   | | |   |\ \|   |  /|   |---|   |  \|   |/  |   |   |
     +---.   +---.   +---.   +---.   +---+   +---+   +---+   +---+

   Where on an edge does the line cross? If the corner values are a and b, the straight line
   between them is zero a fraction t = a / (a - b) of the way from a to b.

   Cases 5 and 10 are saddles: two opposite corners are positive, so the cell holds two
   segments, and which pairs of edges they join is ambiguous. We decide by the mean of the four
   corners, our guess for the value at the centre. A positive centre joins the two positive
   corners, so the segments cut off the other two corners; otherwise the positive corners are
   cut off (the pictures above show this second choice).

3. Every grid edge has a unique integer id, shared by the two cells that touch it. The segment
   that leaves one cell through an edge is continued by the segment that enters the next cell
   through the same edge. Starting from any segment we follow these shared edges forward, then
   backward, until the line closes on itself or stops at the border of the grid or of the
   examined cells. A closed line repeats its first point at the end.
"""
import math

import numpy as np

# Segments in each case, as pairs of cell edges ("left", "top") meaning: from the crossing on the
# left edge to the crossing on the top edge. Cases 0 and 15 have none; the saddles 5 and 10 are
# listed separately because they depend on the sign at the centre.
SEGMENTS = {
    1: [("left", "top")],      2: [("top", "right")],     3: [("left", "right")],
    4: [("right", "bottom")],  6: [("top", "bottom")],    7: [("left", "bottom")],
    8: [("left", "bottom")],   9: [("top", "bottom")],    11: [("right", "bottom")],
    12: [("left", "right")],   13: [("top", "right")],    14: [("left", "top")],
}
SADDLE_SEGMENTS = {   # (case, centre is positive) -> segments
    (5, True): [("top", "right"), ("left", "bottom")],    # cut off the two . corners
    (5, False): [("left", "top"), ("right", "bottom")],   # cut off the two + corners
    (10, True): [("left", "top"), ("right", "bottom")],
    (10, False): [("top", "right"), ("left", "bottom")],
}


def trace_zero(field, xs, ys, cells=None) -> list[np.ndarray]:
    """The lines along field == 0, as a list of (n, 2) arrays of points (x, y).

    field[j, i] is the value at (xs[i], ys[j]). If `cells` is given (a bool array with one entry
    per cell, shape (len(ys) - 1, len(xs) - 1)), only the cells marked True are examined. Cells
    with a corner that is not a finite number are skipped.
    """
    field = np.asarray(field, dtype=np.float64)
    xs = np.asarray(xs, dtype=np.float64)
    ys = np.asarray(ys, dtype=np.float64)

    # Step 1, for the whole grid at once: the case number of every cell.
    positive = field >= 0
    case = (1 * positive[:-1, :-1] + 2 * positive[:-1, 1:]
            + 4 * positive[1:, 1:] + 8 * positive[1:, :-1])
    finite = np.isfinite(field)
    all_finite = finite[:-1, :-1] & finite[:-1, 1:] & finite[1:, 1:] & finite[1:, :-1]
    examine = (case != 0) & (case != 15) & all_finite
    if cells is not None:
        examine &= np.asarray(cells, dtype=bool)
    rows, cols = np.nonzero(examine)

    # Step 2, cell by cell: the segments, as pairs of edge ids, and the crossing point on each edge.
    columns = len(xs)
    first_vertical = len(ys) * (columns - 1)   # horizontal edges come first, then vertical ones

    def horizontal_edge(j, i):   # from grid point (j, i) to (j, i + 1)
        return j * (columns - 1) + i, (j, i), (j, i + 1)

    def vertical_edge(j, i):     # from grid point (j, i) to (j + 1, i)
        return first_vertical + j * columns + i, (j, i), (j + 1, i)

    def crossing(a, b):
        """The point between grid points a and b (each a (j, i) pair) where the field is zero."""
        value_a, value_b = float(field[a]), float(field[b])
        t = value_a / (value_a - value_b)
        x = xs[a[1]] + t * (xs[b[1]] - xs[a[1]])
        y = ys[a[0]] + t * (ys[b[0]] - ys[a[0]])
        return float(x), float(y)

    point_on_edge = {}   # edge id -> crossing point
    segments = []        # (edge id, edge id)
    for j, i, cell_case in zip(rows.tolist(), cols.tolist(), case[rows, cols].tolist()):
        edges = {
            "top": horizontal_edge(j, i),
            "bottom": horizontal_edge(j + 1, i),
            "left": vertical_edge(j, i),
            "right": vertical_edge(j, i + 1),
        }
        if cell_case in (5, 10):
            centre = (field[j, i] + field[j, i + 1] + field[j + 1, i + 1] + field[j + 1, i]) / 4
            pairs = SADDLE_SEGMENTS[cell_case, bool(centre >= 0)]
        else:
            pairs = SEGMENTS[cell_case]
        for pair in pairs:
            ids = []
            for name in pair:
                edge_id, a, b = edges[name]
                if edge_id not in point_on_edge:
                    point_on_edge[edge_id] = crossing(a, b)
                ids.append(edge_id)
            segments.append((ids[0], ids[1]))

    # Step 3: chain the segments into lines through their shared edges. Where the field is exactly
    # zero at a grid point, the edges that meet there all cross at that same point, so it would
    # appear several times in a row; keep it once. A line that shrinks to a single point is dropped.
    lines = []
    for chain in _chain(segments):
        points = [point_on_edge[e] for e in chain]
        points = [p for k, p in enumerate(points) if k == 0 or p != points[k - 1]]
        if len(points) >= 2:
            lines.append(np.array(points))
    return lines


def _chain(segments) -> list[list[int]]:
    """Join segments (pairs of edge ids) that share an edge into chains of edge ids."""
    touching = {}   # edge id -> the one or two segments that end on it
    for k, (start, end) in enumerate(segments):
        touching.setdefault(start, []).append(k)
        touching.setdefault(end, []).append(k)
    used = [False] * len(segments)

    def extend(chain):
        """Keep adding the unused segment that continues from the last edge of the chain."""
        while True:
            edge = chain[-1]
            following = [k for k in touching[edge] if not used[k]]
            if not following:
                return
            used[following[0]] = True
            start, end = segments[following[0]]
            chain.append(end if start == edge else start)

    chains = []
    for k, (start, end) in enumerate(segments):
        if used[k]:
            continue
        used[k] = True
        chain = [start, end]
        extend(chain)                  # forward
        if chain[0] != chain[-1]:      # not closed: also grow from the other end
            chain.reverse()
            extend(chain)
        chains.append(chain)
    return chains


def trace_whole_numbers(phase, xs, ys, cells=None) -> list[np.ndarray]:
    """The lines where phase is a whole number (..., -1, 0, 1, 2, ...), all in one pass.

    sin(2π·phase) is zero exactly where phase is a whole or a half number, and cos(2π·phase) is
    positive only within a quarter of a whole number. So we trace the zeros of sin(2π·phase),
    examining only cells whose four corners all have cos(2π·phase) > 0: that keeps the whole
    numbers and drops the halves.

    We take sin and cos of the distance to the nearest whole number, phase - round(phase), rather
    than of phase itself. The values are the same, but where phase is a whole number this
    distance is exactly zero, while 2π·phase in floating point is not quite a multiple of 2π and
    its sine comes out as a tiny number of either sign.

    This only works if the grid is fine enough: phase must change by less than about 0.18 across
    a cell diagonal. Otherwise a cell crossed by a whole-number line can have a corner where
    cos(2π·phase) <= 0, the cell is dropped, and the line gets a gap.
    """
    phase = np.asarray(phase, dtype=np.float64)
    offset = phase - np.round(phase)   # signed distance to the nearest whole number
    near_whole = np.cos(2 * math.pi * offset) > 0
    corners_near_whole = (near_whole[:-1, :-1] & near_whole[:-1, 1:]
                          & near_whole[1:, 1:] & near_whole[1:, :-1])
    if cells is not None:
        corners_near_whole &= np.asarray(cells, dtype=bool)
    return trace_zero(np.sin(2 * math.pi * offset), xs, ys, cells=corners_near_whole)
