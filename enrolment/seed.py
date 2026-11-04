"""Seed the synthetic demo student's academic history from a preset (see enrolment/presets.py).

Invented data. Every preset respects the supplied prerequisite rules and the illustrative session offerings, so each makes a
sensible starting point for demonstrating eligibility checks, swaps, failed subjects and the planner.
"""
from accounts.seed import DEMO_STUDENT_NUMBER
from enrolment.presets import PRESETS
from enrolment.results import default_mark, grade_for


def seed_enrolment(conn, profile="fresh"):
    """Load the preset's finished sessions, its attempts (passes and fails), what is in progress and what is planned."""
    preset = PRESETS[profile]
    user = conn.execute("SELECT id FROM users WHERE student_number = ?", (DEMO_STUDENT_NUMBER,)).fetchone()
    if user is None:
        return
    uid = user["id"]
    for session, results in preset["history"]:
        for number, (code, outcome) in enumerate(results, 1):
            attempt = 2 if outcome == "passed" and _failed_before(conn, uid, code) else 1  # a pass after a fail is attempt 2
            mark = default_mark(uid, code, attempt, outcome)
            conn.execute(
                "INSERT OR IGNORE INTO subject_attempts (user_id, subject_code, session_label, attempt_number, outcome, mark, grade, source)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, 'seed')", (uid, code, session, attempt, outcome, mark, grade_for(mark)),
            )
            if outcome == "passed":
                conn.execute(
                    "INSERT OR IGNORE INTO enrolments (user_id, subject_code, status, session_label) VALUES (?, ?, 'completed', ?)",
                    (uid, code, session),
                )
    for code in preset["enrolled"]:
        conn.execute(
            "INSERT OR IGNORE INTO enrolments (user_id, subject_code, status, session_label) VALUES (?, ?, 'enrolled', ?)",
            (uid, code, preset["current"]),
        )
    for code, session in preset["plan"]:
        conn.execute("INSERT OR IGNORE INTO planned_subjects (user_id, subject_code, session_label) VALUES (?, ?, ?)", (uid, code, session))


def _failed_before(conn, user_id, code):
    return conn.execute(
        "SELECT 1 FROM subject_attempts WHERE user_id = ? AND subject_code = ? AND outcome = 'failed'", (user_id, code)
    ).fetchone() is not None
