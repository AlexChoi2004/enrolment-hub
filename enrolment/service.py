"""Enrolment business logic: a student's record and which subjects they can take.

`evaluate_subjects` is the single place the eligibility rules live, so the catalogue
page and (next) the enrol endpoint can never disagree about what a student may do.
"""
from collections import defaultdict

from subject_catalogue.service import ELECTIVE_CATEGORIES, ELECTIVE_CREDIT_POINTS

CURRENT_SESSION = "Autumn 2027"  # the session the prototype treats as "now"


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
    A subject is blocked if a prerequisite is not COMPLETED (in progress does not count)
    or if its elective requirement is already full. Only this student's rows are read.

    Returns {"subjects": {code: info}, "categories": {category: progress}, "records": {code: status}}.
    """
    records = {}
    sessions = {}
    for row in conn.execute(
        "SELECT subject_code, status, session_label FROM enrolments WHERE user_id = ?", (user_id,)
    ):
        records[row["subject_code"]] = row["status"]
        sessions[row["subject_code"]] = row["session_label"]

    subjects = conn.execute("SELECT code, name, category, credit_points FROM subjects").fetchall()
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

    result = {}
    for s in subjects:
        code = s["code"]
        state = records.get(code)
        reasons = []
        if state == "completed":
            status, note = "completed", f"Completed in {sessions[code]}"
        elif state == "enrolled":
            status, note = "enrolled", f"In progress in {sessions[code]}"
        else:
            missing = [p for p in prerequisites[code] if records.get(p) != "completed"]
            if missing:
                reasons.append("Needs " + ", ".join(f"{p} {names[p]}" for p in missing))
            progress = categories[s["category"]]
            if s["category"] in ELECTIVE_CATEGORIES and progress["counted_cp"] >= progress["required_cp"]:
                reasons.append(f"{progress['label']} requirement already complete")
            status = "blocked" if reasons else "available"
            note = " · ".join(reasons)
        result[code] = {"status": status, "reasons": reasons, "note": note}
    return {"subjects": result, "categories": categories, "records": records}