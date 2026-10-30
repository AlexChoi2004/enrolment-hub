"""Timetable: the weekly classes for the sessions a student is enrolled in.

Every enrolled subject brings its lecture automatically. The student picks one tutorial per
subject. A choice is refused if it overlaps any lecture or other chosen tutorial in that session.
Lectures of two enrolled subjects can overlap (the invented timetable has a few such pairs);
that is not blocked, but it is detected and shown as a clash.
"""
from enrolment.service import CURRENT_SESSION, open_sessions

DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri")
FIRST_HOUR, LAST_HOUR = 8, 19  # the grid shows 8:00 up to 19:00


class TimetableError(Exception):
    """A class choice was refused. The message is safe to show to the student."""


def season_of(session_label):
    return session_label.split()[0]


def valid_session(label):
    """A session the timetable can show, falling back to the current one."""
    return label if label in open_sessions() else CURRENT_SESSION


def overlaps(a, b):
    return (
        a["day"] == b["day"]
        and a["start_hour"] < b["start_hour"] + b["duration"]
        and b["start_hour"] < a["start_hour"] + a["duration"]
    )


def when(c):
    return f"{c['day']} {c['start_hour']}:00-{c['start_hour'] + c['duration']}:00"


def describe(c):
    return f"{c['subject_code']} {c['name'].lower()} ({when(c)})"


# --- loading -----------------------------------------------------------------------------------

def _enrolled(conn, user_id, session_label):
    return [
        dict(r)
        for r in conn.execute(
            "SELECT s.code, s.name FROM enrolments e JOIN subjects s ON s.code = e.subject_code"
            " WHERE e.user_id = ? AND e.status = 'enrolled' AND e.session_label = ? ORDER BY s.code",
            (user_id, session_label),
        )
    ]


def _classes(conn, codes, season):
    by_subject = {c: {"lecture": None, "tutorials": []} for c in codes}
    for r in conn.execute("SELECT * FROM classes WHERE season = ? ORDER BY id", (season,)):
        row = dict(r)
        if row["subject_code"] not in by_subject:
            continue
        if row["kind"] == "lecture":
            by_subject[row["subject_code"]]["lecture"] = row
        else:
            by_subject[row["subject_code"]]["tutorials"].append(row)
    return by_subject


def _choices(conn, user_id, codes, season):
    chosen = {}
    for r in conn.execute(
        "SELECT cc.subject_code AS chosen_for, c.* FROM class_choices cc JOIN classes c ON c.id = cc.class_id"
        " WHERE cc.user_id = ? AND c.season = ?",
        (user_id, season),
    ):
        row = dict(r)
        subject = row.pop("chosen_for")
        if subject in codes:
            chosen[subject] = row
    return chosen


# --- the weekly grid -----------------------------------------------------------------------------

def build_grid(items):
    """Lay classes out as hour rows by day columns. Returns (rows, left_out).

    A class spanning two hours becomes a cell with rowspan 2, and the cell beneath it is marked
    as covered. A class that overlaps one already placed is left out (it shows up as a clash).
    """
    occupied = {day: {} for day in DAYS}
    placed = {}
    left_out = []
    for item in sorted(items, key=lambda c: (c["start_hour"], c["subject_code"], c["kind"])):
        hours = range(item["start_hour"], item["start_hour"] + item["duration"])
        if any(h in occupied[item["day"]] for h in hours):
            left_out.append(item)
            continue
        for h in hours:
            occupied[item["day"]][h] = item
        placed[(item["day"], item["start_hour"])] = item

    rows = []
    for hour in range(FIRST_HOUR, LAST_HOUR):
        cells = []
        for day in DAYS:
            item = placed.get((day, hour))
            if item:
                cells.append({"item": item, "rowspan": item["duration"]})
            elif hour in occupied[day]:
                cells.append({"skip": True})
            else:
                cells.append(None)
        rows.append({"hour": hour, "label": f"{hour}:00", "cells": cells})
    return rows, left_out


# --- reading (Read) --------------------------------------------------------------------------------

def get_timetable(conn, user_id, session_label):
    season = season_of(session_label)
    subjects = _enrolled(conn, user_id, session_label)
    codes = [s["code"] for s in subjects]
    catalogue = _classes(conn, codes, season)
    chosen = _choices(conn, user_id, codes, season)

    items = []
    for s in subjects:
        lecture = catalogue[s["code"]]["lecture"]
        if lecture:
            items.append({**lecture, "subject_name": s["name"]})
        if s["code"] in chosen:
            items.append({**chosen[s["code"]], "subject_name": s["name"]})

    cards = []
    for s in subjects:
        # A new tutorial may overlap anything except the tutorial it would replace.
        blockers = [i for i in items if not (i["subject_code"] == s["code"] and i["kind"] == "tutorial")]
        options = []
        for t in catalogue[s["code"]]["tutorials"]:
            clash = next((b for b in blockers if overlaps(t, b)), None)
            options.append({
                "id": t["id"], "name": t["name"], "when": when(t), "room": t["room"],
                "chosen": s["code"] in chosen and chosen[s["code"]]["id"] == t["id"],
                "clash": f"clashes with {describe(clash)}" if clash else None,
            })
        lecture = catalogue[s["code"]]["lecture"]
        cards.append({
            "code": s["code"], "name": s["name"],
            "lecture": {"when": when(lecture), "room": lecture["room"]} if lecture else None,
            "chosen": next((o for o in options if o["chosen"]), None),
            "options": options,
        })

    clashes = []
    for i, a in enumerate(items):
        for b in items[i + 1:]:
            if overlaps(a, b):
                clashes.append(f"{describe(a)} clashes with {describe(b)}.")
    rows, _left_out = build_grid(items)
    return {
        "label": session_label,
        "subjects": cards,
        "grid": rows,
        "days": DAYS,
        "clashes": clashes,
        "needs_tutorial": [c["code"] for c in cards if not c["chosen"]],
    }


# --- choosing and dropping a tutorial (Create, Update, Delete) ---------------------------------------------

def choose_class(conn, user_id, subject_code, class_id):
    """Pick (or change) the tutorial for a subject the student is enrolled in."""
    enrolment = conn.execute(
        "SELECT e.session_label, e.status, s.name FROM enrolments e JOIN subjects s ON s.code = e.subject_code"
        " WHERE e.user_id = ? AND e.subject_code = ?",
        (user_id, subject_code),
    ).fetchone()
    if enrolment is None or enrolment["status"] != "enrolled":
        raise TimetableError(f"You are not enrolled in {subject_code}, so there is no tutorial to choose.")
    label = f"{subject_code} {enrolment['name']}"
    session_label = enrolment["session_label"]

    row = conn.execute("SELECT * FROM classes WHERE id = ?", (class_id,)).fetchone()
    if row is None or row["subject_code"] != subject_code:
        raise TimetableError(f"That class does not belong to {label}.")
    if row["kind"] != "tutorial":
        raise TimetableError("Lectures are added automatically. Choose a tutorial.")
    if row["season"] != season_of(session_label):
        raise TimetableError(
            f"That tutorial runs in {row['season']}, but you are enrolled in {label} for {session_label}."
        )

    subjects = _enrolled(conn, user_id, session_label)
    codes = [s["code"] for s in subjects]
    catalogue = _classes(conn, codes, row["season"])
    chosen = _choices(conn, user_id, codes, row["season"])
    for s in subjects:
        if catalogue[s["code"]]["lecture"]:
            blockers = [catalogue[s["code"]]["lecture"]]
        else:
            blockers = []
        if s["code"] in chosen and s["code"] != subject_code:  # the tutorial being replaced is not a blocker
            blockers.append(chosen[s["code"]])
        for b in blockers:
            if overlaps(row, b):
                raise TimetableError(f"{row['name']} for {label} clashes with {describe(b)}.")

    existing = conn.execute(
        "SELECT id FROM class_choices WHERE user_id = ? AND subject_code = ?", (user_id, subject_code)
    ).fetchone()
    if existing:
        conn.execute("UPDATE class_choices SET class_id = ? WHERE id = ?", (class_id, existing["id"]))
    else:
        conn.execute(
            "INSERT INTO class_choices (user_id, subject_code, class_id) VALUES (?, ?, ?)",
            (user_id, subject_code, class_id),
        )
    conn.commit()
    return {"label": label, "session": session_label, "tutorial": f"{row['name']} ({when(row)})", "updated": bool(existing)}


def drop_class(conn, user_id, subject_code):
    row = conn.execute(
        "SELECT cc.id, e.session_label, s.name FROM class_choices cc"
        " JOIN enrolments e ON e.user_id = cc.user_id AND e.subject_code = cc.subject_code"
        " JOIN subjects s ON s.code = cc.subject_code"
        " WHERE cc.user_id = ? AND cc.subject_code = ?",
        (user_id, subject_code),
    ).fetchone()
    if row is None:
        raise TimetableError(f"You have not chosen a tutorial for {subject_code}.")
    conn.execute("DELETE FROM class_choices WHERE id = ?", (row["id"],))
    conn.commit()
    return {"label": f"{subject_code} {row['name']}", "session": row["session_label"]}