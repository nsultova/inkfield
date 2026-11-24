import re
from pathlib import Path

from fastapi.testclient import TestClient

from inkfield.server.app import create_app

WEB = Path(__file__).parent.parent / "inkfield" / "web"


def test_no_network_references():
    for path in [*WEB.glob("*.html"), *WEB.glob("*.css"), *WEB.glob("*.js")]:
        text = path.read_text().replace("http://www.w3.org/2000/svg", "")
        assert not re.search(r"https?://", text), path.name


def test_fonts_are_bundled_and_served(tmp_path):
    css = (WEB / "app.css").read_text()
    names = re.findall(r"url\(['\"]?(fonts/[^'\")]+\.woff2)", css)
    assert any("newsreader" in n.lower() for n in names)
    assert any("plex" in n.lower() for n in names)
    client = TestClient(create_app(tmp_path), base_url="http://127.0.0.1")   # the host `serve` answers
    for name in names:
        assert client.get("/" + name).content[:4] == b"wOF2", name


def test_site_palette_is_present():
    css = (WEB / "app.css").read_text().replace(" ", "")
    for token in ["--ground:#0a0b0e", "--accent:#b7a6dc", "--ground:#c3b6a6", "--accent:#6e1218"]:
        assert token in css, token


def test_page_has_both_views():
    html = (WEB / "index.html").read_text()
    for needle in ['id="gallery"', 'id="studio"', 'id="home"']:
        assert needle in html, needle


def test_page_files_are_revalidated_on_every_load(tmp_path):
    # Without Cache-Control a browser guesses how long app.css and app.js stay fresh from their
    # age, and can pair a new index.html with yesterday's script: a blank page.
    client = TestClient(create_app(tmp_path), base_url="http://127.0.0.1")
    for path in ["/", "/app.css", "/app.js"]:
        assert client.get(path).headers.get("cache-control") == "no-cache", path
