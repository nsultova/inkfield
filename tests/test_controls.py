from inkfield.core.controls import Choice, Slider, Toggle, describe, resolve
from inkfield.core.rng import make_rng

C = [Slider("n", "N", 1, 24, 1, 9), Slider("w", "W", 2, 14, 0.1, 5.5, " mm"),
     Choice("fmt", "F", ("A4", "A3"), "A4"), Toggle("b", "B", True)]


def test_defaults():            assert resolve(C, None) == {"n": 9, "w": 5.5, "fmt": "A4", "b": True}
def test_clamp_and_int():       r = resolve(C, {"n": 99.7, "w": -3}); assert r["n"] == 24 and isinstance(r["n"], int) and r["w"] == 2
def test_garbage_falls_back():  assert resolve(C, {"n": "abc", "w": None, "fmt": "B5", "b": "off", "zzz": 1}) == {"n": 9, "w": 5.5, "fmt": "A4", "b": False}
def test_describe():            assert describe(C)[0] == {"kind": "slider", "name": "n", "label": "N", "min": 1, "max": 24, "step": 1, "default": 9, "unit": ""}


def test_rng_seed_coercion():
    assert make_rng("").random() == make_rng(0).random()
    assert make_rng(-1).random() == make_rng(2**32 - 1).random()
    assert make_rng(7, "a").random() != make_rng(7, "b").random()
