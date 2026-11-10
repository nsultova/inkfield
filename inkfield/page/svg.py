"""The SVG file: what goes to the pen plotter and what the preview shows.

Width and height are given in millimetres and the viewBox uses the same numbers, so one SVG
unit is one millimetre and stroke points can be written as they are. Each stroke becomes one
<path>; strokes are grouped into one Inkscape layer per pen (layer 0 is labelled "1"), which is
how the AxiDraw Inkscape extension and saxi tell pens apart. Nothing is filled, clipped or
transformed: what is in the file is exactly what the pen draws.

The settings that made the drawing (piece, seed, every control) are stored as JSON inside
<metadata>, so a file can be traced back and reloaded with `read_settings`.

Same strokes, page, pen and settings give the same bytes: coordinates are rounded to two
decimals (0.01 mm, finer than any pen), and the settings JSON has sorted keys.
"""
import json
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

import numpy as np

SVG_NS = "http://www.w3.org/2000/svg"
INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"
INKFIELD_NS = "https://inkfield.invalid/ns"


def to_svg(strokes, page, pen_mm: float, settings: dict) -> str:
    width, height = number(page.width), number(page.height)
    by_layer = {}
    for stroke in strokes:
        by_layer.setdefault(stroke.layer, []).append(path_data(stroke.points))
    lines = [
        f'<svg xmlns="{SVG_NS}" xmlns:inkscape="{INKSCAPE_NS}"',
        f'     width="{width}mm" height="{height}mm" viewBox="0 0 {width} {height}">',
        f'<metadata><inkfield xmlns="{INKFIELD_NS}">'
        f'{escape(json.dumps(settings, sort_keys=True))}</inkfield></metadata>',
    ]
    for layer in sorted(by_layer) or [0]:
        lines += [
            f'<g inkscape:groupmode="layer" inkscape:label="{layer + 1}" id="layer{layer + 1}" '
            f'fill="none" stroke="#000000"',
            f'   stroke-width="{number(pen_mm)}" stroke-linecap="round" stroke-linejoin="round">',
        ]
        lines += [f'<path d="{d}"/>' for d in by_layer.get(layer, [])]
        lines.append("</g>")
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def path_data(points: np.ndarray) -> str:
    """One stroke as an SVG path: "M x y" to the start, then "L x y" through every later point.

    Points are rounded to two decimals first; adding 0.0 turns a rounded -0.0 into 0.0, so the
    file never says "-0.00". When the first and last points print the same, the path ends with
    "Z" (close the shape) instead of repeating the start point. The whole stroke is formatted
    with one %-format call, which keeps tens of thousands of points fast.
    """
    rounded = np.round(points, 2) + 0.0
    closed = len(rounded) >= 3 and bool((rounded[0] == rounded[-1]).all())
    if closed:
        rounded = rounded[:-1]
    template = "M%.2f %.2f" + "L%.2f %.2f" * (len(rounded) - 1) + ("Z" if closed else "")
    return template % tuple(rounded.ravel().tolist())


def number(value: float) -> str:
    """A size for an attribute: at most three decimals, no trailing zeros, never "-0".

    210.0 → "210", 148.5 → "148.5", 0.1 + 0.2 → "0.3".
    """
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return "0" if text == "-0" else text


def read_settings(svg_text: str) -> dict:
    """The settings JSON stored in an SVG written by `to_svg`.

    Raises ValueError, with a message saying why, for anything it cannot read: text that is not
    XML, an SVG without inkfield settings (from another tool, or edited so the element is gone),
    or settings that are not a JSON object. It does not check the settings against any piece's
    controls; `resolve` does that when they are used.
    """
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as error:
        raise ValueError(f"not readable as XML: {error}") from None
    if root.tag != f"{{{SVG_NS}}}svg":
        raise ValueError(f"not an SVG file: root element is {root.tag!r}")
    element = root.find(f"{{{SVG_NS}}}metadata/{{{INKFIELD_NS}}}inkfield")
    if element is None or not element.text:
        raise ValueError("no inkfield settings in this SVG")
    try:
        settings = json.loads(element.text)
    except json.JSONDecodeError as error:
        raise ValueError(f"inkfield settings are not valid JSON: {error}") from None
    if not isinstance(settings, dict):
        raise ValueError("inkfield settings are not a JSON object")
    return settings
