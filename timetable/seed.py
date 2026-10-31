"""Generate the synthetic weekly class timetable.

INVENTED DATA. Nothing here comes from a real university timetable.

Each subject gets a random-looking but fixed pattern of classes:
  - 1 lecture + 1 tutorial                 (most common)
  - 1 lecture + 1 tutorial + 1 workshop
  - 1 lecture + 2 tutorials
  - 1 lecture + 1 workshop
The lecture is single and automatic. Every tutorial and workshop has between 5 and 10 time
options spread over the week, so a student can usually find one that avoids a clash.

Everything is driven by seeded random numbers, so the timetable is identical every time the
database is built.
"""
import random

DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri")
SEASONS = ("Autumn", "Spring")
LETTERS = "ABCDEFGHIJ"
MIN_OPTIONS, MAX_OPTIONS = 5, 10  # time options for each tutorial or workshop
FIRST_START, LAST_END = 9, 19  # classes run from 9:00 to 19:00

PATTERNS = (
    (("lecture", "tutorial"), 4),
    (("lecture", "tutorial", "workshop"), 3),
    (("lecture", "tutorial", "tutorial2"), 2),
    (("lecture", "workshop"), 1),
)
DURATIONS = {  # hours; every option of a component has the same length
    "lecture": (1, 1, 2, 2),
    "tutorial": (1, 1, 2),
    "tutorial2": (1, 1, 2),
    "workshop": (2, 3),
}
KINDS = {"lecture": "lecture", "tutorial": "tutorial", "tutorial2": "tutorial", "workshop": "workshop"}


def pattern_for(code):
    rng = random.Random(f"pattern-{code}")  # noqa: S311 (seeded on purpose: repeatable invented data, not security)
    return rng.choices([p for p, _ in PATTERNS], weights=[w for _, w in PATTERNS])[0]


def component_label(component, pattern):
    if component == "tutorial":
        return "Tutorial 1" if "tutorial2" in pattern else "Tutorial"
    return {"lecture": "Lecture", "tutorial2": "Tutorial 2", "workshop": "Workshop"}[component]


def _slots(duration):
    return [(d, h) for d in DAYS for h in range(FIRST_START, LAST_END - duration + 1)]


def _overlap(a, b):
    return a[0] == b[0] and a[1] < b[1] + b[2] and b[1] < a[1] + a[2]


def seed_timetable(conn):
    if conn.execute("SELECT COUNT(*) AS n FROM classes").fetchone()["n"]:
        return  # already generated
    subjects = conn.execute("SELECT code, sessions_offered FROM subjects ORDER BY code").fetchall()
    rows = []
    room_number = 0

    def room():
        nonlocal room_number
        room_number += 1
        return f"Room {chr(65 + room_number % 6)}{100 + (room_number * 7) % 40}"

    for season in SEASONS:
        offered = [s["code"] for s in subjects if s["sessions_offered"] in (season, "Both")]
        placed_lectures = []  # (day, start, duration), so lectures avoid each other where they can
        for code in offered:
            pattern = pattern_for(code)
            rng = random.Random(f"times-{code}-{season}")  # noqa: S311 (seeded on purpose: repeatable invented data, not security)

            duration = rng.choice(DURATIONS["lecture"])
            slots = _slots(duration)
            rng.shuffle(slots)
            day, start = next(
                (s for s in slots if not any(_overlap((*s, duration), p) for p in placed_lectures)),
                slots[0],
            )
            placed_lectures.append((day, start, duration))
            rows.append((code, season, "lecture", "lecture", "Lecture", day, start, duration, room()))

            for component in pattern[1:]:
                duration = rng.choice(DURATIONS[component])
                count = rng.randint(MIN_OPTIONS, MAX_OPTIONS)
                picks = sorted(rng.sample(_slots(duration), count), key=lambda s: (DAYS.index(s[0]), s[1]))
                label = component_label(component, pattern)
                for letter, (day, start) in zip(LETTERS, picks):
                    rows.append((code, season, component, KINDS[component], f"{label} {letter}", day, start, duration, room()))

    conn.executemany(
        "INSERT INTO classes (subject_code, season, component, kind, name, day, start_hour, duration, room)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )