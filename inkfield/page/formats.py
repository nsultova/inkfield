"""Paper formats, and the frame a piece draws into on that paper.

A page is a sheet of a given size with an empty margin all round. The piece never sees the page,
only a frame inside the margin: either the whole rectangle inside the margin ("fill page"), or the
largest frame of the piece's own preferred shape that fits there, centred ("framed").
"""
from dataclasses import dataclass

from inkfield.core.controls import Choice, Slider
from inkfield.core.frame import Frame

FORMATS = {"A4": (210, 297), "A3": (297, 420), "Square": (250, 250)}      # portrait width, height in mm
PAGE_PARAMS = [
    Choice("composition", "Composition", ("framed", "fill page"), "framed"),
    Choice("format", "Format", ("A4", "A3", "Square"), "A4"),
    Choice("orientation", "Orientation", ("portrait", "landscape"), "portrait"),
    Slider("margin", "Margin", 5, 40, 1, 16, " mm"),
    Choice("pen", "Pen", ("0.2", "0.3", "0.5", "0.8"), "0.3"),
]


@dataclass(frozen=True)
class Page:
    width: float     # mm
    height: float    # mm
    margin: float    # mm, kept empty on every side


def make_page(settings: dict) -> Page:
    """The sheet described by resolved page settings; landscape swaps width and height."""
    width, height = FORMATS[settings["format"]]
    if settings["orientation"] == "landscape":
        width, height = height, width
    return Page(width, height, settings["margin"])


def frame_for(page: Page, composition: str, framed_shape: str) -> Frame:
    """The frame the piece draws into, centred on the page.

    The space inside the margin is a rectangle with half-sizes (width / 2 - margin) and
    (height / 2 - margin). "fill page" uses that rectangle. "framed" fits the piece's shape in it:
    a rectangle fills it already, and the largest circle has the smaller half-size as its radius.
    """
    half_w = page.width / 2 - page.margin
    half_h = page.height / 2 - page.margin
    centre_x, centre_y = page.width / 2, page.height / 2
    if composition not in ("framed", "fill page"):
        raise ValueError(f"composition must be 'framed' or 'fill page', got {composition!r}")
    if composition == "fill page" or framed_shape == "rect":
        return Frame("rect", centre_x, centre_y, half_w, half_h)
    radius = min(half_w, half_h)
    return Frame(framed_shape, centre_x, centre_y, radius, radius)
