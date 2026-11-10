"""Border: a double outline around the picture.

The outer line sits on the frame's edge; the inner line sits on the edge the pattern was clipped
to. Both are closed strokes on the first pen's layer.
"""
from inkfield.core.frame import Frame
from inkfield.core.stroke import Stroke


def border(outer: Frame, inner: Frame) -> list[Stroke]:
    return [Stroke(outer.outline()), Stroke(inner.outline())]
