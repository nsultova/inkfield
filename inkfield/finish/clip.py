"""Clip to frame: keep only the parts of each stroke that lie inside the frame.

A stroke is cut exactly where it crosses the frame's edge, with a new point on the edge, rather
than by dropping whole points. Points are first spread at most 1 mm apart, so a long straight
segment that crosses the edge gets cut where it crosses, not at its far vertex.
"""
from inkfield.core.frame import Frame
from inkfield.core.polyline import densify, keep_where
from inkfield.core.stroke import Stroke

MAX_STEP = 1.0   # largest gap between points before clipping, mm


def clip(strokes, frame: Frame) -> list[Stroke]:
    return [Stroke(part, s.layer)
            for s in strokes
            for part in keep_where(densify(s.points, MAX_STEP), frame.contains)]
