"""Fit for my progress (sub-majors): every sub-major, and general electives, judged for THIS student by the swap advisor's rules."""
from features.advisor.ranking import SORTS, row_of, sort_rows
from features.advisor.service import assess
from features.subject_catalogue.service import list_submajors, user_submajor

ELECTIVES = "electives"
ELECTIVES_NAME = "General electives (no sub-major)"


def rank_submajors(conn, user_id, sort="fit"):
    """Every sub-major plus the general electives pathway. What the student already has is kept apart; the rest are in the order asked for."""
    if sort not in SORTS:
        sort = "fit"
    mine = user_submajor(conn, user_id)
    on_electives = bool(conn.execute("SELECT general_electives FROM users WHERE id = ?", (user_id,)).fetchone()[0])
    options = [(s["code"], s["name"], s["is_language"]) for s in list_submajors(conn)] + [(ELECTIVES, ELECTIVES_NAME, False)]
    current, others, counted = None, [], 0
    for code, name, is_language in options:
        advice = assess(conn, user_id, "electives") if code == ELECTIVES else assess(conn, user_id, "submajor", code)
        counted = advice["progress"]["counted_cp"]
        is_current = on_electives if code == ELECTIVES else bool(mine) and mine["code"] == code
        note = "The subjects depend on the language you choose." if is_language else None
        row = row_of(advice, code, name, is_current, note)
        if is_current:
            current = row
        else:
            others.append(row)
    return {"sort": sort, "sorts": SORTS, "first_choice": mine is None and not on_electives, "counted_cp": counted, "current": current, "rows": sort_rows(others, sort)}
