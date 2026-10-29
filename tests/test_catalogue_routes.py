import pytest

from app import create_app
from shared import db

@pytest.fixture()
def client(tmp_path):
    app = create_app({"DATABASE": str(tmp_path / "t.db"), "TESTING": True})
    return app.test_client()


def test_root_redirects_to_subjects(client):
    res = client.get("/")
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/subjects")


def test_subjects_page_lists_subjects(client):
    res = client.get("/subjects")
    assert res.status_code == 200
    assert b"Programming 1" in res.data
    assert b"<html" in res.data


def test_htmx_request_returns_fragment_only(client):
    res = client.get("/subjects?q=programming", headers={"HX-Request": "true"})
    assert res.status_code == 200
    assert b"<html" not in res.data
    assert b"Programming 1" in res.data
    assert res.headers["Vary"] == "HX-Request"


def test_category_filter_through_the_page(client):
    res = client.get("/subjects?category=honours_core")
    assert b"Honours Project B" in res.data
    assert b"Programming 1" not in res.data


def test_no_matches_shows_message(client):
    res = client.get("/subjects?q=zzzzzz")
    assert b"No subjects match these filters." in res.data


def test_invalid_filter_returns_400(client):
    assert client.get("/subjects?category=nonsense").status_code == 400
    assert client.get("/subjects?session=Winter").status_code == 400
    assert client.get("/subjects?q=" + "x" * 60).status_code == 400


def test_detail_page_shows_prerequisite(client):
    res = client.get("/subjects/41026")
    assert res.status_code == 200
    assert b"41025" in res.data
    assert b"Introduction to Software Development" in res.data


def test_subject_without_a_rule_says_no_prerequisites(client):
    res = client.get("/subjects/33130")
    assert b"No prerequisites listed in the supplied data." in res.data


def test_unknown_status_is_not_shown_as_none(tmp_path):
    path = tmp_path / "t.db"
    app = create_app({"DATABASE": str(path), "TESTING": True})
    conn = db.connect(str(path))
    conn.execute("UPDATE subjects SET prereq_status = 'unknown' WHERE code = '33130'")
    conn.commit()
    conn.close()
    res = app.test_client().get("/subjects/33130")
    assert b"not in the supplied data" in res.data
    assert b"No prerequisites listed" not in res.data


def test_malformed_subject_code_returns_400(client):
    assert client.get("/subjects/bad!code").status_code == 400


def test_missing_subject_returns_404(client):
    assert client.get("/subjects/NOPE99").status_code == 404


def test_search_text_is_html_escaped(client):
    res = client.get("/subjects?q=<script>alert(1)</script>")
    assert res.status_code == 200
    assert b"<script>alert(1)</script>" not in res.data
    assert b"&lt;script&gt;" in res.data


def test_synthetic_electives_are_labelled(client):
    res = client.get("/subjects?category=general_elective")
    assert res.data.count(b"synthetic") >= 12


def test_static_theme_is_served(client):
    assert client.get("/static/theme.css").status_code == 200


def test_prerequisite_filter_options_work_through_the_page(client):
    required = client.get("/subjects?prereqs=required")
    none = client.get("/subjects?prereqs=none")
    assert required.status_code == 200
    assert none.status_code == 200
    assert b"12 subjects" in required.data
    assert b"33 subjects" in none.data
    assert client.get("/subjects?prereqs=supplied").status_code == 400