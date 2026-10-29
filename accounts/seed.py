"""Seed the synthetic demo student."""
from functools import lru_cache

from accounts.service import hash_password

DEMO_EMAIL = "john.doe@student.uni.edu.au"
DEMO_STUDENT_NUMBER = "DEMO0001"
# Public demo credential for a synthetic student. Not a real account or password.
DEMO_PASSWORD = "Johndoe#1"
DEMO_DISPLAY_NAME = "John Doe"
DEMO_COURSE_CODE = "C09119"
DEMO_COMMENCEMENT_SESSION = "Autumn 2025"  # two years before the app's current session


@lru_cache(maxsize=1)
def _demo_password_hash():
    # Hashing is deliberately slow, so do it once per process (tests rebuild the DB often).
    return hash_password(DEMO_PASSWORD)


def seed_accounts(conn):
    exists = conn.execute("SELECT 1 FROM users WHERE email = ?", (DEMO_EMAIL,)).fetchone()
    if exists:
        return
    conn.execute(
        "INSERT INTO users (email, student_number, display_name, password_hash,"
        " course_code, commencement_session) VALUES (?, ?, ?, ?, ?, ?)",
        (
            DEMO_EMAIL,
            DEMO_STUDENT_NUMBER,
            DEMO_DISPLAY_NAME,
            _demo_password_hash(),
            DEMO_COURSE_CODE,
            DEMO_COMMENCEMENT_SESSION,
        ),
    )