import tempfile
from collections import Counter, defaultdict
from pathlib import Path

from shared import db
from timetable.seed import pattern_for

PATTERNS = {
    ("lecture", "tutorial"),
    ("lecture", "tutorial", "workshop"),
    ("lecture", "tutorial", "tutorial2"),
    ("lecture", "workshop"),
}


def rows(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM classes ORDER BY id")]


def components(conn):
    """{(code, season): {component: [rows]}}"""
    grouped = defaultdict(lambda: defaultdict(list))
    for c in rows(conn):
        grouped[(c["subject_code"], c["season"])][c["component"]].append(c)
    return grouped


def offered_pairs(conn):
    return {
        (r["code"], season)
        for r in conn.execute("SELECT code, sessions_offered FROM subjects")
        for season in ("Autumn", "Spring")
        if r["sessions_offered"] in (season, "Both")
    }


def test_every_subject_offered_in_a_season_has_exactly_one_lecture(conn):
    grouped = components(conn)
    assert set(grouped) == offered_pairs(conn)
    assert all(len(parts["lecture"]) == 1 for parts in grouped.values())


def test_each_subject_follows_one_of_the_four_patterns(conn):
    for (code, season), parts in components(conn).items():
        assert tuple(sorted(parts, key=["lecture", "tutorial", "tutorial2", "workshop"].index)) in PATTERNS, (code, season)


def test_a_subject_has_the_same_pattern_in_both_seasons(conn):
    patterns = defaultdict(set)
    for (code, _season), parts in components(conn).items():
        patterns[code].add(tuple(sorted(parts)))
    assert all(len(p) == 1 for p in patterns.values())


def test_all_four_patterns_are_used(conn):
    used = {pattern_for(r["code"]) for r in conn.execute("SELECT code FROM subjects")}
    assert used == PATTERNS


def test_every_tutorial_and_workshop_has_five_to_ten_options(conn):
    for (code, season), parts in components(conn).items():
        for component, options in parts.items():
            if component != "lecture":
                assert 5 <= len(options) <= 10, (code, season, component, len(options))


def test_the_number_of_options_varies_between_subjects(conn):
    sizes = {len(options) for parts in components(conn).values() for c, options in parts.items() if c != "lecture"}
    assert len(sizes) >= 4


def test_options_of_a_component_are_distinct_times_of_the_same_length(conn):
    for key, parts in components(conn).items():
        for component, options in parts.items():
            assert len({(o["day"], o["start_hour"]) for o in options}) == len(options), (key, component)
            assert len({o["duration"] for o in options}) == 1, (key, component)


def test_classes_are_on_weekdays_within_the_teaching_day(conn):
    for c in rows(conn):
        assert c["day"] in ("Mon", "Tue", "Wed", "Thu", "Fri")
        assert 9 <= c["start_hour"] and c["start_hour"] + c["duration"] <= 19


def test_class_lengths_suit_the_kind_of_class(conn):
    for c in rows(conn):
        allowed = {"lecture": (1, 2), "tutorial": (1, 2), "workshop": (2, 3)}[c["kind"]]
        assert c["duration"] in allowed, c


def test_kinds_match_components(conn):
    for c in rows(conn):
        expected = "tutorial" if c["component"] in ("tutorial", "tutorial2") else c["component"]
        assert c["kind"] == expected


def test_option_names_are_lettered_and_two_tutorials_are_numbered(conn):
    for (code, season), parts in components(conn).items():
        assert [o["name"] for o in parts["lecture"]] == ["Lecture"]
        if "tutorial2" in parts:
            assert parts["tutorial"][0]["name"] == "Tutorial 1 A" and parts["tutorial2"][0]["name"] == "Tutorial 2 A"
        elif "tutorial" in parts:
            assert parts["tutorial"][0]["name"] == "Tutorial A"
        if "workshop" in parts:
            assert parts["workshop"][0]["name"] == "Workshop A"


def test_there_are_no_classes_in_a_season_a_subject_is_not_offered(conn):
    for r in conn.execute("SELECT code FROM subjects WHERE sessions_offered = 'Spring'"):
        assert conn.execute("SELECT COUNT(*) FROM classes WHERE subject_code = ? AND season = 'Autumn'", (r["code"],)).fetchone()[0] == 0


def test_every_class_has_a_room(conn):
    assert all(c["room"].startswith("Room ") for c in rows(conn))


def test_lecture_clashes_between_subjects_are_rare(conn):
    from timetable.service import overlaps

    for season in ("Autumn", "Spring"):
        lectures = [c for c in rows(conn) if c["component"] == "lecture" and c["season"] == season]
        pairs = [(a, b) for i, a in enumerate(lectures) for b in lectures[i + 1:] if overlaps(a, b)]
        assert len(pairs) <= 6, (season, len(pairs))


def test_the_timetable_is_identical_every_time_the_database_is_built():
    def snapshot():
        path = Path(tempfile.mkdtemp()) / "t.db"
        db.build_database(str(path))
        connection = db.connect(str(path))
        try:
            return [(c["subject_code"], c["season"], c["component"], c["name"], c["day"], c["start_hour"], c["duration"], c["room"]) for c in rows(connection)]
        finally:
            connection.close()

    assert snapshot() == snapshot()


def test_seeding_twice_does_not_duplicate_classes(conn):
    from timetable.seed import seed_timetable

    before = len(rows(conn))
    seed_timetable(conn)
    assert len(rows(conn)) == before


def test_the_demo_students_lectures_do_not_clash(conn):
    from timetable.service import overlaps

    lectures = [dict(r) for r in conn.execute(
        "SELECT c.* FROM classes c JOIN enrolments e ON e.subject_code = c.subject_code"
        " WHERE e.user_id = 1 AND e.status = 'enrolled' AND c.component = 'lecture' AND c.season = 'Autumn'"
    )]
    assert len(lectures) == 4
    assert not any(overlaps(a, b) for i, a in enumerate(lectures) for b in lectures[i + 1:])