"""Tidy: join strokes that meet, drop crumbs, and thin out points nobody would see.

1. Join. Where one stroke ends within `join_tol` of where another starts or ends, the pen could
   carry on without lifting, so the two become one stroke (flipping one if needed). Joins repeat
   until no two loose ends of the same layer lie that close. A closed stroke (its own two ends
   within `join_tol`) is never joined to anything: it is already a complete loop.
2. Drop every stroke shorter than `min_length`: too short to see, but each costs a pen lift.
3. Simplify every stroke with tolerance `simplify_tol`, far below the width of any pen.

How the joining works. Number the ends: stroke k has its start at end 2k and its finish at end
2k + 1. First find every pair of ends, from different open strokes of the same layer, that lie
within `join_tol`. Then pair them up, closest pairs first, each end used at most once: that
gives every end at most one partner. Following partners from stroke to stroke now traces whole
chains, each of which becomes one stroke. Because every close pair whose two ends were both
still free got paired, no two loose ends of the result lie within `join_tol` of each other, which
is what joining over and over would also reach.

Finding close pairs without comparing every end with every other: lay a grid of square cells
`join_tol` wide over the page and drop each end into its cell. Two ends within `join_tol` lie in
the same or in neighbouring cells, so each end only needs to look at its own cell and the eight
around it.
"""
import math

import numpy as np

from inkfield.core.polyline import length, simplify
from inkfield.core.stroke import Stroke

NEIGHBOUR_CELLS = [(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]


def tidy(strokes, min_length=1.5, join_tol=0.1, simplify_tol=0.02) -> list[Stroke]:
    joined = join(strokes, join_tol)
    kept = [s for s in joined if length(s.points) >= min_length]
    return [Stroke(simplify(s.points, simplify_tol), s.layer) for s in kept]


def join(strokes, tol: float) -> list[Stroke]:
    """Strokes whose ends meet within tol, joined into longer strokes (see the module notes)."""
    if not strokes:
        return []
    ends = np.array([(s.points[0], s.points[-1]) for s in strokes]).reshape(-1, 2)
    is_open = np.hypot(*(ends[0::2] - ends[1::2]).T) > tol
    layers = [s.layer for s in strokes]

    # Pair up close ends, closest first; skip ends of one stroke, of closed strokes, of different
    # layers, and ends that already have a partner.
    partner = [-1] * len(ends)
    for a, b in close_pairs(ends, tol):
        sa, sb = a // 2, b // 2
        if (sa != sb and is_open[sa] and is_open[sb] and layers[sa] == layers[sb]
                and partner[a] == -1 and partner[b] == -1):
            partner[a], partner[b] = b, a

    # Trace each chain once, in the order of its lowest-numbered stroke.
    visited = [False] * len(strokes)
    out = []
    for k in range(len(strokes)):
        if visited[k]:
            continue
        chain = trace_chain(chain_start(k, partner), partner, visited)
        if len(chain) == 1 and not chain[0][1]:
            out.append(strokes[k])
            continue
        points = [strokes[s].points[::-1] if backwards else strokes[s].points for s, backwards in chain]
        out.append(Stroke(np.vstack(points), strokes[k].layer))
    return out


def close_pairs(ends, tol: float) -> list[tuple[int, int]]:
    """Every pair of ends (a, b), a < b, at most tol apart: closest first, ties by number."""
    ends = ends.tolist()
    cells = {}
    for e, (x, y) in enumerate(ends):
        cells.setdefault((math.floor(x / tol), math.floor(y / tol)), []).append(e)
    found = []
    for (cx, cy), members in cells.items():
        for dx, dy in NEIGHBOUR_CELLS:
            for b in cells.get((cx + dx, cy + dy), ()):
                for a in members:
                    if a < b:
                        distance = math.dist(ends[a], ends[b])
                        if distance <= tol:
                            found.append((distance, a, b))
    return [(a, b) for _, a, b in sorted(found)]


def chain_start(k, partner) -> int:
    """The loose end where the chain through stroke k begins (stroke k's start, for a loop).

    Walk backwards from stroke k's start: hop to its partner, cross that stroke to its far end,
    and repeat until an end has no partner, or the walk comes back round to stroke k.
    """
    end = 2 * k
    while partner[end] != -1:
        end = partner[end] ^ 1          # the far end of the neighbouring stroke
        if end // 2 == k:
            return 2 * k
    return end


def trace_chain(end, partner, visited) -> list[tuple[int, bool]]:
    """The strokes of a chain in drawing order, entering at `end`, as (stroke, drawn backwards)."""
    chain = []
    while True:
        stroke = end // 2
        visited[stroke] = True
        chain.append((stroke, end % 2 == 1))   # entering at its finish means drawing it backwards
        end = partner[end ^ 1]                  # leave by the other end, on to its partner
        if end == -1 or visited[end // 2]:
            return chain
