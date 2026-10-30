"""Accounts business logic: registration rules, password hashing, login checks and lockout.

No Flask objects in here so the rules can be unit tested directly.
Passwords are never logged or returned; only salted hashes are stored.
"""
import hashlib
import re
import secrets
import sqlite3
import string
import time

from werkzeug.security import check_password_hash, generate_password_hash

MAX_FAILED_LOGINS = 5
LOCKOUT_SECONDS = 300
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
MAX_EMAIL_LENGTH = 100

NAME_PART = r"[a-z]+(?:-[a-z]+)*"
EMAIL_PATTERN = re.compile(rf"{NAME_PART}\.{NAME_PART}@student\.uni\.edu\.au")
STUDENT_NUMBER_PATTERN = re.compile(r"[A-Za-z0-9]{4,20}")  # always use .fullmatch()

EMAIL_FORMAT_MESSAGE = (
    "Use the format firstname.lastname@student.uni.edu.au "
    "(letters only, with one dot between first and last name)."
)

_dummy_hash = None


class ValidationError(ValueError):
    """Submitted form data was missing or malformed."""


class DuplicateEmailError(Exception):
    """An account with this email already exists."""


def hash_password(password):
    return generate_password_hash(password)


def verify_password(password_hash, password):
    return check_password_hash(password_hash, password)


def normalise_email(raw):
    return (raw or "").strip().lower()


def is_valid_email(email):
    return len(email) <= MAX_EMAIL_LENGTH and bool(EMAIL_PATTERN.fullmatch(email))


def email_fingerprint(email):
    """Short one-way tag so logs can correlate attempts without storing the email itself."""
    return hashlib.sha256(email.encode()).hexdigest()[:12]


def password_problems(password):
    """Every password rule the password breaks, as user-facing messages."""
    problems = []
    if len(password) < MIN_PASSWORD_LENGTH:
        problems.append(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if len(password) > MAX_PASSWORD_LENGTH:
        problems.append(f"Password must be {MAX_PASSWORD_LENGTH} characters or fewer.")
    if not re.search(r"[A-Z]", password):
        problems.append("Password must include an uppercase letter.")
    if not re.search(r"[a-z]", password):
        problems.append("Password must include a lowercase letter.")
    if not re.search(r"[0-9]", password):
        problems.append("Password must include a number.")
    if not any(ch in string.punctuation for ch in password):
        problems.append("Password must include a special character (for example # ! @ $).")
    return problems


def validate_registration(form):
    """Return (email, errors). An empty errors list means the form is valid."""
    errors = []
    email = normalise_email(form.get("email"))
    password = form.get("password") or ""
    confirm = form.get("confirm_password") or ""

    if not email:
        errors.append("Enter your email address.")
    elif not is_valid_email(email):
        errors.append(EMAIL_FORMAT_MESSAGE)

    if not password:
        errors.append("Enter a password.")
    else:
        errors.extend(password_problems(password))
        if confirm != password:
            errors.append("Passwords do not match.")
    return email, errors


def validate_login(form):
    """Return (email, password) or raise ValidationError."""
    email = normalise_email(form.get("email"))
    password = form.get("password") or ""
    if not email or not password:
        raise ValidationError("Enter your email and password.")
    if not is_valid_email(email):
        raise ValidationError(EMAIL_FORMAT_MESSAGE)
    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValidationError("Email or password is not in a valid format.")
    return email, password


def display_name_from_email(email):
    local = email.split("@")[0]
    parts = local.split(".")
    return " ".join("-".join(piece.capitalize() for piece in part.split("-")) for part in parts)


def generate_student_number():
    return "S" + f"{secrets.randbelow(10_000_000):07d}"


def account_count(conn):
    return conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]


def get_user(conn, user_id):
    row = conn.execute(
        "SELECT id, student_number, display_name, course_code, commencement_session"
        " FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    return dict(row) if row else None


def get_profile(conn, user_id):
    """The details shown on the student's own profile page (never includes the password hash)."""
    row = conn.execute(
        "SELECT email, student_number, display_name, course_code, commencement_session"
        " FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    return dict(row) if row else None


def create_user(conn, email, password, commencement_session, course_code="C09119"):
    """Create an account and return it (without any password data).

    Raises DuplicateEmailError if the email is taken.
    """
    password_hash = hash_password(password)
    for _ in range(10):  # student numbers are random, so retry on the rare collision
        try:
            cur = conn.execute(
                "INSERT INTO users (email, student_number, display_name, password_hash,"
                " course_code, commencement_session) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    email,
                    generate_student_number(),
                    display_name_from_email(email),
                    password_hash,
                    course_code,
                    commencement_session,
                ),
            )
            conn.commit()
            return get_user(conn, cur.lastrowid)
        except sqlite3.IntegrityError as exc:
            conn.rollback()
            if "users.email" in str(exc):
                raise DuplicateEmailError(email) from exc
    raise RuntimeError("Could not allocate a student number.")


def _waste_time_like_a_real_check(password):
    """Hash against a dummy value so unknown users take as long as real ones."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = generate_password_hash("not-a-real-password")
    check_password_hash(_dummy_hash, password)


def authenticate(conn, email, password, now=None):
    """Return the user (as a dict) if the login is valid, otherwise None.

    Every failure looks the same to the caller so the response never reveals
    whether an account exists or is locked.
    """
    now = int(time.time() if now is None else now)
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

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
        return get_user(conn, user["id"])

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