"""Accounts business logic: password hashing, login checks and lockout.

No Flask objects in here so the rules can be unit tested directly.
Passwords are never logged or returned; only salted hashes are stored.
"""
import re
import time

from werkzeug.security import check_password_hash, generate_password_hash

MAX_FAILED_LOGINS = 5
LOCKOUT_SECONDS = 300
MAX_PASSWORD_LENGTH = 128
STUDENT_NUMBER_PATTERN = re.compile(r"^[A-Za-z0-9]{4,20}$")

_dummy_hash = None


class ValidationError(ValueError):
    """Submitted form data was missing or malformed."""


def hash_password(password):
    return generate_password_hash(password)


def verify_password(password_hash, password):
    return check_password_hash(password_hash, password)


def validate_login(form):
    """Return (student_number, password) or raise ValidationError."""
    student_number = (form.get("student_number") or "").strip()
    password = form.get("password") or ""
    if not student_number or not password:
        raise ValidationError("Enter your student number and password.")
    if not STUDENT_NUMBER_PATTERN.match(student_number) or len(password) > MAX_PASSWORD_LENGTH:
        raise ValidationError("Student number or password is not in a valid format.")
    return student_number.upper(), password


def _waste_time_like_a_real_check(password):
    """Hash against a dummy value so unknown users take as long as real ones."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = generate_password_hash("not-a-real-password")
    check_password_hash(_dummy_hash, password)


def get_user(conn, user_id):
    row = conn.execute(
        "SELECT id, student_number, display_name, course_code FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    return dict(row) if row else None


def authenticate(conn, student_number, password, now=None):
    """Return the user (as a dict) if the login is valid, otherwise None.

    Every failure looks the same to the caller so the response never reveals
    whether an account exists or is locked.
    """
    now = int(time.time() if now is None else now)
    user = conn.execute(
        "SELECT * FROM users WHERE student_number = ?", (student_number,)
    ).fetchone()

    if user is None:
        _waste_time_like_a_real_check(password)
        return None

    if user["locked_until"] > now:
        _waste_time_like_a_real_check(password)
        return None

    if verify_password(user["password_hash"], password):
        conn.execute(
            "UPDATE users SET failed_logins = 0, locked_until = 0 WHERE id = ?", (user["id"],)
        )
        conn.commit()
        return {
            "id": user["id"],
            "student_number": user["student_number"],
            "display_name": user["display_name"],
            "course_code": user["course_code"],
        }

    failed = user["failed_logins"] + 1
    locked_until = 0
    if failed >= MAX_FAILED_LOGINS:
        locked_until = now + LOCKOUT_SECONDS
        failed = 0
    conn.execute(
        "UPDATE users SET failed_logins = ?, locked_until = ? WHERE id = ?",
        (failed, locked_until, user["id"]),
    )
    conn.commit()
    return None