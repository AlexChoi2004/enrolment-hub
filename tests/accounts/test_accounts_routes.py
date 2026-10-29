import logging

import pytest

from accounts import service
from accounts.seed import DEMO_EMAIL, DEMO_PASSWORD
from app import create_app


def logged_in(client):
    with client.session_transaction() as s:
        return "user_id" in s


def test_login_page_renders_form_with_csrf_token(client):
    res = client.get("/login")
    assert res.status_code == 200
    assert b'name="csrf_token"' in res.data
    assert b'type="password"' in res.data
    assert b'type="email"' in res.data
    assert res.headers["Cache-Control"] == "no-store"


def test_login_page_links_to_account_creation(client):
    assert b"/register" in client.get("/login").data


def test_demo_credentials_are_shown_by_default(client):
    res = client.get("/login")
    assert DEMO_EMAIL.encode() in res.data
    assert DEMO_PASSWORD.encode() in res.data


def test_demo_credentials_can_be_hidden(tmp_path):
    app = create_app(
        {"DATABASE": str(tmp_path / "x.db"), "TESTING": True, "SECRET_KEY": "k", "SHOW_DEMO_CREDENTIALS": False}
    )
    res = app.test_client().get("/login")
    assert DEMO_PASSWORD.encode() not in res.data


def test_successful_login_goes_to_my_record_and_starts_a_session(client, log_in):
    res = log_in()
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/students/me")
    assert logged_in(client)
    page = client.get("/subjects").get_data(as_text=True)
    assert "Log out (John Doe)" in page


def test_email_is_case_insensitive(client, log_in):
    assert log_in(email="JOHN.DOE@Student.UNI.edu.au").status_code == 302


def test_wrong_password_is_rejected_with_a_generic_message(client, log_in):
    res = log_in(password="wrong-password")
    assert res.status_code == 401
    assert b"Incorrect email or password" in res.data
    assert not logged_in(client)


def test_unknown_email_gets_the_same_response_as_a_wrong_password(client, log_in):
    wrong_password = log_in(password="wrong-password")
    unknown_email = log_in(email="nobody.here@student.uni.edu.au")
    assert unknown_email.status_code == wrong_password.status_code == 401
    assert b"Incorrect email or password" in unknown_email.data
    assert b"does not exist" not in unknown_email.data


def test_missing_fields_return_400(client, csrf):
    res = client.post("/login", data={"email": "", "password": "", "csrf_token": csrf()})
    assert res.status_code == 400
    assert b"Enter your email and password" in res.data


def test_malformed_email_returns_400_with_the_format_hint(client, log_in):
    res = log_in(email="not-an-email")
    assert res.status_code == 400
    assert b"firstname.lastname@student.uni.edu.au" in res.data
    assert not logged_in(client)


def test_oversized_password_returns_400(client, log_in):
    assert log_in(password="p" * 500).status_code == 400


def test_post_without_csrf_token_is_rejected(client):
    client.get("/login")
    res = client.post("/login", data={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert res.status_code == 400
    assert not logged_in(client)


def test_post_with_wrong_csrf_token_is_rejected(client):
    client.get("/login")
    res = client.post("/login", data={"email": DEMO_EMAIL, "password": DEMO_PASSWORD, "csrf_token": "forged"})
    assert res.status_code == 400
    assert not logged_in(client)


def test_account_locks_after_five_wrong_passwords_even_for_the_right_one(client, log_in):
    for _ in range(5):
        assert log_in(password="bad").status_code == 401
    res = log_in(password=DEMO_PASSWORD)
    assert res.status_code == 401
    assert not logged_in(client)


def test_logout_clears_the_session(client, log_in, csrf):
    log_in()
    token = csrf("/subjects")
    res = client.post("/logout", data={"csrf_token": token})
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/login")
    assert not logged_in(client)


def test_logout_requires_post_and_a_csrf_token(client, log_in):
    log_in()
    assert client.get("/logout").status_code == 405
    assert client.post("/logout").status_code == 400
    assert logged_in(client)


def test_csrf_token_changes_after_login(client, csrf, log_in):
    before = csrf()
    log_in()
    after = csrf("/subjects")
    assert before != after


@pytest.mark.parametrize("evil", ["//evil.example", "https://evil.example/", "/\\evil.example", "javascript:alert(1)"])
def test_login_never_redirects_off_site(client, log_in, evil):
    res = log_in(next=evil)
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/students/me")
    assert "evil" not in res.headers["Location"]


def test_login_honours_a_safe_next_path(client, log_in):
    res = log_in(next="/subjects?q=web")
    assert res.headers["Location"].endswith("/subjects?q=web")


def test_login_page_does_not_echo_an_unsafe_next_value(client):
    res = client.get("/login?next=//evil.example")
    assert b"evil.example" not in res.data


def test_session_cookie_is_httponly_and_samesite(client, log_in):
    res = log_in()
    cookie = res.headers.get("Set-Cookie", "")
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie


def test_passwords_and_emails_are_never_written_to_the_log(client, log_in, caplog):
    caplog.set_level(logging.DEBUG)
    log_in(password="SuperSecret!123")
    log_in()
    assert "SuperSecret!123" not in caplog.text
    assert DEMO_PASSWORD not in caplog.text
    assert DEMO_EMAIL not in caplog.text
    assert f"Failed login for account {service.email_fingerprint(DEMO_EMAIL)}" in caplog.text


def test_pages_carry_security_headers(client):
    res = client.get("/login")
    assert "default-src 'self'" in res.headers["Content-Security-Policy"]
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"


def test_stale_session_for_a_missing_user_is_treated_as_logged_out(client):
    with client.session_transaction() as s:
        s["user_id"] = 9999
    page = client.get("/login").get_data(as_text=True)
    assert "Log in" in page
    assert "Log out" not in page


def test_nav_offers_login_and_create_account_to_visitors(client):
    page = client.get("/login").get_data(as_text=True)
    assert "Log in" in page and "Create account" in page
    assert 'href="/subjects"' not in page


def test_secret_key_is_random_when_not_configured(monkeypatch, tmp_path):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    a = create_app({"DATABASE": str(tmp_path / "a.db")})
    b = create_app({"DATABASE": str(tmp_path / "b.db")})
    assert a.config["SECRET_KEY"] != b.config["SECRET_KEY"]
    assert len(a.config["SECRET_KEY"]) >= 32
    assert a.config["SECRET_KEY"] != "dev-only-change-me"


def test_secret_key_can_be_set_from_the_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("SECRET_KEY", "x" * 40)
    app = create_app({"DATABASE": str(tmp_path / "a.db")})
    assert app.config["SECRET_KEY"] == "x" * 40