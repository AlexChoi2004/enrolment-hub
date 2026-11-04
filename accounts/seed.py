"""Seed the synthetic demo student."""
from functools import lru_cache

from accounts.service import hash_password

DEMO_EMAIL = "john.doe@student.uni.edu.au"
DEMO_STUDENT_NUMBER = "DEMO0001"
# Public demo credential for a synthetic student. Not a real account or password.
DEMO_PASSWORD = "Johndoe#1"  # noqa: S105 (intentionally public; shown on the login page)
DEMO_DISPLAY_NAME = "John Doe"
DEMO_COURSE_CODE = "C09119"
DEMO_MAJOR_CODE = "MAJ03519"  # Enterprise Software Development; new accounts choose theirs
DEMO_SUBMAJOR_CODE = "SMJ10156"  # Innovation and Entrepreneurship (four core subjects, completed)
DEMO_COMMENCEMENT_SESSION = "Autumn 2025"  # the sample history: two years before the app's current session
DEMO_PROFILES = ("fresh", "sample", "late", "failed")  # the starting points; their data is in enrolment/presets.py


def demo_profile_state(profile):
    """(commencement session, current session, major, sub-major) the demo student has under a profile."""
    from enrolment.presets import preset_state

    return preset_state(profile)


@lru_cache(maxsize=1)
def _demo_password_hash():
    # Hashing is deliberately slow, so do it once per process (tests rebuild the DB often).
    return hash_password(DEMO_PASSWORD)


def seed_accounts(conn, profile="fresh"):
    commencement, current, major, submajor = demo_profile_state(profile)
    exists = conn.execute("SELECT 1 FROM users WHERE email = ?", (DEMO_EMAIL,)).fetchone()
    if exists:
        return
    conn.execute(
        "INSERT INTO users (email, student_number, display_name, password_hash,"
        " course_code, commencement_session, current_session, major_code, submajor_code) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            DEMO_EMAIL,
            DEMO_STUDENT_NUMBER,
            DEMO_DISPLAY_NAME,
            _demo_password_hash(),
            DEMO_COURSE_CODE,
            commencement,
            current,
            major,
            submajor,
        ),
    )
