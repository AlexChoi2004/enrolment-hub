import os

from app import create_app


def test_health_endpoint(tmp_path):
    app = create_app({"DATABASE": str(tmp_path / "t.db"), "TESTING": True})
    res = app.test_client().get("/health")
    assert res.status_code == 200
    assert res.get_json() == {"status": "ok"}


def test_app_creates_and_seeds_database_when_missing(tmp_path):
    path = tmp_path / "fresh.db"
    assert not os.path.exists(path)
    create_app({"DATABASE": str(path), "TESTING": True})
    assert os.path.exists(path)


def test_home_page_shows_a_welcome_screen_to_visitors(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"Welcome to Enrolment Hub" in res.data
    assert b"Log in" in res.data and b"Create account" in res.data
    assert b"john.doe@student.uni.edu.au" in res.data  # demo login is offered
    assert b'href="/subjects"' not in res.data  # no Subjects link until you log in


def test_home_page_sends_logged_in_students_to_their_record(client, log_in):
    log_in()
    res = client.get("/")
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/students/me")


def test_subject_catalogue_requires_a_login(client):
    res = client.get("/subjects")
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]
    assert "next=/subjects" in res.headers["Location"]
    assert client.get("/subjects/41026").status_code == 302


def test_catalogue_htmx_request_without_a_login_gets_401(client):
    res = client.get("/subjects?q=web", headers={"HX-Request": "true"})
    assert res.status_code == 401
    assert res.headers["HX-Redirect"].endswith("/login")


def test_nav_shows_subjects_only_when_logged_in(client, log_in):
    assert b'href="/subjects"' not in client.get("/login").data
    log_in()
    assert b'href="/subjects"' in client.get("/students/me", follow_redirects=True).data


def test_static_files_stay_public(client):
    assert client.get("/static/theme.css").status_code == 200