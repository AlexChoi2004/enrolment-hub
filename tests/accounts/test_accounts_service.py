import re

import pytest

from accounts import service
from accounts.seed import DEMO_EMAIL, DEMO_PASSWORD
from accounts.service import DuplicateEmailError, ValidationError


# --- password storage --------------------------------------------------------

def test_demo_password_is_stored_as_a_salted_hash_not_plaintext(conn):
    row = conn.execute("SELECT password_hash FROM users WHERE email = ?", (DEMO_EMAIL,)).fetchone()
    assert row["password_hash"] != DEMO_PASSWORD
    assert DEMO_PASSWORD not in row["password_hash"]
    assert ":" in row["password_hash"] and "$" in row["password_hash"]  # method:params$salt$hash


def test_password_appears_nowhere_in_the_users_table(conn):
    for row in conn.execute("SELECT * FROM users"):
        assert all(DEMO_PASSWORD not in str(value) for value in tuple(row))


def test_same_password_hashes_differently_each_time():
    assert service.hash_password("a-password") != service.hash_password("a-password")


# --- authenticate and lockout ------------------------------------------------

def test_authenticate_succeeds_with_correct_password(conn):
    user = service.authenticate(conn, DEMO_EMAIL, DEMO_PASSWORD)
    assert user["student_number"] == "DEMO0001"
    assert user["commencement_session"] == "Autumn 2025"
    assert "password_hash" not in user


def test_authenticate_rejects_wrong_password(conn):
    assert service.authenticate(conn, DEMO_EMAIL, "wrong-password") is None


def test_authenticate_rejects_unknown_email(conn):
    assert service.authenticate(conn, "nobody.here@student.uni.edu.au", DEMO_PASSWORD) is None


def test_account_locks_after_repeated_failures_even_with_correct_password(conn):
    for _ in range(service.MAX_FAILED_LOGINS):
        assert service.authenticate(conn, DEMO_EMAIL, "bad", now=1000) is None
    assert service.authenticate(conn, DEMO_EMAIL, DEMO_PASSWORD, now=1001) is None


def test_lockout_expires(conn):
    for _ in range(service.MAX_FAILED_LOGINS):
        service.authenticate(conn, DEMO_EMAIL, "bad", now=1000)
    after = 1000 + service.LOCKOUT_SECONDS + 1
    assert service.authenticate(conn, DEMO_EMAIL, DEMO_PASSWORD, now=after) is not None


def test_successful_login_resets_the_failure_count(conn):
    for _ in range(service.MAX_FAILED_LOGINS - 1):
        service.authenticate(conn, DEMO_EMAIL, "bad", now=1000)
    assert service.authenticate(conn, DEMO_EMAIL, DEMO_PASSWORD, now=1001) is not None
    for _ in range(service.MAX_FAILED_LOGINS - 1):
        service.authenticate(conn, DEMO_EMAIL, "bad", now=1002)
    assert service.authenticate(conn, DEMO_EMAIL, DEMO_PASSWORD, now=1003) is not None


def test_get_user_returns_no_password_hash(conn):
    user = service.get_user(conn, 1)
    assert user["display_name"] == "John Doe"
    assert "password_hash" not in user
    assert service.get_user(conn, 9999) is None


# --- email rules -------------------------------------------------------------

@pytest.mark.parametrize(
    "email",
    [
        "john.doe@student.uni.edu.au",
        "mary-jane.smith-jones@student.uni.edu.au",
        "a.b@student.uni.edu.au",
    ],
)
def test_valid_emails_are_accepted(email):
    assert service.is_valid_email(email)


@pytest.mark.parametrize(
    "email",
    [
        "johndoe@student.uni.edu.au",  # no dot between names
        "john.doe.smith@student.uni.edu.au",  # two dots
        "john..doe@student.uni.edu.au",
        ".john@student.uni.edu.au",
        "john.@student.uni.edu.au",
        "john.doe@gmail.com",  # wrong domain
        "john.doe@student.uni.edu.au.evil.com",  # domain only at the start
        "john.doe@evil.student.uni.edu.au",
        "john1.doe@student.uni.edu.au",  # digits
        "john.doe+tag@student.uni.edu.au",
        "john doe@student.uni.edu.au",
        "john.doe@student.uni.edu.au\n",  # trailing newline
        "-john.doe@student.uni.edu.au",
        "jöhn.doe@student.uni.edu.au",  # non-ASCII letters
        "",
        "a" * 100 + ".doe@student.uni.edu.au",  # too long
    ],
)
def test_invalid_emails_are_rejected(email):
    assert not service.is_valid_email(email)


def test_email_is_normalised_to_lower_case_without_spaces():
    assert service.normalise_email("  John.Doe@Student.UNI.edu.au ") == "john.doe@student.uni.edu.au"
    assert service.normalise_email(None) == ""


def test_display_name_comes_from_the_email():
    assert service.display_name_from_email("jane.smith@student.uni.edu.au") == "Jane Smith"
    assert service.display_name_from_email("mary-jane.smith-jones@student.uni.edu.au") == "Mary-Jane Smith-Jones"


def test_email_fingerprint_is_short_stable_and_hides_the_email():
    tag = service.email_fingerprint("john.doe@student.uni.edu.au")
    assert tag == service.email_fingerprint("john.doe@student.uni.edu.au")
    assert len(tag) == 12
    assert "john" not in tag


# --- password rules ----------------------------------------------------------

def test_demo_password_meets_the_rules():
    assert service.password_problems(DEMO_PASSWORD) == []


@pytest.mark.parametrize(
    ("password", "expected"),
    [
        ("Sh0rt#", "at least 8 characters"),
        ("alllowercase1#", "uppercase letter"),
        ("ALLUPPERCASE1#", "lowercase letter"),
        ("NoNumbers#here", "a number"),
        ("NoSpecial123abc", "special character"),
        ("Aa1#" + "x" * 130, "128 characters or fewer"),
    ],
)
def test_each_password_rule_gives_its_own_message(password, expected):
    problems = service.password_problems(password)
    assert len(problems) == 1
    assert expected in problems[0]


def test_a_very_weak_password_lists_every_problem():
    assert len(service.password_problems("a")) == 4  # length, uppercase, number, special


def test_exactly_eight_characters_is_enough():
    assert service.password_problems("Abcdef1#") == []


# --- form validation ---------------------------------------------------------

def test_valid_registration_has_no_errors_and_a_normalised_email():
    email, errors = service.validate_registration(
        {"email": " Jane.Smith@Student.uni.edu.au ", "password": "Str0ng#Pass", "confirm_password": "Str0ng#Pass"}
    )
    assert errors == []
    assert email == "jane.smith@student.uni.edu.au"


def test_registration_reports_every_problem_at_once():
    _, errors = service.validate_registration({"email": "bad", "password": "weak", "confirm_password": "other"})
    assert service.EMAIL_FORMAT_MESSAGE in errors
    assert "Passwords do not match." in errors
    assert len(errors) >= 5


def test_registration_requires_all_fields():
    _, errors = service.validate_registration({})
    assert "Enter your email address." in errors
    assert "Enter a password." in errors


def test_registration_rejects_mismatched_confirmation():
    _, errors = service.validate_registration(
        {"email": "jane.smith@student.uni.edu.au", "password": "Str0ng#Pass", "confirm_password": "Str0ng#Pasx"}
    )
    assert errors == ["Passwords do not match."]


def test_registration_rejects_a_blank_confirmation():
    _, errors = service.validate_registration(
        {"email": "jane.smith@student.uni.edu.au", "password": "Str0ng#Pass", "confirm_password": ""}
    )
    assert errors == ["Passwords do not match."]


def test_validate_login_normalises_the_email():
    assert service.validate_login({"email": " JOHN.DOE@student.uni.edu.au ", "password": "x"}) == (DEMO_EMAIL, "x")


@pytest.mark.parametrize(
    "form",
    [
        {},
        {"email": "", "password": "x"},
        {"email": DEMO_EMAIL, "password": ""},
        {"email": "   ", "password": "x"},
        {"email": DEMO_EMAIL},
        {"password": "x"},
    ],
)
def test_validate_login_rejects_missing_fields(form):
    with pytest.raises(ValidationError):
        service.validate_login(form)


@pytest.mark.parametrize(
    "form",
    [
        {"email": "not-an-email", "password": "x"},
        {"email": "john.doe@gmail.com", "password": "x"},
        {"email": "john.doe'; --@student.uni.edu.au", "password": "x"},
        {"email": DEMO_EMAIL, "password": "p" * 129},
    ],
)
def test_validate_login_rejects_malformed_values(form):
    with pytest.raises(ValidationError):
        service.validate_login(form)


# --- creating accounts -------------------------------------------------------

def test_create_user_stores_a_hash_and_generates_a_student_number(conn):
    user = service.create_user(conn, "jane.smith@student.uni.edu.au", "Str0ng#Pass", "Autumn 2027")
    assert re.fullmatch(r"S\d{7}", user["student_number"])
    assert user["display_name"] == "Jane Smith"
    assert user["commencement_session"] == "Autumn 2027"
    stored = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user["id"],)).fetchone()
    assert stored["password_hash"] != "Str0ng#Pass"
    assert service.authenticate(conn, "jane.smith@student.uni.edu.au", "Str0ng#Pass") is not None


def test_duplicate_email_is_refused(conn):
    service.create_user(conn, "jane.smith@student.uni.edu.au", "Str0ng#Pass", "Autumn 2027")
    with pytest.raises(DuplicateEmailError):
        service.create_user(conn, "jane.smith@student.uni.edu.au", "Other#Pass1", "Autumn 2027")
    with pytest.raises(DuplicateEmailError):
        service.create_user(conn, DEMO_EMAIL, "Other#Pass1", "Autumn 2027")


def test_student_numbers_are_unique(conn):
    numbers = {
        service.create_user(conn, f"person.{name}@student.uni.edu.au", "Str0ng#Pass", "Autumn 2027")["student_number"]
        for name in ["one", "two", "three", "four", "five"]
    }
    assert len(numbers) == 5


def test_account_count(conn):
    assert service.account_count(conn) == 1
    service.create_user(conn, "jane.smith@student.uni.edu.au", "Str0ng#Pass", "Autumn 2027")
    assert service.account_count(conn) == 2