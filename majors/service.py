"""Choosing and swapping a major.

A student confirms one major. Their Subjects page, planner and enrolment rules then use that major's core and
option subjects. Swapping is always allowed: nothing the student has done is deleted, but a subject that is not in the
new major (or the sub-major) stops counting towards the degree. The preview says exactly what would stop counting,
and what carries over, before anything changes.
"""
from enrolment.service import withdraw_in_progress
from subject_catalogue.service import (
    degree_subjects,
    get_major,
)


class MajorError(Exception):
    """A major change was refused. The message is safe to show to the student."""


def _counted_codes(conn, user_id, major_code=None, simulate=False):
    """Subjects that count towards the degree now, or as they would if `major_code` were chosen (nothing is saved)."""
    if simulate:
        conn.execute("UPDATE users SET major_code = ? WHERE id = ?", (major_code, user_id))
    try:
        return {s["code"] for s in degree_subjects(conn, user_id) if s["in_degree"]}
    finally:
        if simulate:
            conn.rollback()


def impact(conn, user_id, new_code):
    """What choosing this major would do to what the student has done and planned."""
    before = _counted_codes(conn, user_id)
    after = _counted_codes(conn, user_id, new_code, simulate=True)
    new_subjects = {r["subject_code"] for r in conn.execute(
        "SELECT subject_code FROM major_subjects WHERE major_code = ?", (new_code,))}
    records = conn.execute(
        "SELECT e.subject_code, e.status, s.name FROM enrolments e JOIN subjects s ON s.code = e.subject_code"
        " WHERE e.user_id = ? ORDER BY e.subject_code", (user_id,)
    ).fetchall()
    lost = [dict(r) for r in records if r["subject_code"] in before and r["subject_code"] not in after]
    carried = [dict(r) for r in records if r["subject_code"] in new_subjects]
    planned = [r[0] for r in conn.execute("SELECT subject_code FROM planned_subjects WHERE user_id = ?", (user_id,))]
    return {"lost": lost, "carried": carried, "plan_removed": sum(1 for p in planned if p not in after),
            "withdrawable": [l for l in lost if l["status"] == "enrolled"]}  # in progress, so they can be withdrawn


def preview(conn, user_id, major_code):
    """A major's structure plus what choosing it would mean for this student."""
    major = get_major(conn, major_code)
    if major is None:
        return None
    current = conn.execute("SELECT major_code FROM users WHERE id = ?", (user_id,)).fetchone()["major_code"]
    major["is_current"] = current == major_code
    major["has_current"] = current is not None
    major["impact"] = (
        impact(conn, user_id, major_code) if not major["is_current"] else {"lost": [], "carried": [], "plan_removed": 0, "withdrawable": []}
    )
    return major


def choose_major(conn, user_id, major_code, withdraw=False):
    """Confirm a major (or swap to another one). Returns what changed.

    With withdraw=True the student is also withdrawn from in-progress subjects that stop counting.
    """
    major = get_major(conn, major_code)
    if major is None:
        raise MajorError("That major does not exist.")
    current = conn.execute("SELECT major_code FROM users WHERE id = ?", (user_id,)).fetchone()["major_code"]
    if current == major_code:
        raise MajorError(f"{major['name']} is already your major.")
    effect = impact(conn, user_id, major_code)

    conn.execute("UPDATE users SET major_code = ? WHERE id = ?", (major_code, user_id))
    withdrawn = withdraw_in_progress(conn, user_id, [l["subject_code"] for l in effect["withdrawable"]]) if withdraw else 0
    # Plan items that are no longer part of the degree are dropped, so the plan stays valid.
    in_degree = {s["code"] for s in degree_subjects(conn, user_id) if s["in_degree"]}
    removed = 0
    for r in conn.execute("SELECT subject_code FROM planned_subjects WHERE user_id = ?", (user_id,)).fetchall():
        if r["subject_code"] not in in_degree:
            conn.execute("DELETE FROM planned_subjects WHERE user_id = ? AND subject_code = ?", (user_id, r["subject_code"]))
            removed += 1
    conn.commit()
    return {"major": major["name"], "swapped": current is not None, "plan_removed": removed,
            "no_longer_counted": len(effect["lost"]) - withdrawn, "withdrawn": withdrawn, "carried": len(effect["carried"])}
