import pytest

from inkfield.cli import main
from inkfield.core.rng import seed_number
from inkfield.page.svg import read_settings


def test_render_writes_a_file(tmp_path, capsys):
    out = tmp_path / "a.svg"
    assert main(["render", "chemical-waves", "--seed", "7", "--format", "A3", "--set", "sources=4", "-o", str(out)]) == 0
    s = read_settings(out.read_text()); assert s["seed"] == 7 and s["page"]["format"] == "A3" and s["params"]["sources"] == 4
    assert "strokes" in capsys.readouterr().out
def test_unknown_slug_returns_2(tmp_path): assert main(["render", "nope", "-o", str(tmp_path / "x.svg")]) == 2
def test_list(capsys): assert main(["list"]) == 0 and "chemical-waves" in capsys.readouterr().out
def test_seed_must_be_a_whole_number(tmp_path, capsys):
    with pytest.raises(SystemExit) as stop: main(["render", "chemical-waves", "--seed", "abc", "-o", str(tmp_path / "x.svg")])
    assert stop.value.code == 2 and "invalid int value: 'abc'" in capsys.readouterr().err and not (tmp_path / "x.svg").exists()
@pytest.mark.parametrize("seed", ["-5", "12345678901234567890"])
def test_negative_and_large_seeds_still_render(tmp_path, seed):
    out = tmp_path / "a.svg"
    assert main(["render", "chemical-waves", "--seed", seed, "--set", "sources=2", "-o", str(out)]) == 0
    assert read_settings(out.read_text())["seed"] == seed_number(int(seed))
