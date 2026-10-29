import pytest

from accounts import service
from accounts.seed import DEMO_PASSWORD, DEMO_STUDENT_NUMBER
from accounts.service import ValidationError


def test_demo_password_is_stored_as_a_salted_hash_not_plaintext(conn):
    row = conn.execute(
        "SELECT password_hash FROM users WHERE student_number = ?", (DEMO_STUDENT_NUMBER,)
    ).fetchone()
    assert row["password_hash"] != DEMO_PASSWORD
    assert DEMO_PASSWORD not in row["password_hash"]
    assert ":" in row["password_hash"] and "$" in row["password_hash"]  # method:params$salt$hash


def test_password_appears_nowhere_in_the_users_table(conn):
    for row in conn.execute("SELECT * FROM users"):
        assert all(DEMO_PASSWORD not in str(value) for value in tuple(row))


def test_same_password_hashes_differently_each_time():
    assert service.hash_password("a-password") != service.hash_password("a-password")


def test_authenticate_succeeds_with_correct_password(conn):
    user = service.authenticate(conn, DEMO_STUDENT_NUMBER, DEMO_PASSWORD)
    assert user["student_number"] == DEMO_STUDENT_NUMBER
    assert "password_hash" not in user


def test_authenticate_rejects_wrong_password(conn):
    assert service.authenticate(conn, DEMO_STUDENT_NUMBER, "wrong-password") is None


def test_authenticate_rejects_unknown_student(conn):
    assert service.authenticate(conn, "NOBODY99", DEMO_PASSWORD) is None


def test_account_locks_after_repeated_failures_even_with_correct_password(conn):
    for _ in range(service.MAX_FAILED_LOGINS):
        assert service.authenticate(conn, DEMO_STUDENT_NUMBER, "bad", now=1000) is None
    assert service.authenticate(conn, DEMO_STUDENT_NUMBER, DEMO_PASSWORD, now=1001) is None


def test_lockout_expires(conn):
    for _ in range(service.MAX_FAILED_LOGINS):
        service.authenticate(conn, DEMO_STUDENT_NUMBER, "bad", now=1000)
    after = 1000 + service.LOCKOUT_SECONDS + 1
    assert service.authenticate(conn, DEMO_STUDENT_NUMBER, DEMO_PASSWORD, now=after) is not None


def test_successful_login_resets_the_failure_count(conn):
    for _ in range(service.MAX_FAILED_LOGINS - 1):
        service.authenticate(conn, DEMO_STUDENT_NUMBER, "bad", now=1000)
    assert service.authenticate(conn, DEMO_STUDENT_NUMBER, DEMO_PASSWORD, now=1001) is not None
    for _ in range(service.MAX_FAILED_LOGINS - 1):
        service.authenticate(conn, DEMO_STUDENT_NUMBER, "bad", now=1002)
    assert service.authenticate(conn, DEMO_STUDENT_NUMBER, DEMO_PASSWORD, now=1003) is not None


def test_get_user_returns_no_password_hash(conn):
    user = service.get_user(conn, 1)
    assert user["student_number"] == DEMO_STUDENT_NUMBER
    assert "password_hash" not in user
    assert service.get_user(conn, 9999) is None


def test_validate_login_normalises_the_student_number():
    assert service.validate_login({"student_number": " demo0001 ", "password": "x"}) == ("DEMO0001", "x")


@pytest.mark.parametrize(
    "form",
    [
        {},
        {"student_number": "", "password": "x"},
        {"student_number": "DEMO0001", "password": ""},
        {"student_number": "   ", "password": "x"},
        {"student_number": "DEMO0001"},
        {"password": "x"},
    ],
)
def test_validate_login_rejects_missing_fields(form):
    with pytest.raises(ValidationError):
        service.validate_login(form)


@pytest.mark.parametrize(
    "form",
    [
        {"student_number": "abc", "password": "x"},  # too short
        {"student_number": "A" * 21, "password": "x"},  # too long
        {"student_number": "DEMO 0001", "password": "x"},  # space
        {"student_number": "DEMO0001'; --", "password": "x"},  # punctuation
        {"student_number": "DEMO0001", "password": "p" * 129},  # oversized password
    ],
)
def test_validate_login_rejects_malformed_values(form):
    with pytest.raises(ValidationError):
        service.validate_login(form)