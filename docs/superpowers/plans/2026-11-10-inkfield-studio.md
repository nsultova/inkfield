# inkfield Studio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A local browser app that hosts procedural-art "pieces" written as readable Python, with schema-built sliders, live preview, kept candidates and plottable SVG export, shipping with one piece, Chemical waves.

**Architecture:** A piece is one Python file (`META`, `PARAMS`, `generate`) returning pen strokes in millimetres. A pure `render()` function runs piece → finishing effects → SVG + statistics. A thin FastAPI server exposes `render()` and candidate storage to a no-build front end that builds its panel from the declared controls.

**Tech Stack:** Python ≥ 3.12, uv, numpy, FastAPI, uvicorn, pytest (+ httpx for the test client), plain HTML/CSS/JS.

**Spec:** `docs/superpowers/specs/2026-11-10-inkfield-studio-design.md` (read it first). Visual reference: `docs/superpowers/specs/2026-11-10-inkfield-mockup.html`.

## Global Constraints

- Python 3.12 or newer; environment managed by `uv`; virtualenv at `.venv`.
- Runtime dependencies are exactly: `numpy`, `fastapi`, `uvicorn`. No scipy, scikit-image, shapely or contour library.
- `inkfield/pieces/`, `core/`, `finish/`, `page/` never import from `inkfield.server` or `inkfield.web`, and do no file or network access. `pieces/` imports only from `inkfield.core` and numpy.
- All geometry is in millimetres on the page, origin top-left, y downward.
- Same piece, seed, settings and page ⇒ byte-identical SVG. All randomness flows from the seed; no `random`, no time-based values in geometry.
- SVG contains only `svg`, `metadata`, `g`, `path` elements; no fill, clip-path, transform, text.
- Front end has no build step and no third-party JavaScript.
- Math in `pieces/` and `core/` is written to be read: plain names, a docstring that explains the idea before the code, numpy only where it replaces an obvious loop over grid points.
- Nothing from `steering-material/*.py` or the old `genart` tool is ported.
- Run all commands from the repository root. Tests: `uv run pytest -q`.

## Review Focus

1. **Garbage settings** (old candidates, stale browser storage: missing keys, unknown keys, strings for numbers, out-of-range values, seed empty/negative/huge). Expected: defaults fill gaps, values clamp, unknown keys are ignored, nothing crashes. Tests in Task 1 (`resolve`) and Task 7 (`render`).
2. **Path traversal through candidate ids or piece slugs** (`../../x`). Expected: 404, nothing read, moved or written outside `candidates/`. Test in Task 8.
3. **Nothing to draw** (elapsed time tiny, huge margin on a small page, border off). Expected: a valid SVG with zero paths and zero statistics. Test in Task 7.
4. **A piece that raises.** Expected: HTTP 422 with the message; the app shows it and keeps the last good preview. Test in Task 8, behaviour in Task 9.
5. **Heaviest settings** (A3, fill page, 24 pacemakers, wavelength 2 mm, elapsed 2). Expected: finishes in seconds, not minutes, without holding one grid per pacemaker in memory. Test in Task 7.

---

## File Map

```
pyproject.toml
inkfield/__init__.py
inkfield/core/stroke.py      Stroke
inkfield/core/frame.py       Frame (circle or rectangle region)
inkfield/core/controls.py    Slider, Choice, Toggle, resolve(), describe()
inkfield/core/piece.py       Meta, Piece, discover()
inkfield/core/rng.py         make_rng()
inkfield/core/polyline.py    length, densify, keep_where, simplify
inkfield/core/noise.py       SmoothField
inkfield/core/contours.py    trace_zero, trace_whole_numbers
inkfield/pieces/__init__.py  (empty)
inkfield/pieces/chemical_waves.py
inkfield/finish/__init__.py  FINISH_PARAMS, FINISH_INFO, apply()
inkfield/finish/wobble.py  clip.py  border.py  tidy.py  order.py
inkfield/page/formats.py     Page, FORMATS, PAGE_PARAMS, make_page, frame_for
inkfield/page/svg.py         to_svg, read_settings
inkfield/page/stats.py       plot_stats
inkfield/render.py           render(), RenderResult
inkfield/cli.py              main()
inkfield/server/app.py       create_app()
inkfield/server/candidates.py  CandidateStore
inkfield/web/index.html  app.css  app.js
tests/test_*.py              one file per module above
README.md
docs/adding-a-piece.md
```

---

### Task 1: Project scaffold and core data types

**Files:**
- Create: `pyproject.toml`, `inkfield/__init__.py`, `inkfield/core/{__init__,stroke,frame,controls,piece,rng}.py`, `inkfield/pieces/__init__.py`
- Test: `tests/test_frame.py`, `tests/test_controls.py`, `tests/test_piece_discovery.py`, `tests/test_import_rule.py`

**Interfaces — Produces:**

```python
# core/stroke.py
@dataclass
class Stroke:
    points: np.ndarray   # shape (N, 2), float64, millimetres
    layer: int = 0

# core/frame.py
@dataclass(frozen=True)
class Frame:
    shape: str           # "circle" or "rect"
    cx: float; cy: float
    half_w: float; half_h: float      # circle: both equal the radius
    @property
    def bbox(self) -> tuple[float, float, float, float]   # x0, y0, x1, y1
    @property
    def scale(self) -> float                               # min(half_w, half_h)
    def contains(self, x, y) -> np.ndarray                 # bool, works on arrays; edge counts as inside
    def inset(self, d: float) -> "Frame"                   # same shape, shrunk by d on every side
    def sample(self, rng, n: int, shrink: float = 1.0) -> np.ndarray  # (n, 2) uniform random points inside; shrink scales the region about its centre
    def outline(self) -> np.ndarray                        # closed polyline; circle uses points ≤ 0.3 mm apart

# core/controls.py
@dataclass(frozen=True)
class Slider: name: str; label: str; min: float; max: float; step: float; default: float; unit: str = ""
@dataclass(frozen=True)
class Choice: name: str; label: str; options: tuple[str, ...]; default: str
@dataclass(frozen=True)
class Toggle: name: str; label: str; default: bool
def resolve(controls: list, values: dict | None) -> dict   # complete, valid dict keyed by control name
def describe(controls: list) -> list[dict]                 # JSON-ready: {"kind": "slider"|"choice"|"toggle", ...fields}

# core/piece.py
@dataclass(frozen=True)
class Meta: slug: str; title: str; subtitle: str; framed_shape: str; info: str
@dataclass(frozen=True)
class Piece: meta: Meta; params: list; generate: Callable   # generate(params: dict, frame: Frame, rng) -> list[Stroke]
def discover(package: str = "inkfield.pieces") -> dict[str, Piece]   # slug -> Piece; modules whose name starts with "_" are skipped

# core/rng.py
def make_rng(seed, stream: str = "") -> np.random.Generator
```

`resolve` rules: missing or unparsable → default; slider values clamp to `[min, max]` and become `int` when `step` is a whole number; a choice value not in `options` → default; toggle accepts bool or the strings `"on"/"off"/"true"/"false"`; keys not declared are dropped.

`make_rng`: `seed` is coerced with `int(float(seed))` falling back to 0, then taken modulo `2**32`; `stream` gives independent generators for the same seed (piece, wobble) via `np.random.SeedSequence([seed, zlib.crc32(stream.encode())])`.

- [ ] **Step 1: Replace the stale environment and scaffold**

```bash
rm -rf .venv .pytest_cache
```

`pyproject.toml`: project `inkfield`, version `0.1.0`, `requires-python = ">=3.12"`, dependencies `numpy`, `fastapi`, `uvicorn`; dependency group `dev` = `pytest`, `httpx`; `[project.scripts] inkfield = "inkfield.cli:main"`; build backend `hatchling`; pytest `testpaths = ["tests"]`. Then `uv sync`. Expected: `.venv` created, `uv run python -c "import numpy, fastapi"` exits 0.

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_frame.py
def test_circle_contains_and_scale():
    f = Frame("circle", 100, 100, 50, 50)
    assert f.scale == 50 and f.bbox == (50, 50, 150, 150)
    assert f.contains(np.array([100, 150, 151]), np.array([100, 100, 100])).tolist() == [True, True, False]

def test_rect_contains_and_inset():
    f = Frame("rect", 105, 148.5, 89, 132.5).inset(3)
    assert (f.half_w, f.half_h) == (86, 129.5)
    assert f.contains(np.array([19.0, 18.9]), np.array([148.5, 148.5])).tolist() == [True, False]

@pytest.mark.parametrize("shape", ["circle", "rect"])
def test_sample_is_inside_and_seeded(shape):
    f = Frame(shape, 100, 100, 40, 60 if shape == "rect" else 40)
    a = f.sample(make_rng(3), 200); b = f.sample(make_rng(3), 200)
    assert a.shape == (200, 2) and np.array_equal(a, b) and f.contains(a[:, 0], a[:, 1]).all()

def test_outline_is_closed_and_on_edge():
    o = Frame("circle", 0, 0, 10, 10).outline()
    assert np.allclose(o[0], o[-1]) and np.allclose(np.hypot(o[:, 0], o[:, 1]), 10)
    assert np.hypot(*np.diff(o, axis=0).T).max() <= 0.3

# tests/test_controls.py
C = [Slider("n", "N", 1, 24, 1, 9), Slider("w", "W", 2, 14, 0.1, 5.5, " mm"),
     Choice("fmt", "F", ("A4", "A3"), "A4"), Toggle("b", "B", True)]
def test_defaults():            assert resolve(C, None) == {"n": 9, "w": 5.5, "fmt": "A4", "b": True}
def test_clamp_and_int():       r = resolve(C, {"n": 99.7, "w": -3}); assert r["n"] == 24 and isinstance(r["n"], int) and r["w"] == 2
def test_garbage_falls_back():  assert resolve(C, {"n": "abc", "w": None, "fmt": "B5", "b": "off", "zzz": 1}) == {"n": 9, "w": 5.5, "fmt": "A4", "b": False}
def test_describe():            assert describe(C)[0] == {"kind": "slider", "name": "n", "label": "N", "min": 1, "max": 24, "step": 1, "default": 9, "unit": ""}

def test_rng_seed_coercion():
    assert make_rng("").random() == make_rng(0).random()
    assert make_rng(-1).random() == make_rng(2**32 - 1).random()
    assert make_rng(7, "a").random() != make_rng(7, "b").random()

# tests/test_piece_discovery.py
def test_discovers_a_dropped_in_file(tmp_path, monkeypatch):
    pkg = tmp_path / "fakepieces"; pkg.mkdir(); (pkg / "__init__.py").write_text("")
    (pkg / "dots.py").write_text(FAKE_PIECE_SOURCE)      # META slug "dots", one Slider, generate returns one Stroke
    (pkg / "_hidden.py").write_text("raise RuntimeError")
    monkeypatch.syspath_prepend(str(tmp_path))
    pieces = discover("fakepieces")
    assert list(pieces) == ["dots"] and pieces["dots"].meta.title == "Dots"

# tests/test_import_rule.py
def test_math_never_imports_plumbing():
    # parse every .py under inkfield/{pieces,core,finish,page} with ast and collect imported module names
    # assert none starts with "inkfield.server" or "inkfield.web" or is in {"os", "pathlib", "io", "socket", "urllib", "requests", "httpx", "fastapi"}
    # assert every import under inkfield/pieces is "numpy", "math", "dataclasses" or starts with "inkfield.core"
```

`core/piece.py` may import `importlib` and `pkgutil`; add them to the allowed set for that file.

- [ ] **Step 3: Run tests, expect failures** — `uv run pytest -q` → import errors.
- [ ] **Step 4: Implement the modules above.**
- [ ] **Step 5: Run tests, expect pass** — `uv run pytest -q`.
- [ ] **Step 6: Commit** — `git add -A && git commit -m "feat: scaffold inkfield with core data types"` (the commit includes `.gitignore`, the spec, the mockup and this plan if still untracked).

---

### Task 2: Polyline tools and smooth noise

**Files:**
- Create: `inkfield/core/polyline.py`, `inkfield/core/noise.py`
- Test: `tests/test_polyline.py`, `tests/test_noise.py`

**Interfaces — Produces:**

```python
# core/polyline.py   (a polyline is an (N, 2) float array)
def length(points) -> float
def densify(points, max_step: float) -> np.ndarray          # insert points so no segment exceeds max_step
def keep_where(points, inside, tol: float = 0.01) -> list[np.ndarray]
    # inside(x_array, y_array) -> bool array. Returns the parts of the polyline that are inside.
    # Each cut end is a new point located by bisection to within tol mm of the true boundary.
    # Parts with fewer than 2 points are dropped.
def simplify(points, tol: float) -> np.ndarray              # Ramer–Douglas–Peucker; endpoints kept; closed lines stay closed

# core/noise.py
class SmoothField:
    def __init__(self, rng, wavelength: float, octaves: int = 2)
    def __call__(self, x, y) -> tuple[np.ndarray, np.ndarray]   # (dx, dy), each roughly within [-1, 1], smooth, same shape as x
```

`SmoothField` is a sum of `octaves` sine waves per component with random directions and phases drawn from `rng` at construction, octave *k* having wavelength `wavelength / 2**k` and weight `0.5**k`, normalised by the weight sum. No lookup tables.

- [ ] **Step 1: Write the failing tests**

```python
def test_length():   assert length(np.array([[0, 0], [3, 4], [3, 10]])) == 11
def test_densify():  d = densify(np.array([[0., 0], [10, 0]]), 1.0); assert len(d) == 11 and np.allclose(d[:, 0], np.arange(11))

def test_keep_where_cuts_on_the_boundary():
    line = np.array([[-20., 0], [20, 0]])
    parts = keep_where(densify(line, 1.0), lambda x, y: np.hypot(x, y) <= 10)
    assert len(parts) == 1
    assert abs(parts[0][0, 0] + 10) <= 0.01 and abs(parts[0][-1, 0] - 10) <= 0.01

def test_keep_where_splits_into_several_parts():
    zig = np.array([[0., 0], [0, 5], [0, 15], [0, 25]])
    parts = keep_where(zig, lambda x, y: (y <= 8) | (y >= 20))
    assert len(parts) == 2 and abs(parts[0][-1, 1] - 8) <= 0.01 and abs(parts[1][0, 1] - 20) <= 0.01

def test_keep_where_all_inside_returns_input_unchanged():
    p = np.array([[0., 0], [1, 1]]); out = keep_where(p, lambda x, y: np.ones_like(x, bool))
    assert len(out) == 1 and np.array_equal(out[0], p)

def test_simplify_drops_collinear_keeps_corners():
    p = np.array([[0., 0], [1, 0.001], [2, 0], [2, 2]]); assert simplify(p, 0.01).tolist() == [[0, 0], [2, 0], [2, 2]]

def test_smooth_field_is_seeded_bounded_and_smooth():
    f = SmoothField(make_rng(1), 80); g = SmoothField(make_rng(1), 80)
    x = np.linspace(0, 300, 500); y = np.zeros(500)
    dx, dy = f(x, y)
    assert np.array_equal(dx, g(x, y)[0]) and np.abs(dx).max() <= 1.0001 and np.abs(dy).max() <= 1.0001
    assert np.abs(np.diff(dx)).max() < 0.2 and dx.std() > 0.1
```

- [ ] **Step 2: Run, expect fail. Step 3: Implement. Step 4: Run, expect pass.**
- [ ] **Step 5: Commit** — `git commit -am "feat: polyline tools and smooth noise"` (after `git add`).

---

### Task 3: Contour tracing

**Files:**
- Create: `inkfield/core/contours.py`
- Test: `tests/test_contours.py`

**Interfaces — Produces:**

```python
def trace_zero(field, xs, ys, cells=None) -> list[np.ndarray]
    # field[j, i] is the value at (xs[i], ys[j]). Returns polylines along field == 0.
    # cells: optional bool array of shape (len(ys)-1, len(xs)-1); only True cells are examined.
    # Cells with a non-finite corner are skipped. Closed loops repeat their first point.
def trace_whole_numbers(phase, xs, ys, cells=None) -> list[np.ndarray]
    # Lines where phase is a whole number (…, -1, 0, 1, 2, …), all in one pass.
```

Algorithm (marching squares), to be explained in the module docstring with a small ASCII picture of the 16 cases:

1. With numpy, mark each grid point positive or not, and build a 4-bit case number per cell. Cells with case 0 or 15, masked-out cells and non-finite cells are ignored.
2. Loop in plain Python over the remaining cells only. Each case gives one or two segments between cell edges; the crossing point on an edge is found by linear interpolation between its two corner values. Saddle cases (5 and 10) are resolved by the sign of the mean of the four corners.
3. Every grid edge has a unique integer id, shared by the two cells that touch it. Chain segments into polylines by following shared edge ids, extending each line in both directions.

`trace_whole_numbers` uses the fact that `sin(2π·phase)` is zero exactly at whole and half numbers, and `cos(2π·phase)` is positive near whole numbers only: it calls `trace_zero(sin(2π·phase), …)` restricted to cells whose four corners all have `cos(2π·phase) > 0`. This requires the grid to be fine enough that phase changes by less than about 0.18 across a cell diagonal; the docstring must say so.

- [ ] **Step 1: Write the failing tests**

```python
xs = ys = np.arange(0, 100.01, 0.5); X, Y = np.meshgrid(xs, ys)

def test_circle():
    lines = trace_zero(np.hypot(X - 50, Y - 50) - 20, xs, ys)
    assert len(lines) == 1
    p = lines[0]; r = np.hypot(p[:, 0] - 50, p[:, 1] - 50)
    assert np.allclose(p[0], p[-1]) and np.abs(r - 20).max() < 0.02
    assert abs(length(p) - 2 * np.pi * 20) < 0.005 * 2 * np.pi * 20

def test_open_line_runs_edge_to_edge():
    lines = trace_zero(X - 30.25, xs, ys)
    assert len(lines) == 1 and np.allclose(lines[0][:, 0], 30.25)
    assert sorted([lines[0][0, 1], lines[0][-1, 1]]) == [0, 100]

def test_two_separate_loops():
    f = np.minimum(np.hypot(X - 25, Y - 25), np.hypot(X - 75, Y - 75)) - 10
    assert len(trace_zero(f, xs, ys)) == 2

def test_cells_mask_and_nan():
    f = np.hypot(X - 50, Y - 50) - 20
    assert trace_zero(f, xs, ys, cells=np.zeros((len(ys) - 1, len(xs) - 1), bool)) == []
    g = f.copy(); g[:, X[0] > 50] = np.nan
    assert all((ln[:, 0] <= 50).all() for ln in trace_zero(g, xs, ys))

def test_whole_numbers_gives_one_ring_per_wavelength():
    lines = trace_whole_numbers(np.hypot(X - 50, Y - 50) / 5.0, xs, ys)
    closed = [ln for ln in lines if np.allclose(ln[0], ln[-1])]
    radii = sorted(round(float(np.hypot(ln[:, 0] - 50, ln[:, 1] - 50).mean())) for ln in closed)
    assert radii == [5, 10, 15, 20, 25, 30, 35, 40, 45, 50]
    for ln in closed:
        r = np.hypot(ln[:, 0] - 50, ln[:, 1] - 50); assert r.max() - r.min() < 0.05
```

- [ ] **Step 2: Run, expect fail. Step 3: Implement. Step 4: Run, expect pass.**
- [ ] **Step 5: Commit** — `feat: readable marching-squares contour tracing`.

---

### Task 4: The Chemical waves piece

**Files:**
- Create: `inkfield/pieces/chemical_waves.py`
- Test: `tests/test_chemical_waves.py`

**Interfaces:**
- Consumes: `Frame`, `Stroke`, `Slider`, `Meta` (Task 1); `keep_where`, `SmoothField` (Task 2); `trace_whole_numbers` (Task 3).
- Produces: module attributes `META`, `PARAMS`, `generate(params, frame, rng) -> list[Stroke]`.

```python
META = Meta(slug="chemical-waves", title="Chemical waves", subtitle="Belousov–Zhabotinsky",
            framed_shape="circle", info=<the info text from the mockup's first section, as plain text>)
PARAMS = [
    Slider("sources",    "Pacemakers",        1,    24,  1,    9),
    Slider("spirals",    "Spiral share",      0,    1,   0.01, 0.30),
    Slider("wavelength", "Wavelength",        2,    14,  0.1,  5.5, " mm"),
    Slider("elapsed",    "Elapsed time",      0.08, 2,   0.01, 0.42),
    Slider("stagger",    "Start stagger",     0,    1,   0.01, 0.70),
    Slider("uneven",     "Medium unevenness", 0,    1,   0.01, 0.20),
]
```

Model and algorithm (spec §9). The module docstring tells this story in plain language with the formulas before any code:

- `elapsed_mm = elapsed · frame.scale`. Pacemaker positions: `frame.sample(rng, sources, shrink=0.92)`. Per pacemaker, drawn from `rng` in a fixed order: `delay = U(0,1) · stagger · elapsed_mm`, `is_spiral = U(0,1) < spirals`, `turn = ±1`, `phase_offset = U(0,1)`.
- Uneven medium: a point `p` is measured at `q = p + uneven · 1.2 · wavelength · SmoothField(rng, wavelength=0.9·frame.scale)(p)`.
- `arrival_i(p) = delay_i + |q − pacemaker_i|`. `base_i = (elapsed_mm − arrival_i) / wavelength`. Phase of a target: `base_i`. Phase of a spiral: `base_i + turn_i · angle_i / 2π + phase_offset_i`, with `angle_i = atan2` of `q − pacemaker_i`.
- Grid over `frame.bbox`, cell size `min(0.5, wavelength / 8)` mm.
- One pass over the pacemakers keeps only a running "earliest arrival" grid and a "who was earliest" grid (never one grid per pacemaker).
- For each pacemaker: trace `trace_whole_numbers(phase_i, …)` restricted to cells where it is the winner on at least one corner and `base_i > −0.5` on all four. Limit the work to the grid window that its territory touches.
- Cut each traced line with `keep_where` so it survives only where (a) `arrival_i ≤` every other pacemaker's arrival, evaluated exactly at the line's points, not from the grid; (b) for spirals, `base_i ≥ 0` and distance from the core `≥ 0.35 · wavelength`.
- Return every surviving part as a `Stroke`. No clipping to the frame, no border, no tidying: finishing does those.

Small named helper functions inside the file (for example `place_pacemakers`, `arrival_time`, `phase`) are encouraged so `generate` reads as the five steps above.

- [ ] **Step 1: Write the failing tests**

```python
FRAME = Frame("circle", 105, 148.5, 86, 86)
D = resolve(PARAMS, None)
def run(seed=7, **kw): return generate({**D, **kw}, FRAME, make_rng(seed, "piece"))
def pts(strokes): return np.vstack([s.points for s in strokes])

def test_deterministic_and_seed_sensitive():
    a, b, c = run(7), run(7), run(8)
    assert len(a) == len(b) and all(np.array_equal(x.points, y.points) for x, y in zip(a, b))
    assert len(a) != len(c) or not np.array_equal(pts(a), pts(c))

def test_strokes_are_well_formed():
    s = run(); assert len(s) > 5
    assert all(x.points.ndim == 2 and x.points.shape[1] == 2 and len(x.points) >= 2 and np.isfinite(x.points).all() and x.layer == 0 for x in s)

@pytest.mark.parametrize("name,value", [("sources", 3), ("spirals", 1.0), ("wavelength", 9), ("elapsed", 1.0), ("stagger", 0.1), ("uneven", 0.8)])
def test_every_control_changes_the_picture(name, value):
    a, b = run(), run(**{name: value}); assert len(a) != len(b) or not np.array_equal(pts(a), pts(b))

def test_single_target_gives_concentric_rings_one_wavelength_apart():
    s = run(sources=1, spirals=0, uneven=0, stagger=0, elapsed=0.5, wavelength=5)
    centre = FRAME.sample(make_rng(7, "piece"), 1, shrink=0.92)[0]     # same draw order as generate
    radii = sorted(float(np.hypot(*(x.points - centre).T).mean()) for x in s)
    assert len(radii) == 9                            # elapsed 43 mm: fronts at 43, 38, …, 3
    assert np.allclose(np.diff(radii), 5, atol=0.05) and abs(radii[-1] - 43) < 0.05
    for x in s: r = np.hypot(*(x.points - centre).T); assert r.max() - r.min() < 0.05

def test_rings_are_smooth():
    s = run(sources=1, spirals=0, uneven=0, stagger=0, elapsed=0.5, wavelength=5)
    for x in s:
        d = np.diff(x.points, axis=0); a = np.arctan2(d[:, 1], d[:, 0])
        turn = np.abs((np.diff(a) + np.pi) % (2 * np.pi) - np.pi)
        assert np.degrees(turn.max()) < 20

def test_lines_meet_at_the_seam():
    # two targets, no delay: the seam is the perpendicular bisector; ends must lie within 0.3 mm of it
    s = run(sources=2, spirals=0, uneven=0, stagger=0, elapsed=1.2)
    P = FRAME.sample(make_rng(7, "piece"), 2, shrink=0.92)      # same draw order as generate
    ends = np.array([e for x in s for e in (x.points[0], x.points[-1]) if not np.allclose(x.points[0], x.points[-1])])
    gap = np.abs(np.hypot(*(ends - P[0]).T) - np.hypot(*(ends - P[1]).T))
    assert len(ends) > 0 and (gap < 0.3).mean() > 0.9           # the rest are ends at the outer reach

def test_spiral_has_a_clean_core():
    s = run(sources=1, spirals=1.0, uneven=0, stagger=0, elapsed=0.6, wavelength=6)
    P = FRAME.sample(make_rng(7, "piece"), 1, shrink=0.92)[0]
    assert np.hypot(*(pts(s) - P).T).min() >= 0.35 * 6 - 0.05
```

The ring, seam and spiral tests rely on `generate` drawing pacemaker positions as its first use of `rng`; keep that order.

- [ ] **Step 2: Run, expect fail. Step 3: Implement. Step 4: Run, expect pass.**
- [ ] **Step 5: Look at it.** Write a 10-line throwaway script in the scratch directory that calls `generate` and dumps a bare SVG; open it or screenshot it with `chromium --headless --screenshot`. Compare with `steering-material/Belousov-Zhabotinsky_00.png` and `_03.png`: rings, spirals, cusped seams, no scribbles. Fix what looks wrong before committing.
- [ ] **Step 6: Commit** — `feat: Chemical waves piece`.

---

### Task 5: Finishing effects

**Files:**
- Create: `inkfield/finish/{__init__,wobble,clip,border,tidy,order}.py`
- Test: `tests/test_finish.py`

**Interfaces:**
- Consumes: `Stroke`, `Frame`, `Slider`, `Toggle`, `make_rng`; `densify`, `keep_where`, `simplify`, `length`; `SmoothField`.
- Produces:

```python
# finish/__init__.py
FINISH_PARAMS = [Slider("wobble", "Hand wobble", 0, 1, 0.01, 0), Toggle("border", "Border", True)]
FINISH_INFO = "Effects that work on any piece, because every piece hands over plain pen strokes."
BORDER_GAP = 0.035                      # inset of the inner border line, as a fraction of frame.scale
def inner_frame(outer: Frame, settings: dict) -> Frame      # outer.inset(BORDER_GAP * outer.scale) when border is on, else outer
def apply(strokes, inner: Frame, outer: Frame, settings: dict, seed) -> list[Stroke]

# one function per file
def wobble(strokes, amount: float, seed) -> list[Stroke]     # displacement up to amount·1.1 mm from SmoothField(make_rng(seed, "wobble"), wavelength=9)
def clip(strokes, frame: Frame) -> list[Stroke]              # densify(…, 1.0) then keep_where(…, frame.contains)
def border(outer: Frame, inner: Frame) -> list[Stroke]       # the two outlines
def tidy(strokes, min_length=1.5, join_tol=0.1, simplify_tol=0.02) -> list[Stroke]
def order(strokes, start=(0.0, 0.0)) -> list[Stroke]         # greedy nearest end, flipping strokes when the far end is nearer
```

`apply` order: wobble → clip to `inner` → append border (if on) → tidy → order. `tidy` order: join strokes of the same layer whose ends lie within `join_tol` (repeat until none remain; a stroke may be flipped to join; closed strokes are never joined to anything), drop strokes shorter than `min_length`, then simplify. Border outlines pass through tidy and order like any stroke.

- [ ] **Step 1: Write the failing tests**

```python
OUTER = Frame("circle", 100, 100, 50, 50)
def S(*p): return Stroke(np.array(p, float))

def test_clip_cuts_exactly_and_keeps_inside():
    out = clip([S((0, 100), (200, 100))], OUTER)
    assert len(out) == 1 and abs(out[0].points[0, 0] - 50) <= 0.01 and abs(out[0].points[-1, 0] - 150) <= 0.01
    p = np.vstack([s.points for s in out]); assert (np.hypot(p[:, 0] - 100, p[:, 1] - 100) <= 50.011).all()

def test_wobble_zero_is_identity_and_nonzero_is_seeded():
    s = [S((0, 0), (50, 0), (100, 0))]
    assert np.array_equal(wobble(s, 0, 1)[0].points, s[0].points)
    a, b = wobble(s, 1, 1)[0].points, wobble(s, 1, 1)[0].points
    assert np.array_equal(a, b) and not np.array_equal(a, s[0].points) and np.abs(a - s[0].points).max() <= 1.1 * 1.0001

def test_tidy_joins_drops_and_simplifies():
    out = tidy([S((0, 0), (5, 0)), S((10, 0), (5.05, 0)), S((50, 50), (50.5, 50))])
    assert len(out) == 1 and np.allclose(out[0].points[[0, -1]], [[0, 0], [10, 0]], atol=0.06) and len(out[0].points) <= 3

def test_order_keeps_the_same_strokes_and_shortens_travel():
    rng = make_rng(1); strokes = [S(*rng.uniform(0, 200, (2, 2))) for _ in range(60)]
    out = order(strokes)
    key = lambda s: tuple(sorted(map(tuple, np.round(s.points, 6).tolist())))
    assert sorted(map(key, out)) == sorted(map(key, strokes))
    travel = lambda ss: sum(np.hypot(*(b.points[0] - a.points[-1])) for a, b in zip(ss, ss[1:]))
    assert travel(out) < 0.5 * travel(strokes)

def test_apply_with_border_on_and_off():
    line = [S((0, 100), (200, 100))]
    on = {"wobble": 0, "border": True}; off = {"wobble": 0, "border": False}
    inner = inner_frame(OUTER, on); assert inner.half_w == 50 - 0.035 * 50 and inner_frame(OUTER, off) == OUTER
    a = apply(line, inner, OUTER, on, 1); b = apply(line, OUTER, OUTER, off, 1)
    assert len(a) == 3 and len(b) == 1
    assert max(length(s.points) for s in a) > 2 * np.pi * 49

def test_apply_on_nothing():
    assert apply([], OUTER, OUTER, {"wobble": 0.5, "border": False}, 1) == []
```

- [ ] **Step 2: Run, expect fail. Step 3: Implement. Step 4: Run, expect pass.**
- [ ] **Step 5: Commit** — `feat: shared finishing effects`.

---

### Task 6: Page formats, SVG and statistics

**Files:**
- Create: `inkfield/page/{__init__,formats,svg,stats}.py`
- Test: `tests/test_page.py`

**Interfaces — Produces:**

```python
# page/formats.py
FORMATS = {"A4": (210, 297), "A3": (297, 420), "Square": (250, 250)}      # portrait width, height in mm
PAGE_PARAMS = [
    Choice("composition", "Composition", ("framed", "fill page"), "framed"),
    Choice("format", "Format", ("A4", "A3", "Square"), "A4"),
    Choice("orientation", "Orientation", ("portrait", "landscape"), "portrait"),
    Slider("margin", "Margin", 5, 40, 1, 16, " mm"),
    Choice("pen", "Pen", ("0.2", "0.3", "0.5", "0.8"), "0.3"),
]
@dataclass(frozen=True)
class Page: width: float; height: float; margin: float
def make_page(settings: dict) -> Page
def frame_for(page: Page, composition: str, framed_shape: str) -> Frame
    # "fill page" → the rectangle inside the margin. "framed" → the largest framed_shape inside the margin, centred.

# page/svg.py
def to_svg(strokes, page: Page, pen_mm: float, settings: dict) -> str
def read_settings(svg_text: str) -> dict

# page/stats.py
PEN_DOWN_MM_S = 25.0; PEN_UP_MM_S = 75.0; LIFT_S = 0.35
def plot_stats(strokes) -> dict     # {"strokes": int, "drawn_m": float, "travel_m": float, "minutes": float}; travel starts at (0, 0)
```

SVG shape, exactly:

```xml
<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
     width="210mm" height="297mm" viewBox="0 0 210 297">
<metadata><inkfield xmlns="https://inkfield.invalid/ns">{"piece": …}</inkfield></metadata>
<g inkscape:groupmode="layer" inkscape:label="1" id="layer1" fill="none" stroke="#000000"
   stroke-width="0.3" stroke-linecap="round" stroke-linejoin="round">
<path d="M12.34 56.78L…"/>
</g>
</svg>
```

Numbers in `width`, `height`, `viewBox` are written without a trailing `.0`; coordinates always with two decimals; a stroke whose first and last points coincide ends with `Z` instead of repeating the point; one `<g>` per layer number present, in ascending order, labelled `layer + 1`; when there are no strokes, one empty layer-1 group. The settings JSON is `json.dumps(settings, sort_keys=True)`, XML-escaped.

- [ ] **Step 1: Write the failing tests**

```python
def test_pages():
    assert make_page(resolve(PAGE_PARAMS, None)) == Page(210, 297, 16)
    assert make_page(resolve(PAGE_PARAMS, {"format": "A3", "orientation": "landscape", "margin": 20})) == Page(420, 297, 20)

def test_frames():
    p = Page(210, 297, 16)
    assert frame_for(p, "framed", "circle") == Frame("circle", 105, 148.5, 89, 89)
    assert frame_for(p, "fill page", "circle") == Frame("rect", 105, 148.5, 89, 132.5)
    assert frame_for(p, "framed", "rect") == Frame("rect", 105, 148.5, 89, 132.5)

SET = {"piece": "x", "seed": 7, "params": {"a": 1.5}, "finish": {}, "page": {"format": "A4"}}
STROKES = [Stroke(np.array([[10, 10], [20, 10.004]])), Stroke(np.array([[0., 0], [5, 0], [5, 5], [0, 0]]))]

def test_svg_structure_and_units():
    svg = to_svg(STROKES, Page(210, 297, 16), 0.3, SET)
    root = ET.fromstring(svg)
    assert root.get("width") == "210mm" and root.get("height") == "297mm" and root.get("viewBox") == "0 0 210 297"
    tags = {el.tag.split("}")[1] for el in root.iter()}
    assert tags == {"svg", "metadata", "inkfield", "g", "path"}
    paths = [el.get("d") for el in root.iter("{http://www.w3.org/2000/svg}path")]
    assert paths == ["M10.00 10.00L20.00 10.00", "M0.00 0.00L5.00 0.00L5.00 5.00Z"]
    for bad in ("clip", "transform", "<text", "style="): assert bad not in svg
    assert 'stroke-width="0.3"' in svg and 'fill="none"' in svg

def test_settings_round_trip_and_determinism():
    svg = to_svg(STROKES, Page(210, 297, 16), 0.3, SET)
    assert read_settings(svg) == SET and svg == to_svg(STROKES, Page(210, 297, 16), 0.3, SET)

def test_empty_drawing_is_valid():
    root = ET.fromstring(to_svg([], Page(250, 250, 16), 0.5, SET)); assert len(list(root.iter("{http://www.w3.org/2000/svg}path"))) == 0

def test_stats():
    s = plot_stats([Stroke(np.array([[30., 40], [130, 40]]))])
    assert s["strokes"] == 1 and s["drawn_m"] == pytest.approx(0.1) and s["travel_m"] == pytest.approx(0.05)
    assert s["minutes"] == pytest.approx((100 / 25 + 50 / 75 + 0.35) / 60)
    assert plot_stats([]) == {"strokes": 0, "drawn_m": 0.0, "travel_m": 0.0, "minutes": 0.0}
```

- [ ] **Step 2: Run, expect fail. Step 3: Implement. Step 4: Run, expect pass.**
- [ ] **Step 5: Commit** — `feat: page formats, SVG writer and plot statistics`.

---

### Task 7: The render function and command-line render

**Files:**
- Create: `inkfield/render.py`, `inkfield/cli.py`
- Test: `tests/test_render.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: everything from Tasks 1–6.
- Produces:

```python
# render.py
@dataclass
class RenderResult: svg: str; stats: dict; page: Page; settings: dict
def render(pieces: dict[str, Piece], piece: str, seed=0, params=None, finish=None, page=None) -> RenderResult
    # raises KeyError for an unknown piece slug
```

`render` steps: resolve the three settings dicts against `piece.params`, `FINISH_PARAMS`, `PAGE_PARAMS`; coerce seed to an int in `[0, 2**32)` using the same rule as `make_rng`; `outer = frame_for(...)`; `inner = inner_frame(outer, finish)`; `strokes = piece.generate(params, inner, make_rng(seed, "piece"))`; `strokes = finish.apply(strokes, inner, outer, finish, seed)`; build `settings = {"piece", "seed", "params", "finish", "page"}` from the resolved values; return SVG, stats, page, settings. It reads no files and has no global state.

CLI (`argparse`), `main(argv=None) -> int`:

- `inkfield` or `inkfield serve [--port 8000] [--no-browser]` — implemented in Task 8; in this task `serve` may be a stub that raises `SystemExit("server not built yet")`.
- `inkfield render <slug> [--seed N] [--composition …] [--format …] [--orientation …] [--margin N] [--pen …] [--wobble X] [--no-border] [--set name=value]… -o FILE` — `--set` feeds piece params; writes the SVG to `FILE`, prints one line of statistics, returns 0; unknown slug prints the available slugs to stderr and returns 2.
- `inkfield list` — prints slug and title of each piece.

- [ ] **Step 1: Write the failing tests**

```python
PIECES = discover()

def test_same_inputs_same_bytes():
    a = render(PIECES, "chemical-waves", seed=7); b = render(PIECES, "chemical-waves", seed=7)
    assert a.svg == b.svg and a.svg != render(PIECES, "chemical-waves", seed=8).svg

def test_settings_round_trip_reproduces_the_svg():
    a = render(PIECES, "chemical-waves", seed=11, params={"sources": 4}, finish={"wobble": 0.3}, page={"format": "Square"})
    s = read_settings(a.svg); assert s == a.settings
    assert render(PIECES, s["piece"], s["seed"], s["params"], s["finish"], s["page"]).svg == a.svg

@pytest.mark.parametrize("fmt", ["A4", "A3", "Square"])
@pytest.mark.parametrize("orient", ["portrait", "landscape"])
@pytest.mark.parametrize("comp", ["framed", "fill page"])
def test_every_page_combination_stays_inside_the_margin(fmt, orient, comp):
    r = render(PIECES, "chemical-waves", seed=3, params={"elapsed": 1.2}, page={"format": fmt, "orientation": orient, "composition": comp})
    xy = np.array(re.findall(r"(-?\d+\.\d\d) (-?\d+\.\d\d)", r.svg), float)
    m = r.page.margin - 0.02
    assert len(xy) > 100 and xy[:, 0].min() >= m and xy[:, 1].min() >= m and xy[:, 0].max() <= r.page.width - m and xy[:, 1].max() <= r.page.height - m

def test_garbage_settings_do_not_crash():           # Review Focus 1
    r = render(PIECES, "chemical-waves", seed="abc", params={"sources": "many", "gone": 3, "wavelength": 1e9}, finish={"border": "off"}, page={"format": "B5", "margin": -4})
    assert r.settings["seed"] == 0 and r.settings["params"]["sources"] == 9 and r.settings["params"]["wavelength"] == 14
    assert r.settings["page"]["format"] == "A4" and r.settings["page"]["margin"] == 5 and "gone" not in r.settings["params"]

def test_nothing_to_draw_is_still_a_valid_svg():    # Review Focus 3
    r = render(PIECES, "chemical-waves", seed=1, params={"elapsed": 0.08, "wavelength": 14, "sources": 1, "stagger": 1}, finish={"border": False}, page={"format": "Square", "margin": 40})
    ET.fromstring(r.svg); assert r.stats["strokes"] == len(re.findall("<path", r.svg))

def test_unknown_piece():
    with pytest.raises(KeyError): render(PIECES, "nope")

def test_speed_default_a4():
    render(PIECES, "chemical-waves", seed=7)                         # warm-up
    t = time.perf_counter(); render(PIECES, "chemical-waves", seed=7); assert time.perf_counter() - t < 0.5

def test_speed_a3_fill_24_sources():
    t = time.perf_counter(); render(PIECES, "chemical-waves", seed=7, params={"sources": 24}, page={"format": "A3", "composition": "fill page"}); assert time.perf_counter() - t < 2.0

def test_heaviest_settings_finish():                # Review Focus 5
    t = time.perf_counter()
    render(PIECES, "chemical-waves", seed=7, params={"sources": 24, "wavelength": 2, "elapsed": 2}, page={"format": "A3", "composition": "fill page"})
    assert time.perf_counter() - t < 20

# tests/test_cli.py
def test_render_writes_a_file(tmp_path, capsys):
    out = tmp_path / "a.svg"
    assert main(["render", "chemical-waves", "--seed", "7", "--format", "A3", "--set", "sources=4", "-o", str(out)]) == 0
    s = read_settings(out.read_text()); assert s["seed"] == 7 and s["page"]["format"] == "A3" and s["params"]["sources"] == 4
    assert "strokes" in capsys.readouterr().out
def test_unknown_slug_returns_2(tmp_path): assert main(["render", "nope", "-o", str(tmp_path / "x.svg")]) == 2
def test_list(capsys): assert main(["list"]) == 0 and "chemical-waves" in capsys.readouterr().out
```

The test thresholds are loose guards; the spec's targets are 200 ms (default A4) and 1 s (A3 fill, 24 pacemakers) on a Ryzen 5 5500U.

- [ ] **Step 2: Run, expect fail. Step 3: Implement. Step 4: Run, expect pass.**
- [ ] **Step 5: Measure and report.** Run `uv run python -c` with a small timing loop for the three speed cases and note the numbers in the commit message. If default A4 exceeds 200 ms, profile (`python -X importtime` is not it; use `cProfile`) and speed up the hot spot without making `chemical_waves.py` harder to read; put any dense optimisation in `core/`. If the targets still cannot be met, stop and report instead of adding the two-tier preview on your own.
- [ ] **Step 6: Commit** — `feat: render pipeline and command-line render`.

---

### Task 8: Server and candidate storage

**Files:**
- Create: `inkfield/server/{__init__,app,candidates}.py`
- Modify: `inkfield/cli.py` (real `serve`)
- Test: `tests/test_candidates.py`, `tests/test_api.py`

**Interfaces:**
- Consumes: `render`, `RenderResult`, `discover`, `describe`, `FINISH_PARAMS`, `FINISH_INFO`, `PAGE_PARAMS`, `read_settings`.
- Produces:

```python
# server/candidates.py
class CandidateStore:
    def __init__(self, root: Path)
    def save(self, slug: str, seed: int, svg: str) -> str          # returns id "YYYYmmdd-HHMMSS-seed<seed>", with "-2", "-3"… appended on collision
    def list(self, slug: str) -> list[dict]                        # oldest first: {"id", "seed", "settings"} read from each SVG's metadata
    def path(self, slug: str, cid: str) -> Path                    # raises KeyError if missing or if slug/id are not plain names
    def remove(self, slug: str, cid: str) -> None                  # moves the file to root/.trash/<slug>/, never deletes
# plain name: re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", s)

# server/app.py
def create_app(candidates_dir: Path = Path("candidates"), pieces: dict | None = None) -> FastAPI
```

HTTP API (JSON unless noted):

| Method and path | Body | Response |
|---|---|---|
| `GET /` and static files | | `inkfield/web/` (index.html at `/`) |
| `GET /api/pieces` | | `{"pieces": [{"slug","title","subtitle","info","params":[…describe]}], "finish": {"info": FINISH_INFO, "params": […]}, "page": {"params": […]}}` |
| `POST /api/render` | `{"piece","seed","params","finish","page"}` (all but `piece` optional) | `{"svg","stats","settings","page":{"width","height","margin"}}` |
| `GET /api/candidates/{slug}` | | `[{"id","seed","settings","url"}]` |
| `POST /api/candidates` | same as render | renders at full quality, saves, returns the new list item |
| `GET /api/candidates/{slug}/{id}.svg` | | the file, `image/svg+xml` |
| `DELETE /api/candidates/{slug}/{id}` | | 204 |

Errors: unknown piece → 404 `{"error": …}`; a piece or effect that raises → 422 `{"error": "<ExceptionType>: <message>"}`; unknown or malformed candidate → 404. `serve` binds `127.0.0.1` only, opens the browser unless `--no-browser`, and stores candidates in `./candidates`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_candidates.py
SVG = to_svg([], Page(210, 297, 16), 0.3, {"piece": "p", "seed": 7, "params": {}, "finish": {}, "page": {}})
def test_save_list_remove(tmp_path):
    st = CandidateStore(tmp_path); a = st.save("p", 7, SVG); b = st.save("p", 7, SVG)
    assert a != b and [c["id"] for c in st.list("p")] == [a, b] and st.list("p")[0]["settings"]["seed"] == 7
    st.remove("p", a)
    assert [c["id"] for c in st.list("p")] == [b] and (tmp_path / ".trash" / "p" / f"{a}.svg").exists()
def test_list_of_unknown_slug_is_empty(tmp_path): assert CandidateStore(tmp_path).list("nothing") == []
@pytest.mark.parametrize("slug,cid", [("..", "x"), ("p", "../../etc/passwd"), ("p", ".trash"), ("p/..", "x"), ("p", "")])
def test_traversal_is_refused(tmp_path, slug, cid):                    # Review Focus 2
    st = CandidateStore(tmp_path / "c"); (tmp_path / "secret.svg").write_text("x")
    with pytest.raises(KeyError): st.path(slug, cid)
    with pytest.raises(KeyError): st.remove(slug, cid)
    assert (tmp_path / "secret.svg").exists()

# tests/test_api.py
def boom(params, frame, rng): raise ValueError("kaput")
@pytest.fixture
def client(tmp_path):
    pieces = dict(discover()); pieces["boom"] = Piece(Meta("boom", "Boom", "", "rect", ""), [], boom)
    return TestClient(create_app(tmp_path, pieces))

def test_index_and_pieces(client):
    assert client.get("/").status_code == 200
    d = client.get("/api/pieces").json()
    cw = next(p for p in d["pieces"] if p["slug"] == "chemical-waves")
    assert [c["name"] for c in cw["params"]] == ["sources", "spirals", "wavelength", "elapsed", "stagger", "uneven"]
    assert [c["name"] for c in d["finish"]["params"]] == ["wobble", "border"] and d["page"]["params"][0]["name"] == "composition"

def test_render(client):
    r = client.post("/api/render", json={"piece": "chemical-waves", "seed": 7}).json()
    assert r["svg"].startswith("<svg") and r["stats"]["strokes"] > 5 and r["page"] == {"width": 210, "height": 297, "margin": 16}
    assert r["settings"]["params"]["sources"] == 9

def test_errors(client):
    assert client.post("/api/render", json={"piece": "nope"}).status_code == 404
    r = client.post("/api/render", json={"piece": "boom"})            # Review Focus 4
    assert r.status_code == 422 and r.json()["error"] == "ValueError: kaput"

def test_candidate_lifecycle(client):
    c = client.post("/api/candidates", json={"piece": "chemical-waves", "seed": 5, "params": {"sources": 3}}).json()
    assert c["seed"] == 5 and c["settings"]["params"]["sources"] == 3
    assert [x["id"] for x in client.get("/api/candidates/chemical-waves").json()] == [c["id"]]
    svg = client.get(c["url"]); assert svg.status_code == 200 and svg.headers["content-type"].startswith("image/svg+xml")
    assert client.delete(f"/api/candidates/chemical-waves/{c['id']}").status_code == 204
    assert client.get("/api/candidates/chemical-waves").json() == [] and client.get(c["url"]).status_code == 404
    assert client.delete("/api/candidates/chemical-waves/..%2F..%2Fx").status_code == 404
```

`tests/test_api.py::test_index_and_pieces` needs `inkfield/web/index.html` to exist; create a one-line placeholder in this task (Task 9 replaces it).

- [ ] **Step 2: Run, expect fail. Step 3: Implement. Step 4: Run, expect pass.**
- [ ] **Step 5: Smoke-run** — `uv run inkfield serve --no-browser --port 8765 &`, then `curl -s localhost:8765/api/pieces | head -c 200` shows JSON; kill the server.
- [ ] **Step 6: Commit** — `feat: local server and candidate storage`.

---

### Task 9: The front end

**Files:**
- Create/replace: `inkfield/web/index.html`, `inkfield/web/app.css`, `inkfield/web/app.js`
- Reference: `docs/superpowers/specs/2026-11-10-inkfield-mockup.html`

**Interfaces — Consumes:** the HTTP API of Task 8, exactly as tabled there.

Take the mockup's markup structure and its whole stylesheet (colour tokens, grid layout, panel, sliders, segmented buttons, info button, tray, thumbnail × button) as the starting point, split into the three files. Do not port its `generate`, marching-squares or `svgBody` code: all geometry comes from `/api/render`.

Required behaviour (spec §12):

- **Start-up:** fetch `/api/pieces`; build the left rail from the pieces (no placeholders); build the right panel as three sections from the declarations: the piece's params (title = piece title, *i* = piece info), Finishing (*i* = finish info), Page. Control kinds: `slider` → label, value with unit, range input; `choice` → segmented buttons; `toggle` → segmented `on`/`off`.
- **Info text** is hidden until its *i* button is clicked; the button toggles it and reflects state with `aria-expanded`.
- **Rendering:** any change calls `POST /api/render`. At most one request is in flight; if settings change meanwhile, exactly one follow-up request is sent with the newest settings when the current one returns. A response is shown only if it is the newest one requested.
- **Preview:** the returned SVG is inserted into the paper element, scaled to fit the stage at the page's true proportions (paper-white, shadow as in the mockup). The margin guide is a separate overlay drawn by the front end from `page.margin`; it is never part of the SVG.
- **Statistics line:** `210×297 mm · 50 strokes · 3.3 m drawn · 1.2 m travel · ≈ 4 min · 132 ms` (last value: request round-trip time).
- **Errors:** a non-200 render response shows its `error` text in the statistics line in the accent colour and leaves the previous preview in place.
- **Seed:** number field and reroll button (random integer 0–99999).
- **Keep candidate:** `POST /api/candidates` with the current settings; append the returned item to the tray.
- **Tray:** on start and on piece change, `GET /api/candidates/{slug}`. Thumbnails are `<img src=url>` of the saved file. Clicking one applies its `settings` (seed, params, finish, page) to all controls and re-renders. A × shown on hover calls `DELETE` and removes the thumbnail; no confirmation.
- **Export SVG:** downloads the SVG string of the preview currently shown as `<slug>-seed<seed>.svg`.
- **Persistence:** current piece, seed, and per-piece params, finish and page settings are stored in `localStorage` under `inkfield.state.v1` on every change and restored on load; unreadable or stale content is ignored (the server resolves leftovers anyway).
- **Reset:** double-clicking a slider restores its default.
- **Theme:** chrome follows `prefers-color-scheme`; the paper stays paper-white with black ink.
- The header shows the name `inkfield` without the mockup's "mockup · working title" tag.

- [ ] **Step 1: Build the three files.**
- [ ] **Step 2: Run the existing suite** — `uv run pytest -q`, expect pass (the index test still holds).
- [ ] **Step 3: Check it in a real browser engine.** Start `uv run inkfield serve --no-browser --port 8765`. Take headless screenshots at 1400×900 with `chromium --headless --screenshot=… --virtual-time-budget=4000 http://127.0.0.1:8765/` and of the mockup file; read both images and compare layout, spacing and tone. Then drive the remaining behaviours with a short throwaway script using Chromium's remote debugging protocol, or, if that is not practical, with temporary `?test=` query hooks that are removed before committing. Confirm each of: fill-page composition renders; A3 landscape renders; a kept candidate appears, restores settings on click and disappears on ×; an induced error (stop the server, move a slider) shows a message and keeps the preview; reload restores settings; dark scheme (`--force-dark-mode` or emulation) keeps the paper white.
- [ ] **Step 4: Fix what the check found; repeat Step 3 until clean.** State in the task report which behaviours were verified and how; say plainly if any could not be verified.
- [ ] **Step 5: Commit** — `feat: studio front end`.

---

### Task 10: Documentation and final check

**Files:**
- Create: `README.md`, `docs/adding-a-piece.md`
- Test: `tests/test_docs_example.py`

`README.md`: what inkfield is (five lines), how to start it (`uv sync`, `uv run inkfield`), the folder map from the spec's §7 with one line each, how to render from the command line, where kept candidates and the trash live, and a pointer to `docs/adding-a-piece.md`.

`docs/adding-a-piece.md` is the first draft of the future skill's recipe (spec §13): the piece contract (docstring, `META`, `PARAMS`, `generate`); a complete minimal example piece of about 25 lines (concentric circles with a "rings" slider and a "spacing" slider, framed shape `circle`); what a piece must not do (clip, draw borders, import anything but `inkfield.core` and numpy, use randomness other than `rng`); how to check it (`uv run inkfield render <slug> -o /tmp/x.svg`, then look at it; `uv run pytest -q`); which `core` tools exist and what each is for.

- [ ] **Step 1: Write the failing test** — the example in the doc must actually work:

```python
def test_documented_example_piece_runs(tmp_path, monkeypatch):
    text = Path("docs/adding-a-piece.md").read_text()
    code = re.search(r"```python\n(\"\"\".*?)```", text, re.S).group(1)     # the first block that starts with a docstring
    pkg = tmp_path / "docpieces"; pkg.mkdir(); (pkg / "__init__.py").write_text(""); (pkg / "rings.py").write_text(code)
    monkeypatch.syspath_prepend(str(tmp_path))
    pieces = discover("docpieces"); slug = next(iter(pieces))
    r = render(pieces, slug, seed=1); assert r.stats["strokes"] >= 3
```

- [ ] **Step 2: Run, expect fail. Step 3: Write both documents. Step 4: Run the whole suite, expect pass.**
- [ ] **Step 5: Readability pass.** Re-read `inkfield/pieces/chemical_waves.py` and `inkfield/core/contours.py` top to bottom as someone learning the idea: the docstring explains the model before the code, names match the docstring's words, no step needs knowledge of the server. Fix what does not read well; re-run the suite.
- [ ] **Step 6: End-to-end.** `uv run inkfield render chemical-waves --seed 7 -o <scratch>/final.svg`; screenshot the SVG and compare with the steering images once more. Confirm `git status` shows no `candidates/`, `.venv/` or `.superpowers/` files staged.
- [ ] **Step 7: Commit** — `docs: README and adding-a-piece guide`.
