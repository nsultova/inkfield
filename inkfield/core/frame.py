"""The frame is the region of the page a piece draws into: a circle or a rectangle.

Both shapes are described the same way: a centre (cx, cy) and two half-sizes. For a rectangle
these are half its width and half its height; for a circle both equal the radius. All values are
millimetres on the page, origin top-left, y downward.
"""
import math
from dataclasses import dataclass

import numpy as np

SHAPES = ("circle", "rect")
OUTLINE_STEP = 0.3   # largest gap between neighbouring points on a circle's outline, mm


@dataclass(frozen=True)
class Frame:
    shape: str           # "circle" or "rect"
    cx: float
    cy: float
    half_w: float        # circle: both equal the radius
    half_h: float

    def __post_init__(self):
        if self.shape not in SHAPES:
            raise ValueError(f"frame shape must be one of {SHAPES}, got {self.shape!r}")

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        """The smallest axis-aligned box around the frame: x0, y0, x1, y1."""
        return (self.cx - self.half_w, self.cy - self.half_h,
                self.cx + self.half_w, self.cy + self.half_h)

    @property
    def scale(self) -> float:
        """One length that says how big the frame is: its smaller half-size."""
        return min(self.half_w, self.half_h)

    def contains(self, x, y) -> np.ndarray:
        """True where (x, y) lies inside the frame; a point exactly on the edge counts as inside.

        Measure each point from the centre. In a circle it is inside when its distance is at
        most the radius; in a rectangle when it is no further than the half-size along each axis.
        Works on single numbers or on whole arrays of points at once.
        """
        dx = np.asarray(x, dtype=np.float64) - self.cx
        dy = np.asarray(y, dtype=np.float64) - self.cy
        if self.shape == "circle":
            return np.hypot(dx, dy) <= self.half_w
        return (np.abs(dx) <= self.half_w) & (np.abs(dy) <= self.half_h)

    def inset(self, d: float) -> "Frame":
        """The same shape with the same centre, its edge moved inward by d on every side."""
        return Frame(self.shape, self.cx, self.cy, self.half_w - d, self.half_h - d)

    def sample(self, rng, n: int, shrink: float = 1.0) -> np.ndarray:
        """n points scattered uniformly at random inside the frame, as an (n, 2) array.

        `shrink` scales the region about its centre first (0.9 keeps points off the outer 10 %).

        Every call takes exactly one block of n × 2 uniform numbers u, v in [0, 1) from `rng`,
        so the same rng state, shape, n and shrink always give the same points.

        Rectangle: u and v slide linearly from one edge to the other.
        Circle: v picks the angle. The radius is not simply u × R, because that crowds points
        towards the centre: a thin ring at radius r has area proportional to r, so it should
        receive that share of points. Taking r = R × sqrt(u) does exactly that.
        """
        u, v = rng.random((n, 2)).T
        if self.shape == "circle":
            radius = self.half_w * shrink * np.sqrt(u)
            angle = 2 * math.pi * v
            x = self.cx + radius * np.cos(angle)
            y = self.cy + radius * np.sin(angle)
        else:
            x = self.cx + (2 * u - 1) * self.half_w * shrink
            y = self.cy + (2 * v - 1) * self.half_h * shrink
        return np.column_stack([x, y])

    def outline(self) -> np.ndarray:
        """The frame's edge as a closed polyline: the last point repeats the first.

        A rectangle needs only its four corners. A circle is approximated by a polygon with
        enough sides that neighbouring points are at most OUTLINE_STEP apart: a side never
        exceeds the arc it replaces, so circumference / OUTLINE_STEP sides is enough.
        """
        x0, y0, x1, y1 = self.bbox
        if self.shape == "rect":
            return np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]], dtype=np.float64)
        sides = max(3, math.ceil(2 * math.pi * self.half_w / OUTLINE_STEP))
        angle = np.linspace(0, 2 * math.pi, sides + 1)
        points = np.column_stack([self.cx + self.half_w * np.cos(angle),
                                  self.cy + self.half_w * np.sin(angle)])
        points[-1] = points[0]   # close exactly, without rounding error
        return points
