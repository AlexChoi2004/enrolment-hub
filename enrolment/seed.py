"""Seed the synthetic demo student's academic history (about two years in).

Invented data. The history respects the supplied prerequisite rules and the
illustrative session offerings, so it makes a sensible starting point for
demonstrating eligibility checks: some subjects are now available, and some
(for example Honours Project A) are blocked until a prerequisite is completed.
"""
from accounts.seed import DEMO_STUDENT_NUMBER
from enrolment.results import default_mark, grade_for
from enrolment.service import CURRENT_SESSION


# (session, status, subject codes). 16 completed subjects = 96 cp (including all four core subjects of the
# Innovation and Entrepreneurship sub-major, so that requirement is complete), then 4 in progress = 24 cp.
DEMO_HISTORY = [
    ("Autumn 2025", "completed", ["41039", "33130", "31268", "48080"]),
    ("Spring 2025", "completed", ["48024", "33230", "31269", "81529"]),
    ("Autumn 2026", "completed", ["31251", "41025", "41078", "31271"]),
    ("Spring 2026", "completed", ["48433", "31282", "81546", "81547"]),
    (CURRENT_SESSION, "enrolled", ["41026", "31272", "32144", "41040"]),
]


def seed_enrolment(conn, profile="fresh"):
    """The sample profile gets the two-year history; the fresh profile starts with nothing at all."""
    if profile != "sample":
        return
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
    # The results behind the completed subjects, so the transcript and the enrolments never disagree.
    conn.executemany(
        "INSERT OR IGNORE INTO subject_attempts (user_id, subject_code, session_label, attempt_number, outcome, mark,"
        " grade, source) VALUES (?, ?, ?, 1, 'passed', ?, ?, 'seed')",
        [
            (user["id"], code, session, default_mark(user["id"], code, 1, "passed"),
             grade_for(default_mark(user["id"], code, 1, "passed")))
            for session, status, codes in DEMO_HISTORY if status == "completed" for code in codes
        ],
    )
