"""Enrolment business logic: a student's record and which subjects they can take.

`evaluate_subjects` is the single place the eligibility rules live, so the catalogue
page and (next) the enrol endpoint can never disagree about what a student may do.
"""
from collections import defaultdict

from subject_catalogue.service import ELECTIVE_CATEGORIES, ELECTIVE_CREDIT_POINTS

CURRENT_SESSION = "Autumn 2027"  # the session the prototype treats as "now"
MAX_CP_PER_SESSION = 24  # a full load: four 6 cp subjects


class EnrolmentError(Exception):
    """An enrolment change was refused. The message is safe to show to the student."""


def open_sessions(current_session=CURRENT_SESSION):
    """Sessions a student may enrol in: the current one and, from Autumn, the Spring after it."""
    season, year = current_session.split()
    return [current_session, f"Spring {year}"] if season == "Autumn" else [current_session]


def offered_in(sessions_offered, session_label):
    return sessions_offered in (session_label.split()[0], "Both")


def study_year(commencement_session, current_session=CURRENT_SESSION):
    """Which year of study a student is in (the year they start is Year 1)."""
    return int(current_session.split()[1]) - int(commencement_session.split()[1]) + 1


def session_sort_key(label):
    """Order session labels like 'Autumn 2025' chronologically (Autumn before Spring)."""
    season, year = label.split()
    return int(year), 0 if season == "Autumn" else 1


def get_course(conn, course_code):
    row = conn.execute(
        "SELECT code, name, major_name FROM courses WHERE code = ?", (course_code,)
    ).fetchone()
    return dict(row) if row else None


def get_record(conn, user_id):
    """One student's academic record. Only ever queries the given user's rows."""
    rows = conn.execute(
        "SELECT e.status, e.session_label, s.code, s.name, s.credit_points,"
        " c.label AS category_label"
        " FROM enrolments e"
        " JOIN subjects s ON s.code = e.subject_code"
        " JOIN requirement_categories c ON c.category = s.category"
        " WHERE e.user_id = ?",
        (user_id,),
    ).fetchall()
    items = sorted(
        (dict(r) for r in rows),
        key=lambda r: (session_sort_key(r["session_label"]), r["code"]),
    )
    completed = [i for i in items if i["status"] == "completed"]
    enrolled = [i for i in items if i["status"] == "enrolled"]

    by_session = {}
    for item in completed:
        by_session.setdefault(item["session_label"], []).append(item)

    completed_cp = sum(i["credit_points"] for i in completed)
    enrolled_cp = sum(i["credit_points"] for i in enrolled)
    degree_total = conn.execute(
        "SELECT SUM(required_credit_points) AS total FROM requirement_categories"
    ).fetchone()["total"]
    return {
        "completed_by_session": list(by_session.items()),
        "enrolled": enrolled,
        "completed_cp": completed_cp,
        "enrolled_cp": enrolled_cp,
        "counted_cp": completed_cp + enrolled_cp,  # one row per subject, so never double counted
        "degree_total_cp": degree_total,
    }


def evaluate_subjects(conn, user_id):
    """Work out, for one student, the status of every subject.

    Statuses: completed, enrolled, available (can enrol now) or blocked (with reasons).
    A subject is blocked if a prerequisite is not COMPLETED (in progress does not count),
    if its elective requirement is already full, or if every open session it is offered in
    is full. Only this student's rows are read.

    Returns {"subjects": {code: info}, "categories": {category: progress},
             "records": {code: status}, "session_loads": {session: credit points}}.
    """
    records = {}
    sessions = {}
    for row in conn.execute(
        "SELECT subject_code, status, session_label FROM enrolments WHERE user_id = ?", (user_id,)
    ):
        records[row["subject_code"]] = row["status"]
        sessions[row["subject_code"]] = row["session_label"]

    subjects = conn.execute(
        "SELECT code, name, category, credit_points, sessions_offered FROM subjects"
    ).fetchall()
    names = {s["code"]: s["name"] for s in subjects}
    prerequisites = defaultdict(list)
    for row in conn.execute("SELECT subject_code, prereq_code FROM prerequisites ORDER BY prereq_code"):
        prerequisites[row["subject_code"]].append(row["prereq_code"])

    categories = {}
    for row in conn.execute(
        "SELECT category, label, required_credit_points FROM requirement_categories"
    ):
        categories[row["category"]] = {
            "label": row["label"],
            "required_cp": row["required_credit_points"],
            "pool": 0,
            "completed": 0,
            "enrolled": 0,
            "counted_cp": 0,
        }
    for s in subjects:
        progress = categories[s["category"]]
        progress["pool"] += 1
        state = records.get(s["code"])
        if state in ("completed", "enrolled"):
            progress[state] += 1
            progress["counted_cp"] += s["credit_points"]  # one record per subject: no double counting

    open_labels = open_sessions()
    loads = {label: 0 for label in open_labels}
    for s in subjects:
        if records.get(s["code"]) == "enrolled" and sessions[s["code"]] in loads:
            loads[sessions[s["code"]]] += s["credit_points"]

    def with_room(subject, labels):
        return [
            label for label in labels
            if offered_in(subject["sessions_offered"], label)
            and loads[label] + subject["credit_points"] <= MAX_CP_PER_SESSION
        ]

    result = {}
    for s in subjects:
        code = s["code"]
        state = records.get(code)
        reasons = []
        roomy = []
        moves = []
        if state == "completed":
            status, note = "completed", f"Completed in {sessions[code]}"
        elif state == "enrolled":
            status, note = "enrolled", f"In progress in {sessions[code]}"
            moves = with_room(s, [label for label in open_labels if label != sessions[code]])
        else:
            missing = [p for p in prerequisites[code] if records.get(p) != "completed"]
            if missing:
                reasons.append("Needs " + ", ".join(f"{p} {names[p]}" for p in missing))
            progress = categories[s["category"]]
            if s["category"] in ELECTIVE_CATEGORIES and progress["counted_cp"] >= progress["required_cp"]:
                reasons.append(f"{progress['label']} requirement already complete")
            if not reasons:
                offered = [label for label in open_labels if offered_in(s["sessions_offered"], label)]
                roomy = with_room(s, open_labels)
                if not offered:
                    reasons.append("Not offered in " + " or ".join(open_labels))
                elif not roomy:
                    reasons.append(
                        " and ".join(
                            f"{label} is full ({loads[label]} of {MAX_CP_PER_SESSION} credit points)"
                            for label in offered
                        )
                    )
            status = "blocked" if reasons else "available"
            note = " · ".join(reasons)
        result[code] = {
            "status": status,
            "reasons": reasons,
            "note": note,
            "sessions": roomy,  # sessions this subject could be enrolled in right now
            "move_sessions": moves,  # for enrolled subjects: other sessions they could move to
        }
    return {
        "subjects": result,
        "categories": categories,
        "records": records,
        "session_loads": loads,
    }


# --- changing an enrolment -------------------------------------------------------------------

def _describe(conn, code):
    row = conn.execute("SELECT code, name, credit_points, sessions_offered FROM subjects WHERE code = ?", (code,)).fetchone()
    return row


def _session_problem(conn, user_id, subject, session_label, exclude_code=None):
    """Why a subject can't go into a session, or None if it can."""
    if session_label not in open_sessions():
        return "You can only enrol in " + " or ".join(open_sessions()) + "."
    if not offered_in(subject["sessions_offered"], session_label):
        return f"{subject['code']} {subject['name']} is not offered in {session_label}."
    load = conn.execute(
        "SELECT COALESCE(SUM(s.credit_points), 0) AS cp FROM enrolments e"
        " JOIN subjects s ON s.code = e.subject_code"
        " WHERE e.user_id = ? AND e.status = 'enrolled' AND e.session_label = ? AND e.subject_code <> ?",
        (user_id, session_label, exclude_code or ""),
    ).fetchone()["cp"]
    if load + subject["credit_points"] > MAX_CP_PER_SESSION:
        return (
            f"{session_label} is full ({load} of {MAX_CP_PER_SESSION} credit points), so there is no room "
            f"for {subject['code']} {subject['name']} ({subject['credit_points']} cp). "
            "Choose another session or withdraw from a subject first."
        )
    return None


def enrol(conn, user_id, subject_code, session_label):
    """Enrol a student in a subject for one session, or raise EnrolmentError with the reason."""
    subject = _describe(conn, subject_code)
    if subject is None:
        raise EnrolmentError("That subject does not exist.")
    label = f"{subject['code']} {subject['name']}"

    info = evaluate_subjects(conn, user_id)["subjects"][subject_code]
    if info["status"] == "completed":
        raise EnrolmentError(f"You have already completed {label}.")
    if info["status"] == "enrolled":
        raise EnrolmentError(f"You are already enrolled in {label}.")
    if info["status"] == "blocked":
        raise EnrolmentError(f"You can't enrol in {label}: {info['note']}.")

    problem = _session_problem(conn, user_id, subject, session_label)
    if problem:
        raise EnrolmentError(problem)

    # The room check is repeated inside the INSERT so two requests at once can't both squeeze in.
    cur = conn.execute(
        "INSERT INTO enrolments (user_id, subject_code, status, session_label)"
        " SELECT ?, ?, 'enrolled', ?"
        " WHERE (SELECT COALESCE(SUM(s.credit_points), 0) FROM enrolments e"
        "        JOIN subjects s ON s.code = e.subject_code"
        "        WHERE e.user_id = ? AND e.status = 'enrolled' AND e.session_label = ?) + ? <= ?",
        (user_id, subject_code, session_label, user_id, session_label,
         subject["credit_points"], MAX_CP_PER_SESSION),
    )
    if cur.rowcount != 1:
        conn.rollback()
        raise EnrolmentError(f"{session_label} is full, so {label} could not be added.")
    conn.commit()
    return label


def withdraw(conn, user_id, subject_code):
    """Remove an in-progress enrolment. Completed subjects are history and cannot be removed."""
    row = conn.execute(
        "SELECT e.status, s.code, s.name FROM enrolments e JOIN subjects s ON s.code = e.subject_code"
        " WHERE e.user_id = ? AND e.subject_code = ?",
        (user_id, subject_code),
    ).fetchone()
    if row is None:
        raise EnrolmentError(f"You are not enrolled in {subject_code}.")
    label = f"{row['code']} {row['name']}"
    if row["status"] == "completed":
        raise EnrolmentError(f"{label} is completed and can't be withdrawn.")
    conn.execute(
        "DELETE FROM enrolments WHERE user_id = ? AND subject_code = ? AND status = 'enrolled'",
        (user_id, subject_code),
    )
    conn.commit()
    return label


def move_session(conn, user_id, subject_code, new_session):
    """Move an in-progress enrolment to another open session."""
    row = conn.execute(
        "SELECT e.status, e.session_label FROM enrolments e WHERE e.user_id = ? AND e.subject_code = ?",
        (user_id, subject_code),
    ).fetchone()
    if row is None:
        raise EnrolmentError(f"You are not enrolled in {subject_code}.")
    subject = _describe(conn, subject_code)
    label = f"{subject['code']} {subject['name']}"
    if row["status"] == "completed":
        raise EnrolmentError(f"{label} is completed and can't be moved.")
    if row["session_label"] == new_session:
        raise EnrolmentError(f"{label} is already in {new_session}.")
    problem = _session_problem(conn, user_id, subject, new_session, exclude_code=subject_code)
    if problem:
        raise EnrolmentError(problem)
    conn.execute(
        "UPDATE enrolments SET session_label = ? WHERE user_id = ? AND subject_code = ? AND status = 'enrolled'",
        (new_session, user_id, subject_code),
    )
    conn.commit()
    return label