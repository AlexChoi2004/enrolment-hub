import logging
import re

import pytest

from accounts.seed import DEMO_EMAIL
from app import create_app
from shared import db

JANE = "jane.smith@student.uni.edu.au"
PASSWORD = "Str0ng#Pass"


def user_count(app):
    conn = db.connect(app.config["DATABASE"])
    try:
        return conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
    finally:
        conn.close()


def logged_in(client):
    with client.session_transaction() as s:
        return "user_id" in s


def test_register_page_explains_the_rules_and_the_made_up_name_note(client):
    res = client.get("/register")
    assert res.status_code == 200
    assert b"made-up name" in res.data
    assert b"firstname.lastname@student.uni.edu.au" in res.data
    assert b"at least 8 characters" in res.data
    assert b'name="confirm_password"' in res.data
    assert b"Year 1" in res.data


def test_successful_registration_logs_the_student_in_and_goes_to_their_record(app, client, register):
    res = register()
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/students/me")
    assert logged_in(client)
    assert user_count(app) == 2  # the demo student and the new one


def test_new_student_starts_in_year_1_with_nothing_enrolled(client, register):
    register()
    page = client.get("/students/me", follow_redirects=True).get_data(as_text=True)
    assert "Jane Smith" in page
    assert "Year 1" in page
    assert "Autumn 2027" in page
    assert "(your first session)" in page
    assert "0 of 192 credit points counted" in page
    assert "No subjects in progress." in page
    assert "No completed subjects." in page
    assert "Welcome" in page


def test_demo_student_is_shown_in_year_3_with_a_history(client, log_in):
    log_in()
    page = client.get("/students/me", follow_redirects=True).get_data(as_text=True)
    assert "John Doe" in page
    assert "Year 3" in page
    assert "120 of 192 credit points counted" in page
    assert "Welcome" not in page


def test_record_url_uses_a_generated_student_number_not_the_email(client, register):
    res = register()
    me = client.get(res.headers["Location"])
    assert re.search(r"/students/S\d{7}/record$", me.headers["Location"])
    page = client.get(me.headers["Location"]).get_data(as_text=True)
    assert JANE not in page


def test_new_student_cannot_view_the_demo_students_record(client, register):
    register()
    assert client.get("/students/DEMO0001/record").status_code == 403


def test_new_account_can_log_out_and_back_in(client, register, log_in, csrf):
    register()
    client.post("/logout", data={"csrf_token": csrf("/subjects")})
    assert not logged_in(client)
    assert log_in(email=JANE, password=PASSWORD).status_code == 302
    assert logged_in(client)


def test_email_is_normalised_when_registering(app, client, register):
    assert register(email=" Jane.Smith@Student.UNI.edu.au ").status_code == 302
    conn = db.connect(app.config["DATABASE"])
    stored = conn.execute("SELECT email FROM users WHERE display_name = 'Jane Smith'").fetchone()
    conn.close()
    assert stored["email"] == JANE


# --- validation errors -------------------------------------------------------

@pytest.mark.parametrize(
    ("password", "message"),
    [
        ("Sh0rt#", "at least 8 characters"),
        ("alllowercase1#", "uppercase letter"),
        ("ALLUPPERCASE1#", "lowercase letter"),
        ("NoNumbers#here", "include a number"),
        ("NoSpecial123abc", "special character"),
    ],
)
def test_each_password_rule_shows_its_own_error(app, client, register, password, message):
    res = register(password=password)
    assert res.status_code == 400
    assert message.encode() in res.data
    assert user_count(app) == 1
    assert not logged_in(client)


def test_bad_email_shows_the_format_message(app, register):
    res = register(email="jane@gmail.com")
    assert res.status_code == 400
    assert b"firstname.lastname@student.uni.edu.au" in res.data
    assert user_count(app) == 1


def test_mismatched_passwords_show_an_error(register):
    res = register(confirm="Different#1")
    assert res.status_code == 400
    assert b"Passwords do not match." in res.data


def test_all_problems_are_listed_together(register):
    res = register(email="bad", password="weak", confirm="other")
    assert res.status_code == 400
    for fragment in [b"firstname.lastname", b"at least 8 characters", b"uppercase", b"number", b"special", b"do not match"]:
        assert fragment in res.data


def test_the_form_keeps_the_email_but_never_echoes_the_password(register):
    res = register(password="weak")
    assert JANE.encode() in res.data
    assert not re.search(rb'type="password"[^>]*value=', res.data)
    assert b'value="weak"' not in res.data


def test_html_in_the_email_field_is_escaped(register):
    res = register(email='"><script>alert(1)</script>@student.uni.edu.au')
    assert res.status_code == 400
    assert b"<script>alert(1)</script>" not in res.data


# --- duplicates, limits, CSRF, logging --------------------------------------

def test_duplicate_email_is_refused(app, register):
    assert register().status_code == 302
    res = register()  # same email again
    assert res.status_code == 409
    assert b"already exists" in res.data
    assert user_count(app) == 2


def test_duplicate_check_is_case_insensitive_and_covers_the_demo_account(app, register):
    res = register(email=DEMO_EMAIL.upper())
    assert res.status_code == 409
    assert user_count(app) == 1


def test_registration_closes_when_the_account_limit_is_reached(tmp_path):
    app = create_app(
        {"DATABASE": str(tmp_path / "x.db"), "TESTING": True, "SECRET_KEY": "k", "MAX_ACCOUNTS": 1}
    )
    client = app.test_client()
    token = re.search(r'name="csrf_token" value="([^"]+)"', client.get("/register").get_data(as_text=True)).group(1)
    res = client.post(
        "/register",
        data={"email": JANE, "password": PASSWORD, "confirm_password": PASSWORD, "csrf_token": token},
    )
    assert res.status_code == 403
    assert b"limit of accounts" in res.data
    assert user_count(app) == 1


def test_registration_without_a_csrf_token_is_rejected(app, client):
    client.get("/register")
    res = client.post("/register", data={"email": JANE, "password": PASSWORD, "confirm_password": PASSWORD})
    assert res.status_code == 400
    assert user_count(app) == 1


def test_registration_with_a_forged_csrf_token_is_rejected(app, client):
    client.get("/register")
    res = client.post(
        "/register",
        data={"email": JANE, "password": PASSWORD, "confirm_password": PASSWORD, "csrf_token": "forged"},
    )
    assert res.status_code == 400
    assert user_count(app) == 1


def test_registration_never_writes_the_password_or_email_to_the_log(register, caplog):
    caplog.set_level(logging.DEBUG)
    register(password="Weak")
    register()
    assert PASSWORD not in caplog.text
    assert "Weak" not in caplog.text
    assert JANE not in caplog.text


def test_new_accounts_store_a_hash_not_the_password(app, register):
    register()
    conn = db.connect(app.config["DATABASE"])
    stored = conn.execute("SELECT password_hash FROM users WHERE email = ?", (JANE,)).fetchone()
    conn.close()
    assert PASSWORD not in stored["password_hash"]
    assert ":" in stored["password_hash"]