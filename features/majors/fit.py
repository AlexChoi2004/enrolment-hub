"""Fit for my progress (majors): every major judged for THIS student, with the swap advisor's own rules.

Nothing here decides anything new. Each row is the advisor's verdict for swapping to that major (what carries over, what would stop
counting, the extra time, the projected graduation), so the numbers are exactly the numbers on each major's own swap page.
"""
from features.advisor.ranking import SORTS, row_of, sort_rows
from features.advisor.service import assess
from features.subject_catalogue.service import list_majors, user_major


def rank_majors(conn, user_id, sort="fit"):
    """Every major for this student. The student's own major is kept apart (it is not a swap); the rest are in the order asked for."""
    if sort not in SORTS:
        sort = "fit"
    mine = user_major(conn, user_id)
    current, others, counted = None, [], 0
    for major in list_majors(conn):
        advice = assess(conn, user_id, "major", major["code"])
        counted = advice["progress"]["counted_cp"]
        row = row_of(advice, major["code"], major["name"], bool(mine) and mine["code"] == major["code"])
        if row["is_current"]:
            current = row
        else:
            others.append(row)
    return {"sort": sort, "sorts": SORTS, "first_choice": mine is None, "counted_cp": counted, "current": current, "rows": sort_rows(others, sort)}
