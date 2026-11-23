# inkfield: playground look and gallery entry (short design)

Approved by Neda on 2026-11-23 in conversation.

## Intent

inkfield should look like the playground on sig2void.com (Neda's own site): near-black ground,
pale ink, lilac accent, Newsreader and IBM Plex Mono, hairline borders. It should open on a
gallery of piece previews; clicking a preview leads into that piece's studio.

## Goals

- **Gallery** at `/#`: a grid of cards, one per piece. Each card shows a real render of the piece
  at its default settings on a white sheet, with a `$_Title` caption and `procedural · SVG` under
  it, as on the site. The whole card is a link to `#<slug>`.
- **Studio** at `/#<slug>`: a header with `$_inkfield` (link back to the gallery), the piece title
  as `$_Title`, then one bordered box: controls on the left (about 295 px) in collapsible groups,
  a toolbar above the sheet (seed, randomize, stats, keep, save SVG), the white sheet in a well,
  and the kept tray below the sheet.
- **Theme**: the site's colour tokens, copied exactly. Dark by default; the site's warm light
  palette on a toggle in the header, remembered in the browser.
- **Fonts**: Newsreader and IBM Plex Mono as woff2 files inside `inkfield/web/fonts/`, so the app
  works offline.
- Back and forward buttons move between gallery and studio.

## Non-goals

- Zoom, pan and fullscreen (a later step).
- Any change to the Python: no new routes, no change to rendering, pieces or candidates.
- Any change to what the controls do, to keeping, exporting or the stored settings.

## Anti-goals

- Loading anything from the network at run time (fonts, scripts, images).
- Losing a behaviour the studio has today: live re-render on change, double-click a slider to
  reset, the info text per section, the margin guide, keep / return to / delete a candidate,
  export, the error line, settings remembered per piece.

## Approaches

1. **Restyle in place, hash navigation (chosen).** Only `inkfield/web/` changes. Gallery and
   studio are two views in the one page, switched by `location.hash`. The server keeps serving
   static files. Smallest change, and the back button works.
2. Two real pages with server routes (`/` and `/piece/<slug>`). Cleaner addresses, but touches
   the server and its tests for no gain in a local tool.
3. A front-end framework or build step. Rejected: the app is 670 lines of plain files and should
   stay readable.

## Decided details

- Tokens (dark): `--ground:#0a0b0e; --ground-deep:#06070a; --ink:#c8d0d2; --ink-dim:#8a9296;
  --ink-quiet:#798185; --ink-faint:#2a2f35; --accent:#b7a6dc; --accent-deep:#9182b4`.
- Tokens (light): `--ground:#c3b6a6; --ground-deep:#b5a897; --ink:#1f1a15; --ink-dim:#3a332b;
  --ink-quiet:#4d453b; --ink-faint:#9a8d7d; --accent:#6e1218; --accent-deep:#4d0d12`.
- Fonts: `--serif: Newsreader, Georgia, serif` for body and titles;
  `--mono: "IBM Plex Mono", ui-monospace, monospace` for header, captions, controls, buttons.
- Control styling follows the site's `.pg-*` rules: group headers 10 px bold uppercase with
  .14em tracking and an accent caret; sliders a 2 px track with an 11 px round accent thumb;
  buttons `--ground-deep` with a hairline border, accent border on hover; "save SVG" outlined in
  accent and pushed to the right; the sheet white with a 2 px radius and a soft shadow.
- Gallery grid: `repeat(auto-fill, minmax(300px, 1fr))`, card image dims to .84 opacity on hover.

## Left to the builder (Claude's calls)

- Gallery previews come from `POST /api/render` with each piece's defaults and seed 0.
- An unknown `#slug` falls back to the gallery.
- The info text per section stays behind its small button inside the group.
- Narrow windows: controls stack under the sheet; no drawer toggle.
- The old mockup in `docs/superpowers/specs/2026-11-10-inkfield-mockup.html` is left as history;
  the comment at the top of `app.css` should point here instead.
