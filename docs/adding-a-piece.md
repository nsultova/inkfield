# Adding a piece

A piece is one Python file in `inkfield/pieces/`. It says which controls it has and how to
turn their values into pen strokes. Everything else (clipping, the border, the page, the SVG,
the statistics, the app) is done for it.

Drop a new file into `inkfield/pieces/` and it appears in the app and in `uv run inkfield list`.
Nothing has to be registered. Files whose name starts with `_` are skipped.

This guide is written so that it can be followed step by step, by a person or by another
Claude session.


## 1. The contract

A piece file contains these four things, in this order, and nothing else:

1. **A module docstring.** It explains the idea before any code: what the reference image
   shows, what process makes it, the formula that came out of that, and what each control
   means. Write the formula out. Someone should be able to learn the idea from the docstring
   alone.
2. **`META`**, a `Meta` from `inkfield.core.piece`:
   - `slug`: the name used on the command line and in URLs, for example `"chemical-waves"`.
     Letters, digits, `-` and `_` only. Two pieces may not share a slug.
   - `title` and `subtitle`: shown in the list of pieces.
   - `framed_shape`: `"circle"` or `"rect"`. In "framed" composition the app gives the piece
     the largest frame of this shape that fits inside the margin.
   - `info`: a few sentences shown behind the *i* button in the app.
3. **`PARAMS`**, a list of controls from `inkfield.core.controls`:
   - `Slider(name, label, min, max, step, default, unit="")`
   - `Choice(name, label, options, default)`, where `options` is a tuple of strings
   - `Toggle(name, label, default)`
4. **`generate(params, frame, rng)`**, which returns a list of `Stroke`.
   - `params` is a dict from control name to value. It is always complete and valid: values
     are clamped to the slider range, and a slider whose step is a whole number gives an `int`.
   - `frame` is a `Frame` from `inkfield.core.frame`: the region to fill, in millimetres on
     the page (origin top-left, y downward).
   - `rng` is a `numpy.random.Generator`, already seeded from the seed in the app.
   - Each `Stroke` holds an (N, 2) array of points in millimetres. The pen goes down at the
     first point and lifts after the last one. A closed line repeats its first point at the end.

`generate` must be a pure function: the same `params`, `frame` and `rng` state must always give
the same strokes. That is what makes "same seed, same settings, same SVG" true.


## 2. What a piece must not do

- **No clipping.** Strokes may run outside the frame. The finishing stage clips them to the
  frame afterwards.
- **No border.** The border is a finishing effect with its own toggle.
- **No imports other than `inkfield.core` and numpy.** (`math` and `dataclasses` from the
  standard library are tolerated.) No files, no network, nothing from `inkfield.server` or
  `inkfield.web`. A test, `tests/test_import_rule.py`, checks this.
- **No randomness other than `rng`.** No `random` module, no `np.random.…` functions, no time,
  no values that depend on the computer. Take every random number from the `rng` you were given.
  Draw them in a fixed order, so the same seed gives the same picture.


## 3. A complete example

Concentric circles around a point near the middle of the frame. Save this as
`inkfield/pieces/rings.py`:

```python
"""Rings: concentric circles around one point, the smallest useful piece.

The idea
--------
Drop a stone into still water and rings spread out from where it fell. Here the rings are
frozen: ring k (k = 1, 2, ..., rings) is the circle of radius

    r_k = k · spacing

around a centre c. The centre is the middle of the frame, moved a little at random, so each
seed gives a slightly different picture. A circle is drawn as a closed polyline through the
points (c_x + r_k · cos θ, c_y + r_k · sin θ), with θ going from 0 to 2π in small steps.

The controls
------------
Rings      how many circles.
Spacing    the distance between neighbouring circles, in mm.
"""
import numpy as np

from inkfield.core.controls import Slider
from inkfield.core.piece import Meta
from inkfield.core.stroke import Stroke

META = Meta(slug="rings", title="Rings", subtitle="Concentric circles", framed_shape="circle",
            info="Circles of radius k · spacing around one centre near the middle.")

PARAMS = [
    Slider("rings",   "Rings",   1, 40, 1,   12),
    Slider("spacing", "Spacing", 1, 15, 0.5, 6, " mm"),
]

POINT_GAP = 0.5   # largest distance between neighbouring points on a circle, mm


def generate(params, frame, rng) -> list[Stroke]:
    cx, cy = frame.sample(rng, 1, shrink=0.1)[0]   # a random point near the middle
    strokes = []
    for k in range(1, params["rings"] + 1):
        radius = k * params["spacing"]
        steps = max(16, int(np.ceil(2 * np.pi * radius / POINT_GAP)))
        angle = np.linspace(0, 2 * np.pi, steps + 1)
        points = np.column_stack([cx + radius * np.cos(angle), cy + radius * np.sin(angle)])
        points[-1] = points[0]                      # close the circle exactly
        strokes.append(Stroke(points))
    return strokes
```

Note what it does not do: the outer rings may leave the frame, and that is fine, because they
are clipped later. The only random number comes from `rng`, through `frame.sample`.

`tests/test_docs_example.py` copies this block into a temporary package and renders it, so the
example here cannot silently go out of date.


## 4. How to check it

Run every command from the repository root.

1. The piece is found:

   ```sh
   uv run inkfield list
   ```

   It prints one line per piece: the slug, a tab, the title.

2. Render it to an SVG file. Write check renders **outside the repository** (for example into
   `/tmp`) so they are never committed:

   ```sh
   uv run inkfield render rings -o /tmp/x.svg
   uv run inkfield render rings --seed 3 --set rings=20 --set spacing=4 -o /tmp/x.svg
   ```

   It prints the number of strokes, metres drawn, metres of pen-up travel and an estimate of
   the plot time. Use `--set name=value` once per control. The other options are `--seed`, the
   page (`--composition`, `--format`, `--orientation`, `--margin`, `--pen`) and the finishing
   effects (`--wobble`, `--no-border`); see `uv run inkfield render --help`.

3. Look at it. Open the SVG in a browser, or start the studio with `uv run inkfield`, pick the
   piece and move its sliders. Check that the picture matches the docstring, that every control
   changes the picture, and that the same seed always gives the same picture.

4. Run the tests:

   ```sh
   uv run pytest -q
   ```

   The import rule test fails if the piece imports something it may not. It is a good idea to
   add `tests/test_<piece>.py` as well, like `tests/test_chemical_waves.py`: the same seed gives
   the same strokes, every control changes the picture, and one test for the property the
   piece is really about.


## 5. Tools in `inkfield.core`

These are the building blocks a piece may use. Each file starts with a docstring that explains
its idea.

| Tool | What it is for |
|------|----------------|
| `stroke.Stroke(points, layer=0)` | One pen-down line: an (N, 2) array of points in mm. `layer` is the pen (always 0 for now). |
| `piece.Meta(slug, title, subtitle, framed_shape, info)` | The piece's name and description. |
| `controls.Slider`, `controls.Choice`, `controls.Toggle` | Declare the controls in `PARAMS`. |
| `frame.Frame` | The region to fill. `shape`, `cx`, `cy`, `half_w`, `half_h`; `bbox` (x0, y0, x1, y1); `scale` (its smaller half-size, a length to measure sizes against); `contains(x, y)` (works on arrays); `inset(d)`; `sample(rng, n, shrink=1.0)` (n random points inside, as an (n, 2) array); `outline()` (the edge as a closed polyline). |
| `noise.SmoothField(rng, wavelength, octaves=2)` | A smooth random vector field. Calling `field(x, y)` gives a push `(dx, dy)`, each between -1 and 1. Good for making regular shapes a little uneven. |
| `contours.trace_zero(field, xs, ys, cells=None)` | Lines where a field sampled on a grid is zero (marching squares). `field[j, i]` is the value at `(xs[i], ys[j])`. |
| `contours.trace_whole_numbers(phase, xs, ys, cells=None)` | Lines where a sampled field is a whole number (..., -1, 0, 1, ...), all in one pass. Needs a grid fine enough that the field changes by less than about 0.18 along a cell side. |
| `polyline.length(points)` | Length of a polyline in mm. |
| `polyline.densify(points, max_step)` | The same line with extra points, so no segment is longer than `max_step`. |
| `polyline.keep_where(points, inside, tol=0.01)` | The parts of a line inside a region given as a test `inside(x, y)`; the cuts are placed exactly on the region's edge. Use it to cut lines at a boundary of the piece's own (not the frame: clipping to the frame is done for you). |
| `polyline.simplify(points, tol)` | Fewer points, same look (Ramer–Douglas–Peucker). |
| `rng.make_rng(seed, stream="")` | How the app makes the `rng` it hands to `generate`. A piece never calls it; it is useful in tests: `make_rng(7, "piece")` gives the same `rng` as seed 7 in the app. |

`inkfield/pieces/chemical_waves.py` is a finished piece that uses most of these. Read it as a
model: the docstring first, then the controls, then `generate` as a short list of numbered
steps, each step a small function below it.
