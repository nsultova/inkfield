import xml.etree.ElementTree as ET

import numpy as np
import pytest

from inkfield.core.controls import resolve
from inkfield.core.frame import Frame
from inkfield.core.stroke import Stroke
from inkfield.page.formats import PAGE_PARAMS, Page, frame_for, make_page
from inkfield.page.stats import plot_stats
from inkfield.page.svg import read_settings, to_svg


def test_pages():
    assert make_page(resolve(PAGE_PARAMS, None)) == Page(210, 297, 16)
    assert make_page(resolve(PAGE_PARAMS, {"format": "A3", "orientation": "landscape", "margin": 20})) == Page(420, 297, 20)

def test_frames():
    p = Page(210, 297, 16)
    assert frame_for(p, "framed", "circle") == Frame("circle", 105, 148.5, 89, 89)
    assert frame_for(p, "fill page", "circle") == Frame("rect", 105, 148.5, 89, 132.5)
    assert frame_for(p, "framed", "rect") == Frame("rect", 105, 148.5, 89, 132.5)

SET = {"piece": "x", "seed": 7, "params": {"a": 1.5}, "finish": {}, "page": {"format": "A4"}}
STROKES = [Stroke(np.array([[10, 10], [20, 10.004]])), Stroke(np.array([[0., 0], [5, 0], [5, 5], [0, 0]]))]

def test_svg_structure_and_units():
    svg = to_svg(STROKES, Page(210, 297, 16), 0.3, SET)
    root = ET.fromstring(svg)
    assert root.get("width") == "210mm" and root.get("height") == "297mm" and root.get("viewBox") == "0 0 210 297"
    tags = {el.tag.split("}")[1] for el in root.iter()}
    assert tags == {"svg", "metadata", "inkfield", "g", "path"}
    paths = [el.get("d") for el in root.iter("{http://www.w3.org/2000/svg}path")]
    assert paths == ["M10.00 10.00L20.00 10.00", "M0.00 0.00L5.00 0.00L5.00 5.00Z"]
    for bad in ("clip", "transform", "<text", "style="): assert bad not in svg
    assert 'stroke-width="0.3"' in svg and 'fill="none"' in svg

def test_settings_round_trip_and_determinism():
    svg = to_svg(STROKES, Page(210, 297, 16), 0.3, SET)
    assert read_settings(svg) == SET and svg == to_svg(STROKES, Page(210, 297, 16), 0.3, SET)

def test_empty_drawing_is_valid():
    root = ET.fromstring(to_svg([], Page(250, 250, 16), 0.5, SET)); assert len(list(root.iter("{http://www.w3.org/2000/svg}path"))) == 0

def test_stats():
    s = plot_stats([Stroke(np.array([[30., 40], [130, 40]]))])
    assert s["strokes"] == 1 and s["drawn_m"] == pytest.approx(0.1) and s["travel_m"] == pytest.approx(0.05)
    assert s["minutes"] == pytest.approx((100 / 25 + 50 / 75 + 0.35) / 60)
    assert plot_stats([]) == {"strokes": 0, "drawn_m": 0.0, "travel_m": 0.0, "minutes": 0.0}


# Beyond the brief: the cases the dispatch spelled out.

def test_pen_width_and_negative_zero_are_written_cleanly():
    svg = to_svg([Stroke(np.array([[-0.001, 3], [4, -0.004]]))], Page(148.5, 210, 10), 0.1 + 0.2, SET)
    assert 'stroke-width="0.3"' in svg and 'viewBox="0 0 148.5 210"' in svg
    assert 'd="M0.00 3.00L4.00 0.00"' in svg and "-0.00" not in svg

def test_one_group_per_layer_in_ascending_order():
    strokes = [Stroke(np.array([[0., 0], [1, 1]]), layer=2), Stroke(np.array([[0., 0], [2, 2]]), layer=0)]
    groups = ET.fromstring(to_svg(strokes, Page(210, 297, 16), 0.3, SET)).findall("{http://www.w3.org/2000/svg}g")
    labels = [g.get("{http://www.inkscape.org/namespaces/inkscape}label") for g in groups]
    assert labels == ["1", "3"] and [g.get("id") for g in groups] == ["layer1", "layer3"]

@pytest.mark.parametrize("text", [
    "not xml at all",
    '<svg xmlns="http://www.w3.org/2000/svg"><g/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><metadata><inkfield xmlns="https://inkfield.invalid/ns">{broken</inkfield></metadata></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><metadata><inkfield xmlns="https://inkfield.invalid/ns">[1, 2]</inkfield></metadata></svg>',
])
def test_read_settings_rejects_files_it_cannot_read(text):
    with pytest.raises(ValueError):
        read_settings(text)
