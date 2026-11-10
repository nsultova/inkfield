# inkfield: a studio for plottable procedural art

Design for project 1 of 3. Date: 2026-11-10. "inkfield" is a working title.

Decisions are marked **(Neda)** where the user stated them and **(my call)** where
Claude chose and the user has not explicitly agreed. Anything marked "my call" can be
overturned without discussion.

## 1. Intent

Neda gives Claude an image, usually a photograph of some natural or mathematical
pattern. Claude works out what process makes the pattern and writes a small generator
that produces endless new pictures following the same rules. The generator appears in
a browser app where Neda explores it with sliders, keeps promising candidates, and
exports an SVG to draw on an AxiDraw A3 pen plotter.

Two things matter as much as the pictures:

- **The code is a learning artefact.** Neda reads the math to understand how a piece
  works. The logic of a piece must be readable on its own, apart from all plumbing.
- **The app is a stable host.** New pieces arrive regularly and their controls differ
  a lot. Adding a piece must not require touching the app.

This is also a deliberate fresh start. An earlier tool with similar goals existed and
was discarded; nothing from it is to be reused or assumed. Concretely:

- `steering-material/` is reference only. Its images are inputs for pieces (the
  Belousov–Zhabotinsky ones now, the others later). Its two `.py` scripts and two
  `ui-example-*.png` screenshots are older experiments: not to be ported, and the
  mockup overrides them wherever they differ.
- The existing `.venv` and `.pytest_cache` in the project root belong to the discarded
  tool. The builder lets `uv` replace `.venv`. (My call.)

## 2. The three projects and what this document covers

1. **The app plus the first piece, "Chemical waves".** This document.
2. **Drawing mode.** An image of a flower, hands and the like turned into contours and
   hatching. Later; reuses the app.
3. **A Claude Code skill** that packages the "image → new piece" procedure. Later,
   after a few pieces have been made by hand.

Project 1 must leave room for 2 and 3 (see section 12) but build neither.

## 3. Goals

- Launch with one command, use in a browser on localhost.
- A piece is one Python file that declares its controls and contains its math. The app
  builds the control panel from that declaration.
- Live preview: moving a slider redraws the plot quickly enough to feel direct.
- Page awareness: A4, A3 and square sheets, portrait or landscape, with a margin.
- Two compositions for every piece: **framed** (the piece's own shape, a round dish for
  Chemical waves) and **fill page** (the pattern fills the sheet inside the margin).
- Shared finishing effects that work on every piece.
- Keep candidates while exploring, return to them later, remove them, export SVG.
- The exported SVG is directly plottable: real millimetres, pen strokes only.
- Same piece, seed, settings and page always give the identical SVG.

## 4. Non-goals for project 1

- Driving the AxiDraw. The app stops at SVG export. **(Neda)**
- Drawing mode and the skill (projects 2 and 3).
- Dashed or dotted lines. Removed from the mockup at Neda's request "for now"; the
  finishing stage must make it easy to add later as real stroke geometry.
- A user interface for multiple pens. Strokes carry a layer number so this can come
  later, but everything is on one layer now.
- Uploading images into the app. Images go to Claude in a coding session, not to the
  app. No AI calls happen while the app runs.

## 5. Anti-goals

These would make the result a failure even if it works:

- Piece math mixed with server, UI or file code.
- A piece that needs changes to the front end to show its controls.
- An SVG that relies on clip paths, fills, transforms or pixel units to look right.
  What the file contains must be exactly what the pen draws.
- A front end that needs a build step or a package manager.
- Sliders that feel laggy at default settings.
- Clever, compressed math that is fast but cannot be read.

## 6. How it gets made

All **(my call)**; Neda offered Python or Rust and was open to suggestions.

- **Python 3.12 or newer, managed with `uv`.** Chosen over Rust because a new piece is
  written every session and Neda reads the math; iteration speed and legibility matter
  more than raw speed.
- **numpy** for grid computations. It is the one heavy dependency in the math and keeps
  field evaluation fast enough for live sliders. No scipy, no scikit-image, no contour
  library: contour tracing is written in this project so it can be read.
- **FastAPI and uvicorn** for the local server.
- **Front end: plain HTML, CSS and JavaScript, no build step,** served by the server.
- **pytest** for tests.
- `uv` creates the virtual environment at `.venv` in the project root, which matches
  Neda's habit of activating `.venv`.
- Target machine: Neda's laptop, an AMD Ryzen 5 5500U (6 cores, 12 threads). Speed
  targets below refer to it.

## 7. Structure

One package, split by what a reader would want to open:

```
inkfield/
  pieces/        one file per piece: its controls and its math, nothing else
  core/          shared, readable building blocks for pieces
                 (seeded randomness, sampling a field on a grid, tracing contour
                 lines, basic polyline geometry, smooth noise)
  finish/        effects that turn strokes into strokes
  page/          paper formats, margins, frames; SVG writing; plot statistics
  server/        HTTP API and candidate storage
  web/           the front end (static files)
tests/
docs/            README-level docs: running the app, adding a piece
candidates/      kept candidates, created at runtime, ignored by git
```

Dependency rule, enforced by a test: `pieces/`, `core/`, `finish/` and `page/` never
import from `server/` or `web/`, and do no file or network access. `pieces/` may import
only from `core/` and numpy.

Exact file names inside these folders are left to the builder.

## 8. The data that flows through

```
piece.generate  →  strokes  →  finishing effects  →  strokes  →  SVG + statistics
```

- **Stroke:** one pen-down path, a sequence of (x, y) points in millimetres on the
  page, plus a layer number (always 0 for now). Origin top-left, y downward, matching
  SVG.
- **Frame:** the region a piece must fill, handed to the piece by the app. It is either
  a circle or a rectangle, in page millimetres, and offers: its bounding box, an
  "is this point inside" test that works on numpy arrays, and a reference length (half
  its shorter dimension) so pieces can express sizes relative to the frame.
- **Framed versus fill page:** each piece names its framed shape (circle for Chemical
  waves). In "framed" the app passes the largest such shape that fits inside the
  margin, centred. In "fill page" it passes the rectangle inside the margin. The piece
  does not know or care about paper formats.

### The piece contract

A piece file contains, in this order, and nothing else:

1. A module docstring explaining the model in plain language with the equations: what
   the reference image shows, what process produces it, how that became a formula, and
   what each control means physically.
2. `META`: slug, title, subtitle, framed shape, and the short info text shown behind
   the *i* button in the app.
3. `PARAMS`: a list of control declarations. Three kinds are enough: a slider (name,
   label, min, max, step, default, optional unit), a choice (a few named options) and
   a toggle.
4. `generate(params, frame, rng) -> strokes`. A pure function. All randomness comes
   from the `rng` it is given, which is seeded from the seed in the UI.

Pieces are discovered automatically: adding a file to `pieces/` makes it appear in the
app. A test proves this with a tiny fake piece.

Image inputs are not part of this contract yet. When drawing mode arrives, the plan
is a fourth control kind, "image", whose value the app or command line loads and hands
to `generate` as a numpy array, so pieces still never touch files. Nothing for that is
built now; the builder only avoids choices that would rule it out. (My call.)

A piece clips nothing and decorates nothing. It may produce strokes that leave the
frame; the finishing stage clips them.

## 9. The first piece: Chemical waves

Reference images: `steering-material/Belousov-Zhabotinsky_0{0,1,3,4}.png`. They show
the Belousov–Zhabotinsky reaction in a petri dish: concentric "target" rings, spirals,
and cusped seams where two wave systems meet. Default behaviour is to make new dishes
in the same world, not to copy a particular dish. **(Neda)**

### The model (my call, shown working in the mockup, liked by Neda)

Geometric, not a chemical simulation:

- A number of **pacemakers** sit at random points. Each starts emitting waves after its
  own delay. Waves travel at the same speed everywhere.
- The time at which pacemaker *i* first reaches point *x* is
  `arrival_i(x) = delay_i + distance(x, pacemaker_i)`. A point belongs to whichever
  pacemaker reaches it first.
- At the moment of the snapshot (the **elapsed time**), a point that its pacemaker
  reached `elapsed - arrival` ago has seen `(elapsed - arrival) / wavelength` waves go
  by. Call that number the phase. **Pen lines are where the phase is a whole number.**
  Phase 0 is the outermost front; points not yet reached have no lines.
- A **spiral** is the same thing with a twist: its phase has
  `± angle around the core / 2π` added, which turns each ring into one arm of an
  Archimedean spiral. Clockwise or anticlockwise is random per spiral.
- **Seams:** colliding waves annihilate, so each pacemaker's lines stop at the border of
  its territory. Between two ring systems of equal wavelength the lines from both sides
  meet at the same points, which gives the cusps seen in the photographs.
- **Medium unevenness:** a smooth, low-frequency distortion of space before distances
  are measured, so rings are slightly lumpy as in a real dish.

### Controls (defaults from the mockup)

| Control | Range | Default | Meaning |
|---|---|---|---|
| Pacemakers | 1 to 24 | 9 | how many wave sources |
| Spiral share | 0 to 1 | 0.30 | probability that a source is a spiral |
| Wavelength | 2 to 14 mm | 5.5 | distance between successive fronts |
| Elapsed time | 0.08 to 2 | 0.42 | how far waves have travelled, as a multiple of the frame's reference length; small values leave empty medium between blobs, large values fill the frame |
| Start stagger | 0 to 1 | 0.70 | how spread out the start delays are, as a fraction of elapsed time |
| Medium unevenness | 0 to 1 | 0.20 | strength of the spatial distortion, relative to wavelength |

### Quality requirements beyond the mockup

The mockup's math is a throwaway sketch with known flaws. The real piece must fix them:

- **Lines reach the seam.** A line ends within 0.3 mm of the true territory border, not
  a grid cell short of it. Where lines from two sides meet at the same point they
  should be joined into one stroke (the join effect in section 10 may do this).
- **Clean spiral cores.** No scribble at the centre of a spiral: the arm ends cleanly
  at a small core radius.
- **Smooth curves.** No visible polygon corners from the sampling grid at A3 size with
  a 0.3 mm pen.
- **No stray fragments.** Strokes shorter than about 1.5 mm are dropped.

How these are achieved is the builder's choice. One workable route: trace each
pacemaker's own smooth phase field separately, then cut its lines exactly where
another pacemaker's arrival time becomes earlier.

### Speed

At default settings on A4 a full redraw (math, finishing, SVG) should take roughly
200 ms or less on Neda's machine, and A3 fill-page with 24 pacemakers under about a
second. Build the simple path first (one full-quality render per change, latest wins) and
measure. Only if the quality requirements cannot be met at that speed, the builder may
render a coarser preview while a slider is being dragged and the full-quality version
on release, as long as kept and exported files are always full quality.

## 10. Finishing effects

Shared by all pieces, applied in a fixed order after the piece runs. Effects that have
user controls declare them the same way pieces do, so the panel builds itself.

In order:

1. **Hand wobble** (slider 0 to 1, default 0): a smooth, small displacement of points
   so lines look hand-drawn. Deterministic for a given seed.
2. **Clip to frame:** cut every stroke exactly at the frame edge (true geometric
   clipping, with a new point on the edge, not dropping whole points).
3. **Border** (on/off, default on): a double outline of the frame, a circle or a
   rectangle. The outer line sits on the frame edge; the pattern is clipped to the
   inner line, inset by about 3.5 % of the frame's reference length.
4. **Tidy:** drop tiny strokes, join strokes whose ends coincide, simplify points that
   add nothing visible (tolerance well below pen width).
5. **Order:** sort and flip strokes to shorten pen-up travel (a simple greedy
   nearest-end pass is enough).

Tidy and order have no controls.

## 11. Page, SVG and statistics

- **Formats:** A4 (210 × 297 mm), A3 (297 × 420 mm), Square (250 × 250 mm, my call on
  the size). Portrait or landscape. **(Neda: A4, A3, square)**
- **Margin:** slider, 5 to 40 mm, default 16.
- **Pen:** 0.2, 0.3, 0.5 or 0.8 mm, default 0.3. It sets the stroke width in the
  preview and the SVG so the preview shows true line weight. It does not change the
  geometry.
- **SVG:** `width` and `height` in mm, `viewBox` in the same numbers, so one user unit
  is one millimetre. One `<path>` per stroke, no fill, grouped in one Inkscape-style
  layer group per layer number so the Inkscape AxiDraw plugin and saxi see layers.
  Coordinates with fixed decimals. No clip paths, transforms, fills, text or styles
  that change what is drawn. The piece slug, seed and all settings are embedded as
  JSON in the SVG's `<metadata>`, so a file can always be traced back and reloaded.
- **Statistics** shown under the paper: page size, stroke count, metres of drawn line,
  metres of pen-up travel, estimated plot time. The time estimate uses fixed assumed
  speeds and is labelled as approximate.

## 12. The app

The approved look and layout is the mockup
`docs/superpowers/specs/2026-11-10-inkfield-mockup.html` (open it in a browser; it is
self-contained and interactive). Follow its layout, proportions, typography, colours
and tone. Its JavaScript math and its line preview are throwaway and must not be
ported: in the real app all geometry comes from Python.

### Layout **(Neda approved the mockup)**

- **Top bar:** name; seed field; reroll button; "Keep candidate"; "Export SVG".
- **Left rail:** list of pieces, title and subtitle. Only real pieces; no placeholders.
- **Centre:** the sheet at true proportions on a neutral desk, the margin as a faint
  dashed guide that is preview-only, statistics underneath.
- **Right panel**, three sections, each built from declarations:
  the piece's controls; Finishing; Page (Composition, Format, Orientation, Margin,
  Pen).
- **Info text is hidden behind a small *i* button** next to a section title and expands
  on click. **(Neda)**
- **Bottom tray:** kept candidates of the current piece as thumbnails.
- The chrome follows the system light or dark setting; the paper always stays
  paper-white with dark ink.

### Behaviour

- Any change redraws the preview. If changes arrive faster than redraws finish, only
  the latest result is shown; stale ones are discarded.
- **Keep candidate** saves the current plot to `candidates/<piece-slug>/` as an SVG
  (with embedded settings, as above) and shows it in the tray. Kept candidates survive
  restarting the app.
- **Clicking a thumbnail** restores its seed and every setting, including page settings,
  and redraws.
- **A × on hover removes a candidate.** **(Neda asked for removal.)** No confirmation
  dialog; the file is moved to `candidates/.trash/` instead of being deleted, so a
  slip is recoverable. (My call.)
- **Export SVG** downloads the current plot through the browser. The file name
  includes piece slug and seed.
- The current piece, seed and settings survive a page reload. (My call.)
- Double-clicking a slider resets it to its default. (My call.)
- **Draft and keeper.** `steering-material/goal.md` asks for a "save-draft" and a
  "save-keeper". Neda was asked whether that still holds and approved the design
  without answering, so (my call): "Keep candidate" is the draft save and "Export SVG"
  is the keeper save. No third save is built.
- **Candidates and changing code.** A kept candidate is its SVG file; the tray shows
  that file, never a re-render, so a kept picture cannot change. Restoring settings
  from an old candidate after the piece's code has changed may give a different
  picture, and that is accepted: controls that no longer exist are ignored and new
  ones take their defaults. "Same inputs, same SVG" is promised for one version of
  the code. (My call.)
- If a piece raises an error, the app shows the message where the statistics are and
  keeps the last good preview; it does not go blank.

### Running it

- `uv run inkfield` starts the server on localhost and opens the browser.
- `uv run inkfield render <piece-slug> --seed N [page and parameter options] -o file.svg`
  renders without the browser. This is for tests and for the future skill. (My call.)

## 13. Room for projects 2 and 3

Nothing to build, only to not block:

- **Drawing mode** will be a piece whose input includes an image file and whose output
  is contours and hatching. So: nothing in the piece contract or UI should assume that
  controls are only numbers, and the finishing stage should be the natural home for a
  future hatching effect.
- **The skill** will need a written recipe for adding a piece. `docs/adding-a-piece.md`
  is written now, by the builder, as the first draft of that recipe: the contract, a
  minimal example, how to run and check a piece from the command line.

## 14. Testing and checking

- Contour tracing: known fields give known curves (a distance field gives a circle of
  the right radius, closed, with the right length within tolerance).
- Chemical waves: deterministic for a fixed seed; different for different seeds; every
  control changes the output; no stroke has fewer than two points or non-finite
  numbers; with one target pacemaker the rings are concentric and one wavelength apart.
- Finishing: after clipping, every point lies inside the frame (within rounding);
  ordering never changes the set of strokes, only order and direction.
- SVG: parses as XML; size and viewBox match the page; contains only the allowed
  elements; embedded settings round-trip to the same SVG.
- All formats, both orientations, both compositions render without error.
- The import rule in section 7.
- API smoke tests for listing pieces, rendering, keeping, listing and removing
  candidates.
- The UI is checked by loading it in a headless browser and looking at a screenshot
  next to the mockup, in both compositions.

## 15. Left to the builder

File and function names inside the folders; grid resolution and how the quality and
speed targets are met; the wire format between server and front end; how settings are
stored for reload; speed constants for the time estimate; the wording of the docs. The
front end may be restructured freely as long as it looks and behaves like the mockup.
