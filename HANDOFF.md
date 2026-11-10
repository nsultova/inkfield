# HANDOFF

Session ended: 2026-11-10 (evening)
Branch / HEAD: master (inkfield-studio @ 528f000 merged by fast-forward)
Home: ~/WORK/PROJECTS/inkfield, its own repository (GitHub: nsultova/inkfield, private). Copied on
2026-11-10 from the training repo ~/WORK/AiEXP/AiEXP-procedural-art, which stays on its old master.

## Goal
"inkfield": a local browser studio for plottable procedural art (image → Claude writes a
generator → sliders → SVG for an AxiDraw A3). Project 1 of 3 (the app + Chemical waves).

## State
- Done: all 10 plan tasks built by `builder` agents, each reviewed by a `reviewer`; a
  whole-branch review ("ready to merge") and one fix wave on top. Suite: 131 passed.
- Speed on the Ryzen 5 5500U: default A4 111 ms, A3 fill page with 24 pacemakers about
  0.5 s, heaviest settings about 2.8 s.
- Neda has run the app and likes it; the project moved to its own repository to be developed further.
- Blocked: none.

## Next action
Project 2 (drawing → contours and hatching) starts with brainstorming, in a fresh session.
Run the app with `uv sync`, `uv run inkfield`.

## Decisions made during the build (Claude's rulings, all reversible)
- The Unevenness strength is capped at 8 % of the noise wavelength so bent space cannot
  fold; the slider saturates for long wavelengths. 0.08 was found by experiment.
- The piece gets the frame inside the border when the border is on (as the plan says);
  spec §8 says "largest shape inside the margin" and needs one clause if Neda agrees.
- `simplify` in `core/polyline.py` is the batched, faster version; its docstring teaches
  the plain algorithm first. Reverting to the simple loop still meets the speed targets
  (167 ms default A4).
- Pacemaker randomness is drawn as a fixed block of 24, so adding a pacemaker leaves the
  others as they were.
- The server refuses requests whose Host is not 127.0.0.1 or localhost.
- `<inkfield>` settings element inside SVG `<metadata>` is allowed.
- Three plan tests were adjusted or supplemented: the seam test ignores line ends on the
  grid edge; a real zero-stroke render test was added; a no-fold test was added.

## Landmines
- `.superpowers/sdd/2026-11-10-inkfield-studio/progress.md` (git-ignored) is the build
  ledger: every ruling and every deferred minor finding. Read it before deleting
  `.superpowers/`. The older flat files in `.superpowers/sdd/` belong to the discarded
  `genart` build.
- `candidates/` is created in whatever folder the server is started from.
- A pytest filter hides starlette's "httpx with testclient is deprecated" warning;
  starlette now prefers a dev dependency named `httpx2`. Dependency change left to Neda.
- Piece switching in the browser has never been exercised (only one piece exists).
- The full build transcript and the session memory of the build live under the old folder's
  Claude project (`~/.claude/projects/-home-nea-WORK-AiEXP-AiEXP-procedural-art/`); the three
  memory files were copied to this folder's project.
- Markdown files in this repo get reflowed on save by something outside the session;
  search by heading, not line number.

## Read first (next session)
- HANDOFF.md — always first
- `README.md` and `docs/adding-a-piece.md`
- `inkfield/pieces/chemical_waves.py` — the model of a finished piece
- `docs/superpowers/specs/2026-11-10-inkfield-studio-design.md` §13 for projects 2 and 3
