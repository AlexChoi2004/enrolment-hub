"""Choosing the 24 cp block of the degree: a sub-major OR general electives.

The two are alternatives (both are 24 cp in the handbook). A sub-major is a separate requirement from the 48 cp
major. Swapping is always allowed: what the student has already done is never deleted, but a subject that is not
part of the new choice (and not in the major) stops counting towards the degree. The preview says exactly what
would stop counting before anything changes.
"""
from features.enrolment.service import withdraw_in_progress
from features.subject_catalogue.service import (
    degree_subjects,
    get_submajor,
    user_major,
)


class SubmajorError(Exception):
    """A change was refused. The message is safe to show to the student."""


def _current(conn, user_id):
    row = conn.execute(
        "SELECT submajor_code, submajor_language, general_electives FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    return row["submajor_code"], row["submajor_language"], bool(row["general_electives"])


def _counted_codes(conn, user_id, code=None, language=None, electives=False, simulate=False):
    """Subjects that count towards the degree now, or as they would if this choice were made (nothing is saved)."""
    if simulate:
        conn.execute(
            "UPDATE users SET submajor_code = ?, submajor_language = ?, general_electives = ? WHERE id = ?",
            (code, language, 1 if electives else 0, user_id),
        )
    try:
        return {s["code"] for s in degree_subjects(conn, user_id) if s["in_degree"]}
    finally:
        if simulate:
            conn.rollback()


def impact(conn, user_id, code=None, language=None, electives=False):
    """What a choice would do: done subjects that stop counting, and plan items that go."""
    before = _counted_codes(conn, user_id)
    after = _counted_codes(conn, user_id, code, language, electives, simulate=True)
    records = conn.execute(
        "SELECT e.subject_code, e.status, s.name FROM enrolments e JOIN subjects s ON s.code = e.subject_code"
        " WHERE e.user_id = ? ORDER BY e.subject_code", (user_id,)
    ).fetchall()
    lost = [dict(r) for r in records if r["subject_code"] in before and r["subject_code"] not in after]
    planned = [r[0] for r in conn.execute("SELECT subject_code FROM planned_subjects WHERE user_id = ?", (user_id,))]
    return {"lost": lost, "plan_removed": sum(1 for p in planned if p not in after),
            "withdrawable": [l for l in lost if l["status"] == "enrolled"]}


def preview(conn, user_id, code, language=None):
    """A sub-major's structure plus what choosing it would mean for this student."""
    current_code, current_language, electives = _current(conn, user_id)
    sub = get_submajor(conn, code, language)
    if sub is None:
        return None
    major = user_major(conn, user_id)
    major_codes = {s["code"] for s in major["core"] + major["options"]} if major else set()
    for group in sub["all_groups"]:
        for subject in group["subjects"]:
            subject["overlaps_major"] = subject["code"] in major_codes  # counts once, in the major
    sub["overlap_count"] = len({s["code"] for g in sub["groups"] for s in g["subjects"] if s["overlaps_major"]})
    sub["is_current"] = current_code == code and (not sub["is_language"] or current_language == language)
    sub["has_current"] = current_code is not None or electives
    chosen_language = language if sub["is_language"] else None
    sub["impact"] = (
        impact(conn, user_id, code, chosen_language)
        if not sub["is_current"] and not (sub["is_language"] and language is None) else {"lost": [], "plan_removed": 0, "withdrawable": []}
    )
    return sub


def electives_preview(conn, user_id):
    """The general-electives alternative: the sample electives on offer plus what choosing them would mean."""
    _, _, electives = _current(conn, user_id)
    subjects = [
        dict(r) for r in conn.execute(
            "SELECT code, name, credit_points, sessions_offered FROM subjects WHERE category = 'general_elective'"
            " ORDER BY name COLLATE NOCASE"
        )
    ]
    has_other = _current(conn, user_id)[0] is not None
    return {
        "subjects": subjects, "required_cp": 24, "is_current": electives, "has_current": has_other,
        "impact": impact(conn, user_id, electives=True) if not electives else {"lost": [], "plan_removed": 0, "withdrawable": []},
    }


def _drop_plan_items_outside_the_degree(conn, user_id):
    in_degree = {s["code"] for s in degree_subjects(conn, user_id) if s["in_degree"]}
    removed = 0
    for r in conn.execute("SELECT subject_code FROM planned_subjects WHERE user_id = ?", (user_id,)).fetchall():
        if r["subject_code"] not in in_degree:
            conn.execute("DELETE FROM planned_subjects WHERE user_id = ? AND subject_code = ?", (user_id, r["subject_code"]))
            removed += 1
    return removed


def choose_submajor(conn, user_id, code, language=None, withdraw=False):
    """Confirm a sub-major (or swap to another one, or from general electives). Returns what changed."""
    sub = get_submajor(conn, code)
    if sub is None:
        raise SubmajorError("That sub-major does not exist.")
    if sub["is_language"]:
        if language not in {l["code"] for l in sub["languages"]}:
            raise SubmajorError("Choose one language program for this sub-major.")
    else:
        language = None
    current_code, current_language, electives = _current(conn, user_id)
    if current_code == code and current_language == language:
        raise SubmajorError(f"{sub['name']} is already your sub-major.")
    lost = impact(conn, user_id, code, language)

    conn.execute(
        "UPDATE users SET submajor_code = ?, submajor_language = ?, general_electives = 0 WHERE id = ?",
        (code, language, user_id),
    )
    conn.execute("DELETE FROM elective_credits WHERE user_id = ?", (user_id,))  # no electives block any more
    withdrawn = withdraw_in_progress(conn, user_id, [l["subject_code"] for l in lost["withdrawable"]]) if withdraw else 0
    removed = _drop_plan_items_outside_the_degree(conn, user_id)
    conn.commit()
    language_name = next((l["name"] for l in sub["languages"] if l["code"] == language), None)
    return {"submajor": sub["name"], "language": language_name, "swapped": current_code is not None or electives,
            "plan_removed": removed, "no_longer_counted": len(lost["lost"]) - withdrawn, "withdrawn": withdrawn}


def choose_electives(conn, user_id, withdraw=False, count_as_electives=()):
    """Take 24 cp of general electives instead of a sub-major. Nothing done is deleted."""
    current_code, _, electives = _current(conn, user_id)
    if electives:
        raise SubmajorError("General electives are already your choice for this part of the degree.")
    lost = impact(conn, user_id, electives=True)
    conn.execute(
        "UPDATE users SET submajor_code = NULL, submajor_language = NULL, general_electives = 1 WHERE id = ?", (user_id,)
    )
    counted = sum(
        conn.execute("INSERT OR IGNORE INTO elective_credits (user_id, subject_code) VALUES (?, ?)", (user_id, c)).rowcount
        for c in count_as_electives
    )
    withdrawn = withdraw_in_progress(conn, user_id, [l["subject_code"] for l in lost["withdrawable"]]) if withdraw else 0
    removed = _drop_plan_items_outside_the_degree(conn, user_id)
    conn.commit()
    return {"swapped": current_code is not None, "plan_removed": removed, "counted_as_electives": counted,
            "no_longer_counted": len(lost["lost"]) - withdrawn - counted, "withdrawn": withdrawn}
