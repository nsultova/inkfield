# Porting the gen_art_dev prototypes into inkfield (short design)

Agreed with Neda on 2026-11-23: six prototypes from `~/PROJECTS/art_thingies/gen_art_dev` become
inkfield pieces, with curated sliders.

| Piece (slug) | Source |
|---|---|
| `geological-strata` | `geological_strata.py` |
| `turbulent-lines` | `turbulent_lines.py` (not the variants in `turbulent-lines-experiments/`) |
| `coiled-tendrils` | `coiled_tendrils.py` |
| `water-droplets` | `water_droplets_v2.py` (v2 replaces v1; the stroke-weight fade is dropped) |
| `glass-droplets` | `glass_droplets.py` |
| `mirror-shards` | `mirror_shards.py` (its `tests/test_mirror_shards.py` shows what the author pinned) |

Left out: `bz_reaction` (Chemical waves covers it) and the JavaScript-only ferromagnetic page.

## Rules for every port

- A port is a rewrite to the contract in `docs/adding-a-piece.md`, with
  `inkfield/pieces/chemical_waves.py` as the model of a finished piece. The prototype's `.html`
  twin and its `scripts/` helpers are not carried over.
- **Keep the character.** The default render should be recognisably the prototype's picture
  (compare with its SVGs in the source folder's `output/` or its `.html` page). Individual seeds
  will not match, because all randomness now comes from the `rng` the piece is handed.
- **Curated sliders: 8 to 10 per piece**, the ones that change the picture most, with plain-word
  labels. Every other prototype parameter becomes a named module-level constant at the prototype's
  default, with a one-line comment, so it is easy to promote to a slider later.
- **Any page.** Lengths that the prototype fixed in millimetres for one canvas are measured against
  the frame (`frame.scale`, `frame.bbox`), so A4, A3, square, portrait, landscape, framed and
  fill-page all give a sensible picture. Choose the `framed_shape` that suits the piece.
- **One pen, lines only.** No fills, no varying stroke width.
- **Readable first.** Neda learns from this code: a docstring that explains the idea before the
  code, small named steps, plain numpy. No new dependencies.
- **Speed.** Default A4 render under about 1 s, heaviest slider settings under about 3 s on a
  Ryzen 5 5500U.
- **`META.seed`**: a seed whose default render is a good gallery card; chosen by looking.
- **Tests** in `tests/test_<piece>.py`, after `tests/test_chemical_waves.py`: same seed gives the
  same strokes and another seed differs; strokes are well formed; every control changes the
  picture; and one or two tests that pin the piece's own idea.
- A port adds exactly two files: the piece and its test. Anything else it seems to need (a helper
  in `inkfield/core`, a doc change) is reported, not done.
