"""Order: choose the drawing order and direction of strokes so the pen travels less in the air.

Greedy nearest end. Start with the pen at `start`. Of all strokes not yet drawn, take the one
with an end nearest the pen; if its finish is nearer than its start, draw it backwards. The pen
is now at that stroke's last point; repeat. This is not the shortest tour possible, but it is
simple and removes most of the wasted travel.

Finding the nearest end quickly. Every end is filed in a grid of square cells. Searching from
the pen, look at the pen's own cell, then the ring of cells around it, then the next ring out,
and so on. Once the best end found so far is no further than r cells' width away after ring r
has been searched, no end in a ring further out can beat it, so the search stops. When the grid
has emptied out so much that a ring search would visit more cells than there are ends left,
it is quicker to measure the distance to every remaining end directly.

Ties go to the lowest-numbered end, so the result never depends on anything but the input.
"""
import math

import numpy as np

from inkfield.core.stroke import Stroke

ENDS_PER_CELL = 2   # how many ends a grid cell holds on average when the search begins


def order(strokes, start=(0.0, 0.0)) -> list[Stroke]:
    if not strokes:
        return []
    # Stroke k has its start at end 2k and its finish at end 2k + 1.
    ends = np.array([(s.points[0], s.points[-1]) for s in strokes]).reshape(-1, 2)
    grid = EndGrid(ends)
    pen = (float(start[0]), float(start[1]))
    out = []
    for _ in strokes:
        end = grid.nearest(pen)
        k = end // 2
        grid.remove(2 * k)
        grid.remove(2 * k + 1)
        stroke = strokes[k]
        if end % 2 == 1:   # its finish is nearer: draw it backwards
            stroke = Stroke(stroke.points[::-1], stroke.layer)
        out.append(stroke)
        pen = tuple(stroke.points[-1].tolist())
    return out


class EndGrid:
    """Stroke ends filed by grid cell, so the nearest one to a point is found without a full scan."""

    def __init__(self, ends):
        self.ends = ends
        self.xy = ends.tolist()
        self.left = np.ones(len(ends), dtype=bool)   # which ends are still waiting to be drawn
        self.count = len(ends)
        x0, y0 = ends.min(axis=0)
        x1, y1 = ends.max(axis=0)
        area = max((x1 - x0) * (y1 - y0), 1e-6)
        self.cell = math.sqrt(area * ENDS_PER_CELL / len(ends))
        self.cells = {}
        for e, point in enumerate(self.xy):
            self.cells.setdefault(self.cell_of(point), []).append(e)

    def cell_of(self, point) -> tuple[int, int]:
        return math.floor(point[0] / self.cell), math.floor(point[1] / self.cell)

    def remove(self, e):
        self.cells[self.cell_of(self.xy[e])].remove(e)
        self.left[e] = False
        self.count -= 1

    def nearest(self, point) -> int:
        cx, cy = self.cell_of(point)
        best = (math.inf, -1)            # (distance, end)
        ring = 0
        while (2 * ring + 1) ** 2 <= self.count:
            for cell in ring_cells(cx, cy, ring):
                for e in self.cells.get(cell, ()):
                    best = min(best, (math.dist(point, self.xy[e]), e))
            if best[0] <= ring * self.cell:
                return best[1]
            ring += 1
        return self.nearest_by_full_scan(point)

    def nearest_by_full_scan(self, point) -> int:
        remaining = np.flatnonzero(self.left)
        distance = np.hypot(*(self.ends[remaining] - point).T)
        return int(remaining[np.argmin(distance)])   # argmin picks the first, lowest-numbered, of ties


def ring_cells(cx, cy, ring):
    """The cells exactly `ring` steps (in x or y, whichever is larger) from cell (cx, cy)."""
    if ring == 0:
        return [(cx, cy)]
    cells = [(cx + d, cy - ring) for d in range(-ring, ring + 1)]
    cells += [(cx + d, cy + ring) for d in range(-ring, ring + 1)]
    cells += [(cx - ring, cy + d) for d in range(-ring + 1, ring)]
    cells += [(cx + ring, cy + d) for d in range(-ring + 1, ring)]
    return cells
