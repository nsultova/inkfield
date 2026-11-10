"""Finishing effects: what happens to every piece's strokes after the piece has drawn them.

In order: hand wobble, clip to the inner frame, add the border, tidy, order. Wobble and border
have controls, declared like a piece's; tidy and order have none.
"""
from inkfield.core.controls import Slider, Toggle
from inkfield.core.frame import Frame
from inkfield.core.stroke import Stroke
from inkfield.finish.border import border
from inkfield.finish.clip import clip
from inkfield.finish.order import order
from inkfield.finish.tidy import tidy
from inkfield.finish.wobble import wobble

FINISH_PARAMS = [Slider("wobble", "Hand wobble", 0, 1, 0.01, 0), Toggle("border", "Border", True)]
FINISH_INFO = "Effects that work on any piece, because every piece hands over plain pen strokes."
BORDER_GAP = 0.035   # inset of the inner border line, as a fraction of frame.scale


def inner_frame(outer: Frame, settings: dict) -> Frame:
    """The frame the pattern is clipped to: inset from the outer edge when there is a border."""
    if settings["border"]:
        return outer.inset(BORDER_GAP * outer.scale)
    return outer


def apply(strokes, inner: Frame, outer: Frame, settings: dict, seed) -> list[Stroke]:
    strokes = wobble(strokes, settings["wobble"], seed)
    strokes = clip(strokes, inner)
    if settings["border"]:
        strokes += border(outer, inner)
    return order(tidy(strokes))
