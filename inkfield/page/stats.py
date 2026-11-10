"""How much a plot will draw, how far the pen travels in the air, and roughly how long it takes.

The pen starts at the plotter's home corner (0, 0). For each stroke it moves up to the stroke's
first point, lowers, draws through every point, and lifts. Drawn length is the sum of the
segments inside strokes; travel is the sum of the straight pen-up moves between them (the
return home at the end is not counted). The time uses fixed assumed speeds, so it is an
estimate, not a promise.
"""
import numpy as np

PEN_DOWN_MM_S = 25.0; PEN_UP_MM_S = 75.0; LIFT_S = 0.35


def plot_stats(strokes) -> dict:
    drawn_mm = 0.0
    travel_mm = 0.0
    pen_at = np.zeros(2)                       # home corner
    for stroke in strokes:
        points = stroke.points
        drawn_mm += float(np.hypot(*np.diff(points, axis=0).T).sum())
        travel_mm += float(np.hypot(*(points[0] - pen_at)))
        pen_at = points[-1]
    seconds = drawn_mm / PEN_DOWN_MM_S + travel_mm / PEN_UP_MM_S + len(strokes) * LIFT_S
    return {"strokes": len(strokes), "drawn_m": drawn_mm / 1000,
            "travel_m": travel_mm / 1000, "minutes": seconds / 60}
