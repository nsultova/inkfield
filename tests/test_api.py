import pytest
from fastapi.testclient import TestClient

from inkfield.core.piece import Meta, Piece, discover
from inkfield.server.app import create_app


def boom(params, frame, rng): raise ValueError("kaput")
@pytest.fixture
def client(tmp_path):
    pieces = dict(discover()); pieces["boom"] = Piece(Meta("boom", "Boom", "", "rect", ""), [], boom)
    return TestClient(create_app(tmp_path, pieces))

def test_index_and_pieces(client):
    assert client.get("/").status_code == 200
    d = client.get("/api/pieces").json()
    cw = next(p for p in d["pieces"] if p["slug"] == "chemical-waves")
    assert [c["name"] for c in cw["params"]] == ["sources", "spirals", "wavelength", "elapsed", "stagger", "uneven"]
    assert [c["name"] for c in d["finish"]["params"]] == ["wobble", "border"] and d["page"]["params"][0]["name"] == "composition"

def test_render(client):
    r = client.post("/api/render", json={"piece": "chemical-waves", "seed": 7}).json()
    assert r["svg"].startswith("<svg") and r["stats"]["strokes"] > 5 and r["page"] == {"width": 210, "height": 297, "margin": 16}
    assert r["settings"]["params"]["sources"] == 9

def test_errors(client):
    assert client.post("/api/render", json={"piece": "nope"}).status_code == 404
    r = client.post("/api/render", json={"piece": "boom"})            # Review Focus 4
    assert r.status_code == 422 and r.json()["error"] == "ValueError: kaput"

def test_candidate_lifecycle(client):
    c = client.post("/api/candidates", json={"piece": "chemical-waves", "seed": 5, "params": {"sources": 3}}).json()
    assert c["seed"] == 5 and c["settings"]["params"]["sources"] == 3
    assert [x["id"] for x in client.get("/api/candidates/chemical-waves").json()] == [c["id"]]
    svg = client.get(c["url"]); assert svg.status_code == 200 and svg.headers["content-type"].startswith("image/svg+xml")
    assert client.delete(f"/api/candidates/chemical-waves/{c['id']}").status_code == 204
    assert client.get("/api/candidates/chemical-waves").json() == [] and client.get(c["url"]).status_code == 404
    assert client.delete("/api/candidates/chemical-waves/..%2F..%2Fx").status_code == 404
