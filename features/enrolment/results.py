"""Academic results: every finished attempt at a subject, and how a result changes the student's current state.

The rules in one place:
  * a result is a new row in subject_attempts; earlier attempts are never changed or deleted (a retake adds a row);
  * a pass makes the subject 'completed' in enrolments, a fail removes the in-progress row, so a failed subject is an
    outstanding requirement again and counts for zero credit points;
  * a subject can only be passed once, so credit points are counted exactly once however many attempts there were.
All of it runs in one transaction. Every mark and grade is simulated demonstration data.
"""
import zlib

PASS_MARK = 50
GRADES = (("HD", 85), ("D", 75), ("C", 65), ("P", PASS_MARK))
OUTCOMES = ("passed", "failed")


class ResultError(Exception):
    """A result was refused. The message is safe to show to the student."""


def grade_for(mark):
    """HD 85+, D 75-84, C 65-74, P 50-64, FL below 50."""
    for grade, floor in GRADES:
        if mark >= floor:
            return grade
    return "FL"


def default_mark(user_id, subject_code, attempt_number, outcome):
    """A plausible, repeatable mark for a simulated result: 50-89 for a pass, 20-49 for a fail."""
    n = zlib.crc32(f"{user_id}:{subject_code}:{attempt_number}".encode())
    return 50 + n % 40 if outcome == "passed" else 20 + n % 30


def check_mark(outcome, mark):
    """Raise ResultError unless this outcome and mark (or no mark) make sense together."""
    if outcome not in OUTCOMES:
        raise ResultError("A result must be passed or failed.")
    if mark is None:
        return
    if not isinstance(mark, int) or isinstance(mark, bool) or not 0 <= mark <= 100:
        raise ResultError("A mark must be a whole number from 0 to 100.")
    if (outcome == "passed") != (mark >= PASS_MARK):
        raise ResultError(f"A mark of {mark} is a {'pass' if mark >= PASS_MARK else 'fail'}, not a {outcome[:-2]}.")


def record_result(conn, user_id, subject_code, session_label, outcome, mark=None, source="simulated", commit=True):
    """Record one finished attempt and bring the student's current state into line. Returns the new attempt."""
    check_mark(outcome, mark)
    subject = conn.execute("SELECT code, name FROM subjects WHERE code = ?", (subject_code,)).fetchone()
    if subject is None:
        raise ResultError("That subject does not exist.")
    label = f"{subject['code']} {subject['name']}"
    previous = conn.execute(
        "SELECT outcome FROM subject_attempts WHERE user_id = ? AND subject_code = ?", (user_id, subject_code)
    ).fetchall()
    if any(r["outcome"] == "passed" for r in previous):
        raise ResultError(f"You have already passed {label}.")
    number = len(previous) + 1
    if mark is None:
        mark = default_mark(user_id, subject_code, number, outcome)
    try:
        conn.execute(
            "INSERT INTO subject_attempts (user_id, subject_code, session_label, attempt_number, outcome, mark, grade, source)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, subject_code, session_label, number, outcome, mark, grade_for(mark), source),
        )
        if outcome == "passed":
            conn.execute(
                "INSERT INTO enrolments (user_id, subject_code, status, session_label) VALUES (?, ?, 'completed', ?)"
                " ON CONFLICT (user_id, subject_code) DO UPDATE SET status = 'completed', session_label = excluded.session_label",
                (user_id, subject_code, session_label),
            )
            conn.execute("DELETE FROM planned_subjects WHERE user_id = ? AND subject_code = ?", (user_id, subject_code))
        else:
            conn.execute(
                "DELETE FROM enrolments WHERE user_id = ? AND subject_code = ? AND status = 'enrolled'", (user_id, subject_code)
            )
        conn.execute("DELETE FROM class_choices WHERE user_id = ? AND subject_code = ?", (user_id, subject_code))
    except Exception:
        conn.rollback()
        raise
    if commit:
        conn.commit()
    return {"subject_code": subject_code, "attempt_number": number, "outcome": outcome, "mark": mark,
            "grade": grade_for(mark), "session_label": session_label}


def attempts_for(conn, user_id):
    """Every finished attempt for one student, oldest first."""
    return [
        dict(r) for r in conn.execute(
            "SELECT a.*, s.name, s.credit_points FROM subject_attempts a JOIN subjects s ON s.code = a.subject_code"
            " WHERE a.user_id = ? ORDER BY a.id", (user_id,)
        )
    ]


def failed_subjects(conn, user_id):
    """{code: details} for subjects the student has failed and not yet passed (they need a retake)."""
    failed = {}
    passed = {r["subject_code"] for r in conn.execute(
        "SELECT subject_code FROM subject_attempts WHERE user_id = ? AND outcome = 'passed'", (user_id,))}
    for r in conn.execute(
        "SELECT subject_code, session_label, attempt_number, outcome, mark FROM subject_attempts"
        " WHERE user_id = ? ORDER BY id", (user_id,)
    ):
        code = r["subject_code"]
        if code in passed:
            continue
        entry = failed.setdefault(code, {"failures": 0, "attempts": 0})
        entry["attempts"] += 1
        entry["failures"] += 1
        entry.update(last_session=r["session_label"], last_mark=r["mark"], last_attempt=r["attempt_number"])
    return failed
