"""Generate the synthetic weekly class timetable.

INVENTED DATA. Every subject offered in a season gets one 2-hour lecture and three 1-hour
tutorials (A, B, C). Times and rooms follow a fixed pattern, so the timetable is identical
every time the database is built. Nothing here comes from a real university timetable.

Lectures are spread over 25 slots, so most subjects do not collide, but a few do. That is
deliberate: it gives clash detection something to find.
"""
DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri")
LECTURE_STARTS = (9, 11, 13, 15, 17)
SEASONS = ("Autumn", "Spring")
TUTORIAL_LETTERS = ("A", "B", "C")


def _room(n):
    return f"Room {chr(65 + n % 6)}{100 + (n * 7) % 40}"


def seed_timetable(conn):
    if conn.execute("SELECT COUNT(*) AS n FROM classes").fetchone()["n"]:
        return  # already generated
    subjects = conn.execute("SELECT code, sessions_offered FROM subjects ORDER BY code").fetchall()
    rows = []
    for season in SEASONS:
        offered = [s["code"] for s in subjects if s["sessions_offered"] in (season, "Both")]
        for i, code in enumerate(offered):
            rows.append((code, season, "lecture", "Lecture", DAYS[i % 5], LECTURE_STARTS[(i // 5) % 5], 2, _room(i)))
            for k, letter in enumerate(TUTORIAL_LETTERS):
                rows.append((
                    code, season, "tutorial", f"Tutorial {letter}",
                    DAYS[(i + 1 + 2 * k) % 5],
                    9 + (i * 3 + k * 4) % 9,  # 9 to 17, one hour long
                    1,
                    _room(i + k + 1),
                ))
    conn.executemany(
        "INSERT INTO classes (subject_code, season, kind, name, day, start_hour, duration, room)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )