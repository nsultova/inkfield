"""One drawing, start to finish: piece → finishing effects → SVG and plot statistics.

`render` is a pure function. It takes whatever settings arrive (from the browser, a saved file or
the command line), makes them complete and valid with `resolve`, and returns the SVG together with
the exact settings that made it. Those settings are also stored inside the SVG, so feeding them
back in reproduces the same bytes. It reads and writes no files and keeps no state between calls.
"""
from dataclasses import dataclass

from inkfield import finish as finishing
from inkfield.core.controls import resolve
from inkfield.core.piece import Piece
from inkfield.core.rng import make_rng, seed_number
from inkfield.page.formats import PAGE_PARAMS, Page, frame_for, make_page
from inkfield.page.stats import plot_stats
from inkfield.page.svg import to_svg


@dataclass
class RenderResult:
    svg: str
    stats: dict
    page: Page
    settings: dict


def render(pieces: dict[str, Piece], piece: str, seed=0, params=None, finish=None,
           page=None) -> RenderResult:
    """Draw `piece` (a slug in `pieces`; KeyError if unknown) with the given seed and settings."""
    chosen = pieces[piece]
    seed = seed_number(seed)
    params = resolve(chosen.params, params)
    finish = resolve(finishing.FINISH_PARAMS, finish)
    page_settings = resolve(PAGE_PARAMS, page)

    sheet = make_page(page_settings)
    outer = frame_for(sheet, page_settings["composition"], chosen.meta.framed_shape)
    inner = finishing.inner_frame(outer, finish)
    strokes = chosen.generate(params, inner, make_rng(seed, "piece"))
    strokes = finishing.apply(strokes, inner, outer, finish, seed)

    settings = {"piece": piece, "seed": seed, "params": params, "finish": finish,
                "page": page_settings}
    svg = to_svg(strokes, sheet, float(page_settings["pen"]), settings)
    return RenderResult(svg=svg, stats=plot_stats(strokes), page=sheet, settings=settings)
