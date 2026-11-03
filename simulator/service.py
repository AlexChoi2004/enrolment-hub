"""The semester simulator: finish a simulated semester, record the results, and move the student to the next one.

Everything goes through the same functions as the rest of the app (enrolment.results.record_result and the student's
own current session), so the transcript, planner, catalogue and timetable all react. Finishing a semester is ONE
transaction: either every result is saved and the session advances, or nothing changes.

Choices for each subject the student is enrolled in this session:
  passed / failed - a result is recorded (a new attempt; earlier attempts are kept);
  none            - "no result yet": NO attempt is recorded, nothing is invented, the enrolment ends and the subject
                    goes back to being an outstanding requirement.
Advancing the calendar never makes up passes or fails. All results are simulated demonstration data.
"""
from accounts.seed import DEMO_MAJOR_CODE, DEMO_STUDENT_NUMBER, DEMO_SUBMAJOR_CODE
from enrolment.results import ResultError, check_mark, record_result
from enrolment.seed import seed_enrolment
from enrolment.service import (
    CURRENT_SESSION,
    current_session_of,
    next_session,
    semester_number,
    session_sort_key,
    study_year,
)

RESULTS = ("passed", "failed", "none")
LABELS = {"passed": "Passed", "failed": "Failed", "none": "No result yet"}


class SimulatorError(Exception):
    """The simulator refused something. The message is safe to show to the student."""


def current_state(conn, user_id):
    """Where the student is now and which subjects they are enrolled in this session."""
    label = current_session_of(conn, user_id)
    commenced = conn.execute("SELECT commencement_session FROM users WHERE id = ?", (user_id,)).fetchone()[0]
    subjects = [
        dict(r) for r in conn.execute(
            "SELECT s.code, s.name, s.credit_points FROM enrolments e JOIN subjects s ON s.code = e.subject_code"
            " WHERE e.user_id = ? AND e.status = 'enrolled' AND e.session_label = ? ORDER BY s.code",
            (user_id, label),
        )
    ]
    later = conn.execute(
        "SELECT COUNT(*) FROM enrolments WHERE user_id = ? AND status = 'enrolled' AND session_label <> ?", (user_id, label)
    ).fetchone()[0]
    nxt = next_session(label)
    return {
        "label": label, "year": study_year(commenced, label), "semester": semester_number(label),
        "next": nxt, "next_year": study_year(commenced, nxt), "next_semester": semester_number(nxt),
        "subjects": subjects, "enrolled_later": later,
    }


def parse_choices(subjects, get):
    """Read the form: get("result_<code>") and get("mark_<code>"). Returns (choices, errors)."""
    choices, errors = {}, []
    for s in subjects:
        code = s["code"]
        result = (get(f"result_{code}") or "none").strip()
        raw = (get(f"mark_{code}") or "").strip()
        if result not in RESULTS:
            errors.append(f"{code} {s['name']}: choose Passed, Failed or No result yet.")
            continue
        mark = None
        if raw:
            if not raw.isdigit():
                errors.append(f"{code} {s['name']}: the mark must be a whole number from 0 to 100.")
                continue
            mark = int(raw)
        choices[code] = {"result": result, "mark": mark}
    return choices, errors


def check_choices(subjects, choices):
    """Problems with the choices as a whole, before anything is saved."""
    errors, names = [], {s["code"]: s["name"] for s in subjects}
    for code in set(choices) - set(names):
        errors.append(f"{code} is not one of the subjects you are enrolled in this session.")
    for code, c in choices.items():
        if code not in names:
            continue
        label = f"{code} {names[code]}"
        if c["result"] == "none":
            if c["mark"] is not None:
                errors.append(f"{label}: a mark can't be entered when there is no result yet.")
            continue
        try:
            check_mark(c["result"], c["mark"])
        except ResultError as exc:
            errors.append(f"{label}: {exc}")
    return errors


def complete_semester(conn, user_id, choices):
    """Save the results for this session's subjects and advance to the next session, all or nothing."""
    state = current_state(conn, user_id)
    errors = check_choices(state["subjects"], choices)
    if errors:
        raise SimulatorError(" ".join(errors))
    results, no_result = [], []
    try:
        for s in state["subjects"]:
            c = choices.get(s["code"], {"result": "none", "mark": None})
            if c["result"] == "none":
                conn.execute(
                    "DELETE FROM enrolments WHERE user_id = ? AND subject_code = ? AND status = 'enrolled'",
                    (user_id, s["code"]),
                )
                conn.execute("DELETE FROM class_choices WHERE user_id = ? AND subject_code = ?", (user_id, s["code"]))
                no_result.append(s)
            else:
                attempt = record_result(conn, user_id, s["code"], state["label"], c["result"], c["mark"], commit=False)
                results.append({**attempt, "name": s["name"]})
        conn.execute("UPDATE users SET current_session = ? WHERE id = ?", (state["next"], user_id))
        conn.commit()
    except Exception as exc:
        conn.rollback()
        if isinstance(exc, ResultError):
            raise SimulatorError(str(exc)) from exc
        raise
    passed_cp = sum(r["credit_points"] for r in [s for s in state["subjects"] if any(
        x["subject_code"] == s["code"] and x["outcome"] == "passed" for x in results)])
    stale = sum(
        1 for r in conn.execute("SELECT session_label FROM planned_subjects WHERE user_id = ?", (user_id,))
        if session_sort_key(r["session_label"]) < session_sort_key(state["next"])
    )
    return {
        "from": state["label"], "to": state["next"], "year": state["next_year"], "semester": state["next_semester"],
        "results": results, "no_result": no_result, "passed_cp": passed_cp, "plans_to_reschedule": stale,
    }


def reset_demo_student(conn):
    """Put the simulated demo student back exactly as seeded. Touches only the demo student's own records."""
    user = conn.execute("SELECT id FROM users WHERE student_number = ?", (DEMO_STUDENT_NUMBER,)).fetchone()
    if user is None:
        raise SimulatorError("There is no demo student to reset.")
    uid = user["id"]
    try:
        counts = {
            table: conn.execute(f"DELETE FROM {table} WHERE user_id = ?", (uid,)).rowcount  # noqa: S608 (fixed table names)
            for table in ("subject_attempts", "class_choices", "planned_subjects", "enrolments")
        }
        conn.execute(
            "UPDATE users SET current_session = ?, major_code = ?, submajor_code = ?, submajor_language = NULL,"
            " general_electives = 0 WHERE id = ?",
            (CURRENT_SESSION, DEMO_MAJOR_CODE, DEMO_SUBMAJOR_CODE, uid),
        )
        seed_enrolment(conn)  # the original history again, and the attempts behind it
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return counts
