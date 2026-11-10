from inkfield.cli import main
from inkfield.page.svg import read_settings


def test_render_writes_a_file(tmp_path, capsys):
    out = tmp_path / "a.svg"
    assert main(["render", "chemical-waves", "--seed", "7", "--format", "A3", "--set", "sources=4", "-o", str(out)]) == 0
    s = read_settings(out.read_text()); assert s["seed"] == 7 and s["page"]["format"] == "A3" and s["params"]["sources"] == 4
    assert "strokes" in capsys.readouterr().out
def test_unknown_slug_returns_2(tmp_path): assert main(["render", "nope", "-o", str(tmp_path / "x.svg")]) == 2
def test_list(capsys): assert main(["list"]) == 0 and "chemical-waves" in capsys.readouterr().out
