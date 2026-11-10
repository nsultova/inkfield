# inkfield

inkfield is a small studio for pen-plotter art that runs in your browser, on your own computer.
A piece is one readable Python file: it turns a seed and a few settings into pen strokes in
millimetres. Finishing effects clip, frame and tidy the strokes, and the result is an SVG
ready for a plotter such as the AxiDraw. The math is kept plain so that it can be read and learned
from. The first piece is Chemical waves, after the Belousov–Zhabotinsky reaction.


## Starting it

You need [uv](https://docs.astral.sh/uv/). From the repository root:

```sh
uv sync
uv run inkfield
```

This starts the studio at http://127.0.0.1:8000/ and opens it in your browser. Stop it with
Ctrl+C. The server listens on 127.0.0.1 only, so other computers cannot reach it. Use
`uv run inkfield serve --port 8001` for another port, and `--no-browser` to not open a browser.


## Rendering from the command line

```sh
uv run inkfield list
uv run inkfield render chemical-waves --seed 7 -o /tmp/waves.svg
uv run inkfield render chemical-waves --seed 7 --format A3 --set sources=4 --set wavelength=8 -o /tmp/waves.svg
```

`list` prints every piece: slug and title. `render` writes one SVG and prints the number of
strokes, metres drawn, metres of pen-up travel and an estimate of the plot time.

- `--set name=value` sets one of the piece's controls; repeat it for several.
- Page: `--composition {framed,fill page}`, `--format {A4,A3,Square}`,
  `--orientation {portrait,landscape}`, `--margin MM`, `--pen {0.2,0.3,0.5,0.8}`.
- Finishing: `--wobble 0…1` (hand wobble), `--no-border`.
- See `uv run inkfield render --help`.

The same piece, seed and settings give a byte-identical SVG. This holds for one version of the
code: if a piece's code changes, the same settings may give a different picture. Every SVG
stores the piece, seed and all settings in its `<metadata>`, so a file can always be traced
back.


## Kept candidates and the trash

"Keep candidate" in the studio saves the current drawing as an SVG file in
`candidates/<piece-slug>/`, inside the folder you started `uv run inkfield` from. Removing a
candidate (the × on its thumbnail) does not delete it: the file moves to
`candidates/.trash/<piece-slug>/`, where you can get it back. The `candidates/` folder is
ignored by git.

A kept candidate is its SVG file. The tray shows that file, so a kept picture never changes.
Clicking a thumbnail restores its seed and settings and draws them again with the current code.
If the piece's code has changed since, that new drawing may differ from the kept one: controls
that no longer exist are ignored, and new controls take their defaults.


## Chemical waves: one thing to know

The "Medium unevenness" control is capped so that the medium does not fold over itself (two
nearby points would swap places and rings would cross). The cap was found by experiment, so
this holds in practice, not by proof. The push grows with unevenness and
with the wavelength, so with long wavelengths the cap is reached early and the upper part of
the slider changes nothing more. The docstring of `inkfield/pieces/chemical_waves.py` explains
the whole model.


## Folders

```
inkfield/
  pieces/     one file per piece: its controls and its math, nothing else
  core/       shared, readable building blocks for pieces: seeded randomness, the frame,
              smooth noise, contour tracing, polyline tools, the piece contract
  finish/     effects that turn strokes into strokes: wobble, clip, border, tidy, order
  page/       paper formats, margins and frames; SVG writing; plot statistics
  server/     the HTTP API and candidate storage
  web/        the front end (static files, no build step)
  render.py   one drawing from start to finish: piece, finishing, SVG, statistics
  cli.py      the `inkfield` command
tests/        `uv run pytest -q`
docs/         this kind of documentation; docs/superpowers/ holds the design and the plan
candidates/   kept candidates, made when you keep one, ignored by git
```

`pieces/`, `core/`, `finish/` and `page/` never import the server or the front end and never
touch files or the network. A test checks this.


## Adding a piece

See [docs/adding-a-piece.md](docs/adding-a-piece.md): the piece contract, a complete small
example, how to check a piece from the command line, and the tools in `inkfield.core`.
