"""Timetable: the weekly classes for the sessions a student is enrolled in.

Every enrolled subject brings its lecture automatically. Depending on the subject, the student
then picks one class for each tutorial and workshop. Choosing a class that overlaps another is
allowed, but it is detected, warned about and drawn in red so it can be fixed.
"""
from enrolment.service import CURRENT_SESSION, open_sessions

DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri")
FIRST_HOUR, LAST_HOUR = 8, 19  # the grid shows 8:00 up to 19:00
COMPONENTS = ("tutorial", "tutorial2", "workshop")  # the parts a student chooses; lectures are automatic
COLOURS = 8  # each subject in a session gets its own colour, reused after this many


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


def component_label(name):
    """'Tutorial 2 C' -> 'Tutorial 2' (the class name without its option letter)."""
    return name.rsplit(" ", 1)[0]


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
    """{code: {"lecture": row or None, "components": {component: [option rows]}}}"""
    by_subject = {c: {"lecture": None, "components": {}} for c in codes}
    for r in conn.execute("SELECT * FROM classes WHERE season = ? ORDER BY id", (season,)):
        row = dict(r)
        if row["subject_code"] not in by_subject:
            continue
        if row["component"] == "lecture":
            by_subject[row["subject_code"]]["lecture"] = row
        else:
            by_subject[row["subject_code"]]["components"].setdefault(row["component"], []).append(row)
    return by_subject


def _choices(conn, user_id, codes, season):
    """{(code, component): chosen class row}"""
    chosen = {}
    for r in conn.execute(
        "SELECT cc.subject_code AS chosen_for, cc.component AS chosen_component, c.*"
        " FROM class_choices cc JOIN classes c ON c.id = cc.class_id"
        " WHERE cc.user_id = ? AND c.season = ?",
        (user_id, season),
    ):
        row = dict(r)
        subject, component = row.pop("chosen_for"), row.pop("chosen_component")
        if subject in codes:
            chosen[(subject, component)] = row
    return chosen


# --- the weekly layout -----------------------------------------------------------------------------

def layout_days(items):
    """Group classes by day and give each a lane, so overlapping classes sit side by side.

    Returns one column per weekday. Every item gets `lane` and `lanes` (how many lanes its
    cluster of overlapping classes needs) and `clash` (True if it overlaps any other class).
    """
    items = [dict(i) for i in items]
    for item in items:
        item["clash"] = any(other is not item and overlaps(item, other) for other in items)

    columns = []
    for day in DAYS:
        day_items = sorted(
            (i for i in items if i["day"] == day),
            key=lambda i: (i["start_hour"], i["subject_code"], i["component"]),
        )
        clusters, current, current_end = [], [], 0
        for item in day_items:
            if current and item["start_hour"] >= current_end:
                clusters.append(current)
                current, current_end = [], 0
            current.append(item)
            current_end = max(current_end, item["start_hour"] + item["duration"])
        if current:
            clusters.append(current)
        for cluster in clusters:
            lane_ends = []
            for item in cluster:
                end = item["start_hour"] + item["duration"]
                for lane, lane_end in enumerate(lane_ends):
                    if lane_end <= item["start_hour"]:
                        item["lane"], lane_ends[lane] = lane, end
                        break
                else:
                    item["lane"] = len(lane_ends)
                    lane_ends.append(end)
            for item in cluster:
                item["lanes"] = len(lane_ends)
        columns.append({"day": day, "items": day_items})
    return columns


# --- reading (Read) --------------------------------------------------------------------------------

def get_timetable(conn, user_id, session_label):
    season = season_of(session_label)
    subjects = _enrolled(conn, user_id, session_label)
    codes = [s["code"] for s in subjects]
    catalogue = _classes(conn, codes, season)
    chosen = _choices(conn, user_id, codes, season)

    items = []
    for index, s in enumerate(subjects):
        extra = {"subject_name": s["name"], "colour": index % COLOURS}
        if catalogue[s["code"]]["lecture"]:
            items.append({**catalogue[s["code"]]["lecture"], **extra})
        for component in COMPONENTS:
            if (s["code"], component) in chosen:
                items.append({**chosen[(s["code"], component)], **extra})

    cards, needs = [], []
    for index, s in enumerate(subjects):
        components = []
        for component in COMPONENTS:
            rows = catalogue[s["code"]]["components"].get(component)
            if not rows:
                continue
            # A new choice is compared with everything except the class it would replace.
            blockers = [i for i in items if not (i["subject_code"] == s["code"] and i["component"] == component)]
            options = []
            for r in rows:
                clash = next((b for b in blockers if overlaps(r, b)), None)
                options.append({
                    "id": r["id"], "name": r["name"], "when": when(r), "room": r["room"],
                    "chosen": (s["code"], component) in chosen and chosen[(s["code"], component)]["id"] == r["id"],
                    "clash": f"clashes with {describe(clash)}" if clash else None,
                })
            label = component_label(rows[0]["name"])
            picked = next((o for o in options if o["chosen"]), None)
            if not picked:
                needs.append(f"{s['code']} {label}")
            components.append({"component": component, "label": label, "chosen": picked, "options": options})
        lecture = catalogue[s["code"]]["lecture"]
        cards.append({
            "code": s["code"], "name": s["name"], "colour": index % COLOURS,
            "lecture": {"when": when(lecture), "room": lecture["room"]} if lecture else None,
            "components": components,
        })

    columns = layout_days(items)
    clashes = []
    for i, a in enumerate(items):
        for b in items[i + 1:]:
            if overlaps(a, b):
                clashes.append(f"{describe(a)} clashes with {describe(b)}.")
    return {
        "label": session_label,
        "subjects": cards,
        "columns": columns,
        "hours": [f"{h}:00" for h in range(FIRST_HOUR, LAST_HOUR)],
        "clashes": clashes,
        "needs_choice": needs,
    }


# --- choosing and dropping a class (Create, Update, Delete) -------------------------------------------------

def choose_class(conn, user_id, subject_code, class_id):
    """Pick (or change) the class for one tutorial or workshop of a subject the student is enrolled in.

    An overlap with another class is allowed: it comes back in `clashes` so it can be warned about.
    """
    enrolment = conn.execute(
        "SELECT e.session_label, e.status, s.name FROM enrolments e JOIN subjects s ON s.code = e.subject_code"
        " WHERE e.user_id = ? AND e.subject_code = ?",
        (user_id, subject_code),
    ).fetchone()
    if enrolment is None or enrolment["status"] != "enrolled":
        raise TimetableError(f"You are not enrolled in {subject_code}, so there is nothing to choose.")
    label = f"{subject_code} {enrolment['name']}"
    session_label = enrolment["session_label"]

    row = conn.execute("SELECT * FROM classes WHERE id = ?", (class_id,)).fetchone()
    if row is None or row["subject_code"] != subject_code:
        raise TimetableError(f"That class does not belong to {label}.")
    if row["component"] == "lecture":
        raise TimetableError("Lectures are added automatically. Choose a tutorial or workshop.")
    if row["season"] != season_of(session_label):
        raise TimetableError(
            f"That class runs in {row['season']}, but you are enrolled in {label} for {session_label}."
        )
    row = dict(row)

    subjects = _enrolled(conn, user_id, session_label)
    codes = [s["code"] for s in subjects]
    catalogue = _classes(conn, codes, row["season"])
    chosen = _choices(conn, user_id, codes, row["season"])
    others = [c["lecture"] for c in catalogue.values() if c["lecture"]]
    others += [r for key, r in chosen.items() if key != (subject_code, row["component"])]  # the one being replaced is not an "other"
    clashes = [describe(o) for o in others if overlaps(row, o)]

    existing = conn.execute(
        "SELECT id FROM class_choices WHERE user_id = ? AND subject_code = ? AND component = ?",
        (user_id, subject_code, row["component"]),
    ).fetchone()
    if existing:
        conn.execute("UPDATE class_choices SET class_id = ? WHERE id = ?", (class_id, existing["id"]))
    else:
        conn.execute(
            "INSERT INTO class_choices (user_id, subject_code, component, class_id) VALUES (?, ?, ?, ?)",
            (user_id, subject_code, row["component"], class_id),
        )
    conn.commit()
    return {
        "label": label,
        "session": session_label,
        "class": f"{row['name']} ({when(row)})",
        "updated": bool(existing),
        "clashes": clashes,
    }


def drop_class(conn, user_id, subject_code, component):
    row = conn.execute(
        "SELECT cc.id, e.session_label, s.name, c.name AS class_name FROM class_choices cc"
        " JOIN enrolments e ON e.user_id = cc.user_id AND e.subject_code = cc.subject_code"
        " JOIN subjects s ON s.code = cc.subject_code JOIN classes c ON c.id = cc.class_id"
        " WHERE cc.user_id = ? AND cc.subject_code = ? AND cc.component = ?",
        (user_id, subject_code, component),
    ).fetchone()
    if row is None:
        raise TimetableError(f"You have not chosen that class for {subject_code}.")
    conn.execute("DELETE FROM class_choices WHERE id = ?", (row["id"],))
    conn.commit()
    return {
        "label": f"{subject_code} {row['name']}",
        "session": row["session_label"],
        "class": component_label(row["class_name"]),
    }