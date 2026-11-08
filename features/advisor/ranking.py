"""Ranking swap options for one student: the order and the shape of a row.

Shared by the major and sub-major "fit for my progress" pages. Nothing here decides anything new: each row is the swap advisor's own
answer for one option, and this module only puts the rows in order.
"""
TIER_ORDER = {"good": 0, "costs_time": 1, "think": 2}
SORTS = {"fit": "Best fit", "lost": "Fewest credit points lost", "graduation": "Earliest graduation", "name": "Name"}


def session_index(label):
    """A session's place in time: 'Autumn 2028' comes before 'Spring 2028'."""
    term, year = label.split()
    return int(year) * 2 + (0 if term == "Autumn" else 1)


def row_of(advice, code, name, is_current, note=None):
    return {
        "code": code, "name": name, "is_current": is_current, "tier": advice["tier"], "label": advice["label"], "why": advice["why"],
        "carried_cp": advice["carried_cp"], "lost_cp": advice["lost_cp"], "lost_subjects": len(advice["lost"]), "carry_percent": advice["carry_percent"],
        "extra_sessions": advice["extra_sessions"], "graduate": advice["graduate_after"], "note": note,
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
