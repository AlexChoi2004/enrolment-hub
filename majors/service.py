"""Choosing and swapping a major.

A student confirms one major. Their Subjects page, planner and enrolment rules then use that
major's core and option subjects. Swapping is allowed as long as nothing they have already
completed or are enrolled in only counts towards the major they are leaving.
"""
from subject_catalogue.service import (
    NON_MAJOR_CATEGORIES,
    degree_subjects,
    get_major,
)


class MajorError(Exception):
    """A major change was refused. The message is safe to show to the student."""


def swap_blockers(conn, user_id, new_code):
    """Completed or enrolled subjects that count only in the current major, not in the new one."""
    new_subjects = {r["subject_code"] for r in conn.execute(
        "SELECT subject_code FROM major_subjects WHERE major_code = ?", (new_code,))}
    blockers = []
    for r in conn.execute(
        "SELECT e.subject_code, e.status, s.name, s.category FROM enrolments e"
        " JOIN subjects s ON s.code = e.subject_code WHERE e.user_id = ?"
        " ORDER BY e.subject_code",
        (user_id,),
    ):
        if r["category"] in NON_MAJOR_CATEGORIES or r["subject_code"] in new_subjects:
            continue
        blockers.append({"code": r["subject_code"], "name": r["name"], "status": r["status"]})
    return blockers


def preview(conn, user_id, major_code):
    """A major's structure plus what choosing it would mean for this student."""
    major = get_major(conn, major_code)
    if major is None:
        return None
    current = conn.execute("SELECT major_code FROM users WHERE id = ?", (user_id,)).fetchone()["major_code"]
    major["is_current"] = current == major_code
    major["has_current"] = current is not None
    major["blockers"] = swap_blockers(conn, user_id, major_code) if current and not major["is_current"] else []
    return major


def choose_major(conn, user_id, major_code):
    """Confirm a major (or swap to another one). Returns what changed."""
    major = get_major(conn, major_code)
    if major is None:
        raise MajorError("That major does not exist.")
    current = conn.execute("SELECT major_code FROM users WHERE id = ?", (user_id,)).fetchone()["major_code"]
    if current == major_code:
        raise MajorError(f"{major['name']} is already your major.")
    if current:
        blockers = swap_blockers(conn, user_id, major_code)
        if blockers:
            listed = ", ".join(f"{b['code']} {b['name']} ({b['status']})" for b in blockers)
            raise MajorError(
                f"You can't swap to {major['name']} yet: these only count in your current major: {listed}. "
                "Withdraw from the ones in progress first; completed subjects can't be undone."
            )

    conn.execute("UPDATE users SET major_code = ? WHERE id = ?", (major_code, user_id))
    # Plan items that are no longer part of the degree are dropped, so the plan stays valid.
    in_degree = {s["code"] for s in degree_subjects(conn, user_id) if s["in_degree"]}
    removed = 0
    for r in conn.execute("SELECT subject_code FROM planned_subjects WHERE user_id = ?", (user_id,)).fetchall():
        if r["subject_code"] not in in_degree:
            conn.execute("DELETE FROM planned_subjects WHERE user_id = ? AND subject_code = ?", (user_id, r["subject_code"]))
            removed += 1
    conn.commit()
    return {"major": major["name"], "swapped": current is not None, "plan_removed": removed}