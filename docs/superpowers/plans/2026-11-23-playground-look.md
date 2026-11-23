# Playground Look and Gallery Entry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the inkfield studio to match the sig2void.com playground and open the app on a gallery of piece previews that link into each piece's studio.

**Architecture:** Only `inkfield/web/` changes. One page holds two views, gallery and studio, switched by `location.hash` (`#` = gallery, `#<slug>` = studio). The server and its API stay as they are; gallery previews use the existing `POST /api/render`.

**Tech Stack:** plain HTML, CSS and JavaScript (no build step, no framework); pytest for static checks of the served files.

**Spec:** `docs/superpowers/specs/2026-11-23-playground-look-design.md`

## Global Constraints

- No Python source under `inkfield/` changes. No new routes.
- Nothing loads from the network at run time: no `http://` or `https://` reference in `inkfield/web/*.html`, `*.css`, `*.js` other than the SVG namespace string `http://www.w3.org/2000/svg`.
- Colour tokens, dark and light, exactly as listed in the spec under "Decided details".
- Fonts: Newsreader and IBM Plex Mono as woff2 in `inkfield/web/fonts/`.
- `STORAGE_KEY = "inkfield.state.v1"` and the shape of what it stores stay as they are, so settings saved before this change still load.
- Every behaviour listed under the spec's "Anti-goals" still works.
- Start every shell with `source .venv/bin/activate`. Suite: `pytest -q` (131 passed before this work).
- Reference for the look: the site's stylesheet rules named `.pg-*`, `.sheet-head`, `.sheet-nav`, `.index--pg`, `.work`, `.caption`, `.sigil`, `.mode-toggle`, `.mts*`. A copy may be at `<scratchpad>/site/main.css`; otherwise fetch `https://sig2void.com/playground/water-droplets/` and the stylesheet it links.

## Review Focus

1. Settings stored by the old UI under `inkfield.state.v1` load without error and show the same plot. (Task 1 browser check)
2. An address with an unknown `#slug` shows the gallery, not a blank page. (Task 2 browser check)
3. A gallery preview whose render fails shows a short message in its card; the other cards and the links still work. (Task 2 browser check)
4. Leaving a studio while a render is in flight never paints that render onto another piece or onto the gallery. (Task 2 browser check)
5. With `localStorage` unavailable, the page still loads and the theme toggle still switches. (Task 1 browser check)

There is no JavaScript test runner in this project and adding one is out of scope; these five are checked in a real browser (headless Chromium or Firefox via a throwaway script kept outside the repo), and the check's outcome goes in the task report.

---

### Task 1: Fonts, theme and the restyled studio

**Files:**
- Create: `inkfield/web/fonts/*.woff2`, `tests/test_web_static.py`
- Modify: `inkfield/web/index.html`, `inkfield/web/app.css`, `inkfield/web/app.js`

**Interfaces:**
- Produces: in `index.html`, a `<section id="studio">` that wraps everything the studio shows, and a header `<a id="home" href="#">` reading `$_inkfield`. In `app.js`, `choosePiece(slug)` keeps its name and meaning. Root attribute `data-mode="dark" | "light"` on `<html>` selects the palette; the choice is stored under `localStorage["inkfield.mode"]`.

- [ ] **Step 1: Write the failing tests** in `tests/test_web_static.py`

```python
import re
from pathlib import Path
from fastapi.testclient import TestClient
from inkfield.server.app import create_app

WEB = Path(__file__).parent.parent / "inkfield" / "web"

def test_no_network_references():
    for path in [*WEB.glob("*.html"), *WEB.glob("*.css"), *WEB.glob("*.js")]:
        text = path.read_text().replace("http://www.w3.org/2000/svg", "")
        assert not re.search(r"https?://", text), path.name

def test_fonts_are_bundled_and_served(tmp_path):
    css = (WEB / "app.css").read_text()
    names = re.findall(r"url\(['\"]?(fonts/[^'\")]+\.woff2)", css)
    assert any("newsreader" in n.lower() for n in names)
    assert any("plex" in n.lower() for n in names)
    client = TestClient(create_app(candidates_dir=tmp_path), base_url="http://127.0.0.1")
    for name in names:
        assert client.get("/" + name).content[:4] == b"wOF2", name

def test_site_palette_is_present():
    css = (WEB / "app.css").read_text().replace(" ", "")
    for token in ["--ground:#0a0b0e", "--accent:#b7a6dc", "--ground:#c3b6a6", "--accent:#6e1218"]:
        assert token in css, token
```

Match the client construction to how `tests/test_api.py` builds its client.

- [ ] **Step 2: Run** `pytest -q tests/test_web_static.py`. Expected: the fonts and palette tests fail.

- [ ] **Step 3: Add the fonts.** Download from sig2void.com every woff2 its `@font-face` rules name for Newsreader (roman) and IBM Plex Mono (400, and 700 if the site ships it) into `inkfield/web/fonts/`. Declare them in `app.css` with `font-display: swap`. If the site ships no 700 weight, do not synthesise one: use 400 with the tracking.

- [ ] **Step 4: Restyle the studio.** Rewrite `app.css` on the spec's tokens and details; restructure `index.html` and the DOM-building functions in `app.js` (`buildPanel`, `section`, `controlRow`, the tray and top-bar code) to this layout:

```
header:  $_inkfield (a#home)                               [mode toggle]
h1:      $_<Piece title>
box:     | controls 295px, collapsible groups | toolbar: seed  ⚡ randomize  stats  keep  save SVG |
         |                                    | well: white sheet                                 |
         |                                    | tray: KEPT thumbnails                             |
```

Decisions: each control section becomes a group whose header button collapses it (collapsed state is not stored); the info button and its text stay inside the group body; the stats line moves into the toolbar; "save SVG" is the accent-outlined button at the right; the piece rail (`<nav id="pieces">`, `buildRail`, `markRail`) is removed, since the gallery in Task 2 replaces it and until then the app opens on the stored or first piece as today; below 760 px wide the controls stack under the sheet. The mode toggle sets `data-mode` and stores it, with every `localStorage` access in try/catch; default is dark. The top comment of `app.css` points to this spec.

- [ ] **Step 5: Run** `pytest -q`. Expected: 134 passed.

- [ ] **Step 6: Browser check.** Start `inkfield --no-browser` in a scratch directory, drive it headless, and confirm with screenshots (dark and light) read back as images: the plot renders; a slider change re-renders; double-click resets a slider; info text opens; a group collapses; keep adds a thumbnail, clicking it returns to it, × removes it; save SVG downloads; Review Focus 1 and 5. Stop the server afterwards.

- [ ] **Step 7: Commit** `feat: playground look for the studio`.

### Task 2: Gallery and hash navigation

**Files:**
- Modify: `inkfield/web/index.html`, `inkfield/web/app.css`, `inkfield/web/app.js`, `README.md`, `tests/test_web_static.py`

**Interfaces:**
- Consumes: `section#studio`, `a#home`, `choosePiece(slug)` from Task 1; `catalogue` (the `/api/pieces` answer) and `postJSON("/api/render", body)` already in `app.js`.
- Produces: `<section id="gallery">`; `route()` in `app.js`, called on `hashchange` and at start, which shows the gallery for an empty or unknown hash and otherwise calls `choosePiece(slug)` and shows the studio.

- [ ] **Step 1: Add the failing test**

```python
def test_page_has_both_views():
    html = (WEB / "index.html").read_text()
    for needle in ['id="gallery"', 'id="studio"', 'id="home"']:
        assert needle in html, needle
```

- [ ] **Step 2: Run it.** Expected: fails on `id="gallery"`.

- [ ] **Step 3: Build the gallery.** One `<a class="work" href="#<slug>">` per piece in catalogue order: the preview on a white sheet, then a caption `$_<Title>` with `procedural · SVG` beneath, styled after the site's `.index--pg`, `.work`, `.caption`, `.sigil`. Previews: `POST /api/render` with seed 0 and no overrides, one request per piece, inserted through the existing `plotNode` sanitiser; a failed render puts a short message in the card. Previews are rendered once per page load. A one-paragraph lede above the grid in the serif face.

- [ ] **Step 4: Add `route()`.** Exactly one of `#gallery` / `#studio` is visible. Entering a studio restores that piece's stored settings as `choosePiece` does today. A render answer that arrives after the view or piece has changed is dropped (extend the existing `version` guard). The page title is `inkfield` on the gallery and `<Title> · inkfield` in a studio.

- [ ] **Step 5: Update `README.md`** where it describes the screen or the piece list, in two or three sentences.

- [ ] **Step 6: Run** `pytest -q`. Expected: 135 passed.

- [ ] **Step 7: Browser check.** Gallery screenshot, dark and light; click a card, land in the studio; back returns to the gallery; forward returns to the studio; reload on `#chemical-waves` stays in the studio; Review Focus 2, 3 (force a failure by answering the render request with a 500 in the driver) and 4.

- [ ] **Step 8: Commit** `feat: gallery entry with hash navigation`.
