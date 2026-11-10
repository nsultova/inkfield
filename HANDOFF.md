# HANDOFF

Session ended: 2026-11-10 17:04
Branch / HEAD: master @ f04d7eb (spec, plan, mockup, .gitignore and this file are untracked)

## Goal
Design "inkfield": a local browser studio for plottable procedural art (image → Claude
writes a generator → sliders → SVG for an AxiDraw A3), then build project 1 of 3.

## State
- Done: design approved by Neda — `docs/superpowers/specs/2026-11-10-inkfield-studio-design.md`
- Done: interactive mockup approved (v2) — `docs/superpowers/specs/2026-11-10-inkfield-mockup.html`
- Done: implementation plan, 10 tasks, approved — `docs/superpowers/plans/2026-11-10-inkfield-studio.md`
- Done: `.gitignore` (`.superpowers/`, `.venv/`, caches, `candidates/`)
- In flight: nothing built. No product code exists yet.
- Blocked: none

## Next action
Invoke `superpowers:subagent-driven-development` on
`docs/superpowers/plans/2026-11-10-inkfield-studio.md`, starting at Task 1. Neda chose
subagent-driven execution: `builder` agents implement one task each, `reviewer` agents
check each task, Fable orchestrates. Branch off master first; Task 1's commit picks up
the untracked docs.

## Decisions
- Fresh start. The old `genart` tool is discarded; port nothing from it or from
  `steering-material/*.py`. The mockup overrides `steering-material/ui-example-*.png`.
- Python + numpy + FastAPI + no-build front end, managed by `uv`. Not Rust: Neda reads
  the math, and a new piece is written every session.
- Contour tracing is written in-project (readable marching squares). No scipy,
  scikit-image, shapely or contour library.
- Chemical waves is a geometric arrival-time model, not a reaction-diffusion simulation.
- Default for any image: generate new pictures following the same rules. Reproduce a
  specific image only when Neda says so.
- Dashed/dotted lines removed "for now" at Neda's request. Do not add them.
- "Keep candidate" = draft save, "Export SVG" = keeper save. Neda was asked about
  `goal.md`'s draft/keeper pair and approved without answering; this is Claude's call.
- Removing a candidate moves it to `candidates/.trash/`, no confirmation dialog.
- If the speed targets (200 ms A4 default, 1 s A3 fill) cannot be met, the builder
  stops and reports; it does not add a coarse-while-dragging preview on its own.
- Projects 2 (drawing → hatching) and 3 (the "new piece from image" skill) come later.
  Build neither now.

## Landmines
- `.venv/` and `.pytest_cache/` in the root belong to the old `genart` tool (editable
  install of a package that no longer exists). Plan Task 1 Step 1 deletes them and runs
  `uv sync`. Do not activate the old `.venv` before that.
- The mockup's JavaScript math is a throwaway sketch with known flaws (lines stop a grid
  cell short of seams, messy spiral cores). Port its CSS and markup only (plan Task 9).
- `trace_whole_numbers` (plan Task 3) needs cell size ≤ wavelength / 8, or lines get
  gaps. Chemical waves uses `min(0.5, wavelength / 8)` mm.
- In `tidy`, closed strokes must never be joined: the border outline starts exactly
  where a horizontal line through the centre ends (plan Task 5).
- Chemical waves tests assume `generate` draws pacemaker positions as its first use of
  `rng` (plan Task 4).
- Markdown files in this repo get reflowed on save by something outside the session, so
  line numbers in the spec and plan shift. Search by heading, not line number.

## Read first (next session)
- HANDOFF.md — always first
- `docs/superpowers/plans/2026-11-10-inkfield-studio.md` — header, Global Constraints, Review Focus
- `docs/superpowers/specs/2026-11-10-inkfield-studio-design.md` — sections 5, 8, 9, 12
- Target machine: AMD Ryzen 5 5500U laptop; `uv` and `chromium` are installed.
