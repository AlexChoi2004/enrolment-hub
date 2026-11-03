"""The academic transcript: every result for the student, grouped by session. Reads the same records as everything else."""
from enrolment.results import attempts_for, failed_subjects
from enrolment.service import get_record, session_sort_key


def transcript(conn, user_id, newest_first=False):
    """Rows grouped by session (oldest first), plus totals. All of it is simulated demonstration data."""
    attempts = attempts_for(conn, user_id)
    per_subject = {}
    for a in attempts:
        per_subject[a["subject_code"]] = per_subject.get(a["subject_code"], 0) + 1
    rows = []
    for a in attempts:
        rows.append({
            "code": a["subject_code"], "name": a["name"], "session": a["session_label"], "credit_points": a["credit_points"],
            "mark": a["mark"], "grade": a["grade"], "kind": a["outcome"],
            "outcome": "Passed" if a["outcome"] == "passed" else "Failed", "attempt": a["attempt_number"],
        })
    for r in conn.execute(
        "SELECT e.subject_code, e.session_label, s.name, s.credit_points FROM enrolments e"
        " JOIN subjects s ON s.code = e.subject_code WHERE e.user_id = ? AND e.status = 'enrolled'", (user_id,)
    ):
        rows.append({
            "code": r["subject_code"], "name": r["name"], "session": r["session_label"], "credit_points": r["credit_points"],
            "mark": None, "grade": None, "kind": "in_progress", "outcome": "In Progress",
            "attempt": per_subject.get(r["subject_code"], 0) + 1,
        })
    by_session = {}
    for row in rows:
        by_session.setdefault(row["session"], []).append(row)
    groups = []
    for label in sorted(by_session, key=session_sort_key):
        year, season = label.split()[1], label.split()[0]
        groups.append({"label": label, "year": year, "season": season, "rows": sorted(by_session[label], key=lambda r: (r["code"], r["attempt"]))})
    record = get_record(conn, user_id)
    if newest_first:
        groups.reverse()
    return {
        "newest_first": newest_first,
        "groups": groups,
        "attempt_count": len(attempts),
        "passed_cp": record["completed_cp"],  # each subject once, however many attempts it took
        "failed_attempts": sum(1 for a in attempts if a["outcome"] == "failed"),
        "in_progress": sum(1 for r in rows if r["kind"] == "in_progress"),
        "retakes": sorted(failed_subjects(conn, user_id)),
    }
