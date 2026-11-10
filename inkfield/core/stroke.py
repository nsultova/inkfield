"""A stroke is one continuous pen-down movement.

The pen touches the paper at the first point, travels through every point in order, and lifts
after the last one. Points are (x, y) in millimetres on the page, origin top-left, y downward.
`layer` says which pen draws it (0 is the first pen).
"""
from dataclasses import dataclass

import numpy as np


@dataclass
class Stroke:
    points: np.ndarray   # shape (N, 2), float64, millimetres
    layer: int = 0

    def __post_init__(self):
        self.points = np.asarray(self.points, dtype=np.float64)
        if self.points.ndim != 2 or self.points.shape[1] != 2:
            raise ValueError(f"stroke points must have shape (N, 2), got {self.points.shape}")
