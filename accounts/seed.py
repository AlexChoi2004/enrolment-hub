"""Seed the single synthetic demo student."""
from functools import lru_cache

from accounts.service import hash_password

DEMO_STUDENT_NUMBER = "DEMO0001"
# Public demo credential for a synthetic student. Not a real account or password.
DEMO_PASSWORD = "demo-student-2027"
DEMO_COURSE_CODE = "C09119"


@lru_cache(maxsize=1)
def _demo_password_hash():
    # Hashing is deliberately slow, so do it once per process (tests rebuild the DB often).
    return hash_password(DEMO_PASSWORD)


def seed_accounts(conn):
    exists = conn.execute(
        "SELECT 1 FROM users WHERE student_number = ?", (DEMO_STUDENT_NUMBER,)
    ).fetchone()
    if exists:
        return
    conn.execute(
        "INSERT INTO users (student_number, display_name, password_hash, course_code)"
        " VALUES (?, ?, ?, ?)",
        (DEMO_STUDENT_NUMBER, "Demo Student", _demo_password_hash(), DEMO_COURSE_CODE),
    )