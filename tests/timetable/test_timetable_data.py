import tempfile
from collections import Counter
from pathlib import Path

from shared import db


def rows(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM classes ORDER BY id")]


def test_every_subject_offered_in_a_season_has_one_lecture_and_three_tutorials(conn):
    offered = {
        (r["code"], season)
        for r in conn.execute("SELECT code, sessions_offered FROM subjects")
        for season in ("Autumn", "Spring")
        if r["sessions_offered"] in (season, "Both")
    }
    counts = Counter((c["subject_code"], c["season"], c["kind"]) for c in rows(conn))
    assert len(offered) == 63
    for code, season in offered:
        assert counts[(code, season, "lecture")] == 1, (code, season)
        assert counts[(code, season, "tutorial")] == 3, (code, season)


def test_there_are_no_classes_in_a_season_a_subject_is_not_offered(conn):
    spring_only = conn.execute("SELECT code FROM subjects WHERE sessions_offered = 'Spring'").fetchall()
    for r in spring_only:
        assert conn.execute(
            "SELECT COUNT(*) FROM classes WHERE subject_code = ? AND season = 'Autumn'", (r["code"],)
        ).fetchone()[0] == 0


def test_total_class_count(conn):
    assert len(rows(conn)) == 252  # 63 subject-seasons x (1 lecture + 3 tutorials)


def test_classes_are_on_weekdays_within_the_teaching_day(conn):
    for c in rows(conn):
        assert c["day"] in ("Mon", "Tue", "Wed", "Thu", "Fri")
        assert 9 <= c["start_hour"] and c["start_hour"] + c["duration"] <= 19


def test_lectures_are_two_hours_and_tutorials_one_hour(conn):
    for c in rows(conn):
        assert c["duration"] == (2 if c["kind"] == "lecture" else 1)


def test_tutorials_are_named_a_b_c(conn):
    names = {c["name"] for c in rows(conn) if c["kind"] == "tutorial"}
    assert names == {"Tutorial A", "Tutorial B", "Tutorial C"}


def test_every_class_has_a_room(conn):
    assert all(c["room"].startswith("Room ") for c in rows(conn))


def test_the_timetable_is_identical_every_time_the_database_is_built():
    def snapshot():
        path = Path(tempfile.mkdtemp()) / "t.db"
        db.build_database(str(path))
        connection = db.connect(str(path))
        try:
            return [(c["subject_code"], c["season"], c["name"], c["day"], c["start_hour"], c["room"]) for c in rows(connection)]
        finally:
            connection.close()

    assert snapshot() == snapshot()


def test_seeding_twice_does_not_duplicate_classes(conn):
    from timetable.seed import seed_timetable

    seed_timetable(conn)
    assert len(rows(conn)) == 252


def test_the_demo_students_lectures_do_not_clash(conn):
    from timetable.service import overlaps

    lectures = [dict(r) for r in conn.execute(
        "SELECT c.* FROM classes c JOIN enrolments e ON e.subject_code = c.subject_code"
        " WHERE e.user_id = 1 AND e.status = 'enrolled' AND c.kind = 'lecture' AND c.season = 'Autumn'"
    )]
    assert len(lectures) == 4
    assert not any(overlaps(a, b) for i, a in enumerate(lectures) for b in lectures[i + 1:])