import pytest
from fastapi.testclient import TestClient

from inkfield.core.piece import Meta, Piece, discover
from inkfield.server.app import create_app
from inkfield.server.candidates import CandidateStore


def boom(params, frame, rng): raise ValueError("kaput")
@pytest.fixture
def client(tmp_path):
    pieces = dict(discover()); pieces["boom"] = Piece(Meta("boom", "Boom", "", "rect", ""), [], boom)
    return TestClient(create_app(tmp_path, pieces), base_url="http://127.0.0.1")   # the host `serve` answers

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

def keep(client): return client.post("/api/candidates", json={"piece": "chemical-waves", "seed": 5, "params": {"sources": 2}}).json()

def test_candidate_svg_cannot_run_scripts(client):
    h = client.get(keep(client)["url"]).headers
    assert h["x-content-type-options"] == "nosniff"
    assert h["content-security-policy"] == "default-src 'none'; style-src 'unsafe-inline'"

def test_delete_race_is_404_and_other_disk_errors_are_json(client, monkeypatch):
    cid = keep(client)["id"]
    def gone(self, slug, cid): raise FileNotFoundError(cid)
    monkeypatch.setattr(CandidateStore, "remove", gone)
    r = client.delete(f"/api/candidates/chemical-waves/{cid}"); assert r.status_code == 404 and r.json() == {"error": "no such candidate"}
    def stuck(self, slug, cid): raise PermissionError(13, "Permission denied")
    monkeypatch.setattr(CandidateStore, "remove", stuck)
    r = client.delete(f"/api/candidates/chemical-waves/{cid}"); assert r.status_code == 500 and "Permission denied" in r.json()["error"]

@pytest.mark.parametrize("host", ["127.0.0.1", "127.0.0.1:8765", "localhost", "localhost:8000"])
def test_local_hosts_are_answered(tmp_path, host):
    assert TestClient(create_app(tmp_path)).get("/api/pieces", headers={"host": host}).status_code == 200

@pytest.mark.parametrize("host", ["evil.example", "evil.example:8765", "testserver", "127.0.0.1.evil.example", "localhost.evil.example:8000"])
def test_other_hosts_are_refused(tmp_path, host):                   # DNS rebinding
    for path in ("/", "/api/pieces"):
        r = TestClient(create_app(tmp_path)).get(path, headers={"host": host})
        assert r.status_code == 403 and "error" in r.json()
