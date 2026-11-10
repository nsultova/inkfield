"""A smooth random vector field: at every point of the page, a gentle push (dx, dy).

Each component is a sum of plane waves. A plane wave sin(2π/λ · (x cos θ + y sin θ) + φ) is a
sine that ripples across the page in direction θ, with wavelength λ, shifted by phase φ. One wave
alone looks like corduroy; adding a few in different directions and sizes breaks the pattern up.

Octave k has wavelength `wavelength / 2**k` and weight 0.5**k: each octave adds finer ripples
that are half as strong. Dividing by the sum of the weights keeps each component within [-1, 1].
Directions and phases are drawn from the rng once, at construction, so the same rng state always
gives the same field, and the field is a formula, not a lookup table.
"""
import math

import numpy as np


class SmoothField:
    def __init__(self, rng, wavelength: float, octaves: int = 2):
        octave = np.arange(octaves)
        self.frequency = 2 * math.pi / (wavelength / 2.0**octave)   # radians per mm, per octave
        self.weight = 0.5**octave / (0.5**octave).sum()
        # One direction and one phase per octave, for each of the two components.
        self.direction = rng.uniform(0, 2 * math.pi, (2, octaves))
        self.phase = rng.uniform(0, 2 * math.pi, (2, octaves))

    def __call__(self, x, y) -> tuple[np.ndarray, np.ndarray]:
        """The push (dx, dy) at the points (x, y); each has the same shape as x."""
        x = np.asarray(x, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        return self._component(0, x, y), self._component(1, x, y)

    def _component(self, c, x, y) -> np.ndarray:
        total = np.zeros(np.broadcast(x, y).shape)
        for k in range(len(self.weight)):
            angle = self.direction[c, k]
            along = x * math.cos(angle) + y * math.sin(angle)   # distance travelled in direction θ
            total += self.weight[k] * np.sin(self.frequency[k] * along + self.phase[c, k])
        return total
