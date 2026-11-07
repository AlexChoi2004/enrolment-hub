"""Compare majors: every major judged for THIS student, with the swap advisor's own rules.

Nothing here decides anything new. Each row is the advisor's verdict for swapping to that major (what carries over, what would stop
counting, the extra time, the projected graduation), so the numbers on this page are exactly the numbers on each major's own swap page.
This module only runs the advisor once per major and puts the results in order.
"""
from features.advisor.service import assess
from features.subject_catalogue.service import list_majors, user_major

TIER_ORDER = {"good": 0, "costs_time": 1, "think": 2}
SORTS = {"fit": "Best fit", "lost": "Fewest credit points lost", "graduation": "Earliest graduation", "name": "Name"}


def session_index(label):
    """A session's place in time: 'Autumn 2028' comes before 'Spring 2028'."""
    term, year = label.split()
    return int(year) * 2 + (0 if term == "Autumn" else 1)


def row_of(advice, major, is_current):
    return {
        "code": major["code"], "name": major["name"], "is_current": is_current, "tier": advice["tier"], "label": advice["label"],
        "why": advice["why"], "carried_cp": advice["carried_cp"], "lost_cp": advice["lost_cp"], "lost_subjects": len(advice["lost"]),
        "carry_percent": advice["carry_percent"], "extra_sessions": advice["extra_sessions"], "graduate": advice["graduate_after"],
    }


def fit_key(row):
    return (TIER_ORDER[row["tier"]], row["lost_cp"], row["extra_sessions"], row["name"])


def sort_rows(rows, sort):
    keys = {
        "fit": fit_key,
        "lost": lambda r: (r["lost_cp"], r["extra_sessions"], r["name"]),
        "graduation": lambda r: (session_index(r["graduate"]), r["lost_cp"], r["name"]),
        "name": lambda r: r["name"],
    }
    return sorted(rows, key=keys[sort])


def compare_majors(conn, user_id, sort="fit"):
    """Every major for this student. The student's own major is kept apart (it is not a swap) and the rest are in the order asked for."""
    if sort not in SORTS:
        sort = "fit"
    mine = user_major(conn, user_id)
    current, others, counted = None, [], 0
    for major in list_majors(conn):
        advice = assess(conn, user_id, "major", major["code"])
        counted = advice["progress"]["counted_cp"]
        row = row_of(advice, major, bool(mine) and mine["code"] == major["code"])
        if row["is_current"]:
            current = row
        else:
            others.append(row)
    return {"sort": sort, "sorts": SORTS, "first_choice": mine is None, "counted_cp": counted, "current": current, "rows": sort_rows(others, sort)}
