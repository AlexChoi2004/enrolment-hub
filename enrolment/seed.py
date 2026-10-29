"""Seed the synthetic demo student's academic history (about two years in).

Invented data. The history respects the supplied prerequisite rules and the
illustrative session offerings, so it makes a sensible starting point for
demonstrating eligibility checks: some subjects are now available, and some
(for example Honours Project A) are blocked until a prerequisite is completed.
"""
from accounts.seed import DEMO_STUDENT_NUMBER

from enrolment.service import CURRENT_SESSION

# (session, status, subject codes). 16 completed subjects = 96 cp (including all four general
# electives, so that requirement is complete), then 4 in progress = 24 cp.
DEMO_HISTORY = [
    ("Autumn 2025", "completed", ["41039", "33130", "31271", "SYN101"]),
    ("Spring 2025", "completed", ["48024", "33230", "31269", "SYN103"]),
    ("Autumn 2026", "completed", ["31251", "41025", "41078", "31268"]),
    ("Spring 2026", "completed", ["48433", "31282", "SYN106", "SYN109"]),
    (CURRENT_SESSION, "enrolled", ["41026", "31272", "32144", "41040"]),
]


def seed_enrolment(conn):
    user = conn.execute(
        "SELECT id FROM users WHERE student_number = ?", (DEMO_STUDENT_NUMBER,)
    ).fetchone()
    if user is None:
        return
    rows = [
        (user["id"], code, status, session)
        for session, status, codes in DEMO_HISTORY
        for code in codes
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO enrolments (user_id, subject_code, status, session_label)"
        " VALUES (?, ?, ?, ?)",
        rows,
    )