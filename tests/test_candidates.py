import pytest

from inkfield.page.formats import Page
from inkfield.page.svg import to_svg
from inkfield.server.candidates import CandidateStore

SVG = to_svg([], Page(210, 297, 16), 0.3, {"piece": "p", "seed": 7, "params": {}, "finish": {}, "page": {}})
def test_save_list_remove(tmp_path):
    st = CandidateStore(tmp_path); a = st.save("p", 7, SVG); b = st.save("p", 7, SVG)
    assert a != b and [c["id"] for c in st.list("p")] == [a, b] and st.list("p")[0]["settings"]["seed"] == 7
    st.remove("p", a)
    assert [c["id"] for c in st.list("p")] == [b] and (tmp_path / ".trash" / "p" / f"{a}.svg").exists()
def test_list_of_unknown_slug_is_empty(tmp_path): assert CandidateStore(tmp_path).list("nothing") == []
@pytest.mark.parametrize("slug,cid", [("..", "x"), ("p", "../../etc/passwd"), ("p", ".trash"), ("p/..", "x"), ("p", "")])
def test_traversal_is_refused(tmp_path, slug, cid):                    # Review Focus 2
    st = CandidateStore(tmp_path / "c"); (tmp_path / "secret.svg").write_text("x")
    with pytest.raises(KeyError): st.path(slug, cid)
    with pytest.raises(KeyError): st.remove(slug, cid)
    assert (tmp_path / "secret.svg").exists()
