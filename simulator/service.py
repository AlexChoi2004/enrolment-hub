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
import json

from accounts.seed import DEMO_PROFILES, DEMO_STUDENT_NUMBER, demo_profile_state
from enrolment.results import ResultError, check_mark, record_result
from enrolment.seed import seed_enrolment
from enrolment.service import (
    CURRENT_SESSION,
    current_session_of,
    next_session,
    open_sessions,
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


def period(conn, user_id):
    """Just the current session, year and semester (cheap enough to show on every page)."""
    label = current_session_of(conn, user_id)
    commenced = conn.execute("SELECT commencement_session FROM users WHERE id = ?", (user_id,)).fetchone()[0]
    return {"label": label, "year": study_year(commenced, label), "semester": semester_number(label)}


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
    snapshot = _snapshot(conn, user_id, state["subjects"])  # what to put back if the student rolls this semester back
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
        snapshot["attempt_ids"] = [r[0] for r in conn.execute(
            "SELECT id FROM subject_attempts WHERE user_id = ? AND id > ? ORDER BY id", (user_id, snapshot["last_attempt_id"]))]
        conn.execute("INSERT INTO semester_log (user_id, session_label, snapshot) VALUES (?, ?, ?)",
                     (user_id, state["label"], json.dumps(snapshot)))
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


def _snapshot(conn, user_id, subjects):
    """What completing the semester is about to change, for the subjects enrolled this session."""
    codes = [s["code"] for s in subjects]
    marks = ",".join("?" for _ in codes)
    rows = lambda table, columns: [  # noqa: E731 (table and columns are fixed names in this file, never user input)
        dict(r) for r in conn.execute(
            f"SELECT {columns} FROM {table} WHERE user_id = ? AND subject_code IN ({marks})", (user_id, *codes))  # noqa: S608
    ] if codes else []
    return {
        "codes": codes,
        "enrolments": rows("enrolments", "subject_code, status, session_label"),
        "class_choices": rows("class_choices", "subject_code, component, class_id"),
        "planned": rows("planned_subjects", "subject_code, session_label"),
        "last_attempt_id": conn.execute("SELECT COALESCE(MAX(id), 0) FROM subject_attempts WHERE user_id = ?", (user_id,)).fetchone()[0],
    }


def can_roll_back(conn, user_id):
    return conn.execute("SELECT COUNT(*) FROM semester_log WHERE user_id = ?", (user_id,)).fetchone()[0] > 0


def rollback_preview(conn, user_id):
    """What rolling back the most recent completed semester would undo, or None if there is nothing to roll back."""
    log = conn.execute("SELECT * FROM semester_log WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
    if log is None:
        return None
    snap = json.loads(log["snapshot"])
    marks = ",".join("?" for _ in snap["attempt_ids"]) or "NULL"  # only "?" placeholders are ever put into the query text
    query = ("SELECT a.subject_code, s.name, a.outcome, a.mark, a.grade FROM subject_attempts a"  # noqa: S608
             f" JOIN subjects s ON s.code = a.subject_code WHERE a.user_id = ? AND a.id IN ({marks}) ORDER BY a.id")
    attempts = [dict(r) for r in conn.execute(query, (user_id, *snap["attempt_ids"]))]
    names = {r["code"]: r["name"] for r in conn.execute("SELECT code, name FROM subjects")}
    return {"session": log["session_label"], "from": current_session_of(conn, user_id), "attempts": attempts,
            "subjects": [{"code": c, "name": names[c]} for c in snap["codes"]],
            "no_result": [{"code": c, "name": names[c]} for c in snap["codes"] if c not in {a["subject_code"] for a in attempts}]}


def roll_back_semester(conn, user_id):
    """Undo the most recent completed semester: remove the results it recorded, put the subjects back as enrolled (with their
    class choices and plan entries) and return to that session. All or nothing. Anything done since to those subjects is replaced,
    and enrolments that would now be too far ahead go back into the plan."""
    log = conn.execute("SELECT * FROM semester_log WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
    if log is None:
        raise SimulatorError("There is no completed semester to roll back.")
    snap = json.loads(log["snapshot"])
    before = current_session_of(conn, user_id)
    try:
        for attempt_id in snap["attempt_ids"]:
            conn.execute("DELETE FROM subject_attempts WHERE id = ? AND user_id = ?", (attempt_id, user_id))
        for code in snap["codes"]:
            for table in ("enrolments", "class_choices", "planned_subjects"):
                conn.execute(f"DELETE FROM {table} WHERE user_id = ? AND subject_code = ?", (user_id, code))  # noqa: S608 (fixed names)
        for r in snap["enrolments"]:
            conn.execute("INSERT INTO enrolments (user_id, subject_code, status, session_label) VALUES (?, ?, ?, ?)",
                         (user_id, r["subject_code"], r["status"], r["session_label"]))
        for r in snap["class_choices"]:
            conn.execute("INSERT INTO class_choices (user_id, subject_code, component, class_id) VALUES (?, ?, ?, ?)",
                         (user_id, r["subject_code"], r["component"], r["class_id"]))
        for r in snap["planned"]:
            conn.execute("INSERT INTO planned_subjects (user_id, subject_code, session_label) VALUES (?, ?, ?)",
                         (user_id, r["subject_code"], r["session_label"]))
        conn.execute("UPDATE users SET current_session = ? WHERE id = ?", (log["session_label"], user_id))
        window = open_sessions(log["session_label"])
        too_far = [r for r in conn.execute(
            "SELECT subject_code, session_label FROM enrolments WHERE user_id = ? AND status = 'enrolled'", (user_id,))
            if r["session_label"] not in window]
        for r in too_far:  # enrolled for a session that is no longer next: it goes back to being a plan
            conn.execute("DELETE FROM enrolments WHERE user_id = ? AND subject_code = ?", (user_id, r["subject_code"]))
            conn.execute("DELETE FROM class_choices WHERE user_id = ? AND subject_code = ?", (user_id, r["subject_code"]))
            conn.execute("INSERT OR IGNORE INTO planned_subjects (user_id, subject_code, session_label) VALUES (?, ?, ?)",
                         (user_id, r["subject_code"], r["session_label"]))
        conn.execute("DELETE FROM semester_log WHERE id = ?", (log["id"],))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"from": before, "to": log["session_label"], "removed_results": len(snap["attempt_ids"]),
            "restored": len(snap["codes"]), "back_to_plan": len(too_far)}


def reset_demo_student(conn, profile="fresh"):
    """Put the simulated demo student back exactly as seeded. Touches only the demo student's own records.

    profile "fresh" starts a first-year student in Year 1, Semester 1 with nothing done; "sample" loads the
    two-year history (Year 3, Semester 1) so there is a record to explore.
    """
    if profile not in DEMO_PROFILES:
        raise SimulatorError("Choose a starting point from the list.")
    user = conn.execute("SELECT id FROM users WHERE student_number = ?", (DEMO_STUDENT_NUMBER,)).fetchone()
    if user is None:
        raise SimulatorError("There is no demo student to reset.")
    uid = user["id"]
    try:
        counts = {
            table: conn.execute(f"DELETE FROM {table} WHERE user_id = ?", (uid,)).rowcount  # noqa: S608 (fixed table names)
            for table in ("semester_log", "elective_credits", "subject_attempts", "class_choices", "planned_subjects", "enrolments")
        }
        commencement, current, major, submajor = demo_profile_state(profile)
        conn.execute(
            "UPDATE users SET current_session = ?, commencement_session = ?, major_code = ?, submajor_code = ?,"
            " submajor_language = NULL, general_electives = 0 WHERE id = ?",
            (current, commencement, major, submajor, uid),
        )
        seed_enrolment(conn, profile)  # the sample history and the attempts behind it (nothing for a fresh start)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return counts
