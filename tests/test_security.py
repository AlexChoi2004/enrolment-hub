import pytest
from flask import Flask

from shared import security


@pytest.fixture()
def tiny_app():
    app = Flask(__name__)
    app.secret_key = "test-key"

    @app.get("/token")
    def token():
        return security.csrf_token()

    @app.post("/protected")
    def protected():
        security.require_csrf()
        return "ok"

    app.after_request(security.apply_security_headers)
    return app


def test_csrf_token_is_stable_within_a_session(tiny_app):
    client = tiny_app.test_client()
    first = client.get("/token").get_data(as_text=True)
    second = client.get("/token").get_data(as_text=True)
    assert first == second
    assert len(first) >= 32


def test_csrf_tokens_differ_between_sessions(tiny_app):
    a = tiny_app.test_client().get("/token").get_data(as_text=True)
    b = tiny_app.test_client().get("/token").get_data(as_text=True)
    assert a != b


def test_post_with_valid_form_token_is_accepted(tiny_app):
    client = tiny_app.test_client()
    token = client.get("/token").get_data(as_text=True)
    assert client.post("/protected", data={"csrf_token": token}).status_code == 200


def test_post_with_valid_header_token_is_accepted(tiny_app):
    client = tiny_app.test_client()
    token = client.get("/token").get_data(as_text=True)
    assert client.post("/protected", headers={"X-CSRF-Token": token}).status_code == 200


def test_post_without_a_token_is_rejected(tiny_app):
    client = tiny_app.test_client()
    client.get("/token")
    assert client.post("/protected").status_code == 400


def test_post_with_a_wrong_token_is_rejected(tiny_app):
    client = tiny_app.test_client()
    client.get("/token")
    assert client.post("/protected", data={"csrf_token": "nope"}).status_code == 400


def test_post_with_no_session_at_all_is_rejected(tiny_app):
    assert tiny_app.test_client().post("/protected", data={"csrf_token": "anything"}).status_code == 400


def test_non_ascii_token_is_rejected_not_a_server_error(tiny_app):
    client = tiny_app.test_client()
    client.get("/token")
    assert client.post("/protected", data={"csrf_token": "caf\u00e9"}).status_code == 400


@pytest.mark.parametrize("target", ["/subjects", "/subjects?q=web", "/students/me", "/"])
def test_safe_next_accepts_same_site_paths(target):
    assert security.is_safe_next(target)


@pytest.mark.parametrize(
    "target",
    [
        "",
        None,
        "//evil.example",
        "https://evil.example",
        "http://evil.example/path",
        "/\\evil.example",
        "javascript:alert(1)",
        "subjects",
        "/subjects\r\nSet-Cookie: x=1",
    ],
)
def test_safe_next_rejects_everything_else(target):
    assert not security.is_safe_next(target)


def test_safe_next_falls_back_to_the_default():
    assert security.safe_next("//evil.example", "/subjects") == "/subjects"
    assert security.safe_next("/students/me", "/subjects") == "/students/me"


def test_security_headers_are_applied(tiny_app):
    res = tiny_app.test_client().get("/token")
    assert "default-src 'self'" in res.headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in res.headers["Content-Security-Policy"]
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"
    assert res.headers["Referrer-Policy"] == "same-origin"