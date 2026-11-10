import re
import time
import xml.etree.ElementTree as ET

import numpy as np
import pytest

from inkfield.core.piece import Meta, Piece, discover
from inkfield.page.svg import read_settings
from inkfield.render import render

PIECES = discover()


def test_same_inputs_same_bytes():
    a = render(PIECES, "chemical-waves", seed=7); b = render(PIECES, "chemical-waves", seed=7)
    assert a.svg == b.svg and a.svg != render(PIECES, "chemical-waves", seed=8).svg

def test_settings_round_trip_reproduces_the_svg():
    a = render(PIECES, "chemical-waves", seed=11, params={"sources": 4}, finish={"wobble": 0.3}, page={"format": "Square"})
    s = read_settings(a.svg); assert s == a.settings
    assert render(PIECES, s["piece"], s["seed"], s["params"], s["finish"], s["page"]).svg == a.svg

@pytest.mark.parametrize("fmt", ["A4", "A3", "Square"])
@pytest.mark.parametrize("orient", ["portrait", "landscape"])
@pytest.mark.parametrize("comp", ["framed", "fill page"])
def test_every_page_combination_stays_inside_the_margin(fmt, orient, comp):
    r = render(PIECES, "chemical-waves", seed=3, params={"elapsed": 1.2}, page={"format": fmt, "orientation": orient, "composition": comp})
    xy = np.array(re.findall(r"(-?\d+\.\d\d) (-?\d+\.\d\d)", r.svg), float)
    m = r.page.margin - 0.02
    assert len(xy) > 100 and xy[:, 0].min() >= m and xy[:, 1].min() >= m and xy[:, 0].max() <= r.page.width - m and xy[:, 1].max() <= r.page.height - m

def test_garbage_settings_do_not_crash():           # Review Focus 1
    r = render(PIECES, "chemical-waves", seed="abc", params={"sources": "many", "gone": 3, "wavelength": 1e9}, finish={"border": "off"}, page={"format": "B5", "margin": -4})
    assert r.settings["seed"] == 0 and r.settings["params"]["sources"] == 9 and r.settings["params"]["wavelength"] == 14
    assert r.settings["page"]["format"] == "A4" and r.settings["page"]["margin"] == 5 and "gone" not in r.settings["params"]

@pytest.mark.parametrize("junk", [[1, 2], "abc", 7, None, ""])
def test_settings_that_are_not_dicts_fall_back_to_defaults(junk):
    r = render(PIECES, "chemical-waves", seed=5, params=junk, finish=junk, page=junk)
    d = render(PIECES, "chemical-waves", seed=5)
    assert r.svg == d.svg

@pytest.mark.parametrize("seed, expected", [("", 0), (-1, 2**32 - 1), (2**40 + 3, 3), (7.9, 7), ("12", 12), (None, 0), (10**400, 0), ("1e400", 0)])
def test_seed_is_coerced_like_make_rng(seed, expected):
    assert render(PIECES, "chemical-waves", seed=seed, params={"elapsed": 0.08}).settings["seed"] == expected

def test_nothing_to_draw_is_still_a_valid_svg():    # Review Focus 3
    r = render(PIECES, "chemical-waves", seed=1, params={"elapsed": 0.08, "wavelength": 14, "sources": 1, "stagger": 1}, finish={"border": False}, page={"format": "Square", "margin": 40})
    ET.fromstring(r.svg); assert r.stats["strokes"] == len(re.findall("<path", r.svg))

def test_a_piece_that_draws_nothing_gives_an_empty_valid_svg():    # Review Focus 3
    blank = Piece(meta=Meta("blank", "Blank", "", "rect", ""), params=[], generate=lambda params, frame, rng: [])
    r = render({"blank": blank}, "blank", finish={"border": False})
    ET.fromstring(r.svg); assert "<path" not in r.svg
    assert r.stats == {"strokes": 0, "drawn_m": 0.0, "travel_m": 0.0, "minutes": 0.0}

def test_unknown_piece():
    with pytest.raises(KeyError): render(PIECES, "nope")

def test_speed_default_a4():
    render(PIECES, "chemical-waves", seed=7)                         # warm-up
    t = time.perf_counter(); render(PIECES, "chemical-waves", seed=7); assert time.perf_counter() - t < 0.5

def test_speed_a3_fill_24_sources():
    t = time.perf_counter(); render(PIECES, "chemical-waves", seed=7, params={"sources": 24}, page={"format": "A3", "composition": "fill page"}); assert time.perf_counter() - t < 2.0

def test_heaviest_settings_finish():                # Review Focus 5
    t = time.perf_counter()
    render(PIECES, "chemical-waves", seed=7, params={"sources": 24, "wavelength": 2, "elapsed": 2}, page={"format": "A3", "composition": "fill page"})
    assert time.perf_counter() - t < 20
