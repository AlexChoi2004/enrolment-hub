"""Enrolment business logic (grows in later chunks)."""

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