import pytest

from accounts.service import create_user
from enrolment.service import enrol, move_session, withdraw
from timetable import service
from timetable.service import TimetableError, choose_class, drop_class, get_timetable

AUTUMN, SPRING = "Autumn 2027", "Spring 2027"


@pytest.fixture()
def student(conn):
    return create_user(conn, "new.student@student.uni.edu.au", "Str0ng#Pass", AUTUMN)["id"]


def set_classes(conn, code, season, lecture, tutorials):
    """Replace a subject's generated classes with exact ones, so a test controls the times.

    lecture and each tutorial are (day, start_hour, duration). Returns the tutorial ids.
    """
    conn.execute("DELETE FROM class_choices WHERE subject_code = ?", (code,))
    conn.execute("DELETE FROM classes WHERE subject_code = ? AND season = ?", (code, season))
    if lecture:
        conn.execute(
            "INSERT INTO classes (subject_code, season, kind, name, day, start_hour, duration, room)"
            " VALUES (?, ?, 'lecture', 'Lecture', ?, ?, ?, 'Room T1')", (code, season, *lecture))
    ids = []
    for i, (day, start, duration) in enumerate(tutorials):
        cur = conn.execute(
            "INSERT INTO classes (subject_code, season, kind, name, day, start_hour, duration, room)"
            " VALUES (?, ?, 'tutorial', ?, ?, ?, ?, 'Room T2')", (code, season, f"Tutorial {'ABC'[i]}", day, start, duration))
        ids.append(cur.lastrowid)
    conn.commit()
    return ids


def chosen_rows(conn, user_id):
    return {r["subject_code"]: r["class_id"] for r in conn.execute(
        "SELECT subject_code, class_id FROM class_choices WHERE user_id = ?", (user_id,))}


@pytest.fixture()
def two_subjects(conn, student):
    """A new student enrolled in Programming 1 (A) and Mathematics 1 (B) for Autumn 2027."""
    enrol(conn, student, "41039", AUTUMN)
    enrol(conn, student, "33130", AUTUMN)
    return student


# --- reading -------------------------------------------------------------------------------------------

def test_the_demo_students_autumn_timetable_lists_each_subject_with_its_classes(conn):
    t = get_timetable(conn, 1, AUTUMN)
    assert [s["code"] for s in t["subjects"]] == ["31272", "32144", "41026", "41040"]
    assert all(s["lecture"] and len(s["options"]) == 3 for s in t["subjects"])
    assert t["needs_tutorial"] == ["31272", "32144", "41026", "41040"]
    assert t["clashes"] == []


def test_a_session_with_no_enrolments_is_empty(conn):
    t = get_timetable(conn, 1, SPRING)
    assert t["subjects"] == [] and t["clashes"] == []


def test_the_session_tabs_only_offer_open_sessions():
    assert service.valid_session("Spring 2027") == "Spring 2027"
    assert service.valid_session("Winter 2099") == "Autumn 2027"
    assert service.valid_session("") == "Autumn 2027"


# --- choosing (Create) and changing (Update) ------------------------------------------------------------

def test_choosing_a_tutorial_adds_it_to_the_timetable(conn):
    t = get_timetable(conn, 1, AUTUMN)
    option = next(o for o in t["subjects"][2]["options"] if not o["clash"])  # 41026
    result = choose_class(conn, 1, "41026", option["id"])
    assert result["label"] == "41026 Advanced Software Development" and result["updated"] is False
    assert chosen_rows(conn, 1) == {"41026": option["id"]}
    after = get_timetable(conn, 1, AUTUMN)
    assert after["subjects"][2]["chosen"]["id"] == option["id"]
    assert "41026" not in after["needs_tutorial"]


def test_choosing_again_changes_the_tutorial_and_keeps_one_row(conn, two_subjects):
    a, b, c = set_classes(conn, "41039", "Autumn", ("Mon", 9, 2), [("Tue", 9, 1), ("Wed", 9, 1), ("Thu", 9, 1)])
    choose_class(conn, two_subjects, "41039", a)
    result = choose_class(conn, two_subjects, "41039", b)
    assert result["updated"] is True
    assert chosen_rows(conn, two_subjects) == {"41039": b}


def test_a_replacement_tutorial_may_use_the_slot_of_the_one_it_replaces(conn, two_subjects):
    a, b, _ = set_classes(conn, "41039", "Autumn", ("Mon", 9, 2), [("Tue", 10, 1), ("Tue", 10, 1), ("Thu", 9, 1)])
    choose_class(conn, two_subjects, "41039", a)
    choose_class(conn, two_subjects, "41039", b)  # same time as the one it replaces: not a clash with itself
    assert chosen_rows(conn, two_subjects) == {"41039": b}


# --- clash detection -----------------------------------------------------------------------------------------

def test_a_tutorial_that_overlaps_another_subjects_lecture_is_refused(conn, two_subjects):
    set_classes(conn, "41039", "Autumn", ("Mon", 9, 2), [("Fri", 9, 1), ("Fri", 10, 1), ("Fri", 11, 1)])
    clash, _, _ = set_classes(conn, "33130", "Autumn", ("Thu", 15, 2), [("Mon", 10, 1), ("Mon", 11, 1), ("Tue", 10, 1)])
    with pytest.raises(TimetableError, match=r"clashes with 41039 lecture \(Mon 9:00-11:00\)"):
        choose_class(conn, two_subjects, "33130", clash)
    assert chosen_rows(conn, two_subjects) == {}


def test_classes_that_only_touch_do_not_clash(conn, two_subjects):
    set_classes(conn, "41039", "Autumn", ("Mon", 9, 2), [("Fri", 9, 1), ("Fri", 10, 1), ("Fri", 11, 1)])
    _, adjacent, other_day = set_classes(conn, "33130", "Autumn", ("Thu", 15, 2), [("Mon", 10, 1), ("Mon", 11, 1), ("Tue", 10, 1)])
    choose_class(conn, two_subjects, "33130", adjacent)  # starts at 11:00, the lecture ends at 11:00
    choose_class(conn, two_subjects, "33130", other_day)  # a different day entirely


def test_two_tutorials_cannot_overlap(conn, two_subjects):
    a, _, _ = set_classes(conn, "41039", "Autumn", ("Mon", 9, 2), [("Wed", 10, 1), ("Wed", 13, 1), ("Wed", 14, 1)])
    b, free, _ = set_classes(conn, "33130", "Autumn", ("Thu", 15, 2), [("Wed", 10, 1), ("Wed", 15, 1), ("Wed", 16, 1)])
    choose_class(conn, two_subjects, "41039", a)
    with pytest.raises(TimetableError, match=r"clashes with 41039 tutorial a \(Wed 10:00-11:00\)"):
        choose_class(conn, two_subjects, "33130", b)
    choose_class(conn, two_subjects, "33130", free)


def test_a_tutorial_cannot_overlap_its_own_lecture(conn, two_subjects):
    clash, _, _ = set_classes(conn, "41039", "Autumn", ("Mon", 9, 2), [("Mon", 10, 1), ("Tue", 9, 1), ("Wed", 9, 1)])
    with pytest.raises(TimetableError, match="clashes with 41039 lecture"):
        choose_class(conn, two_subjects, "41039", clash)


def test_the_timetable_marks_options_that_would_clash(conn, two_subjects):
    set_classes(conn, "41039", "Autumn", ("Mon", 9, 2), [("Fri", 9, 1), ("Fri", 10, 1), ("Fri", 11, 1)])
    set_classes(conn, "33130", "Autumn", ("Thu", 15, 2), [("Mon", 10, 1), ("Mon", 11, 1), ("Tue", 10, 1)])
    card = next(s for s in get_timetable(conn, two_subjects, AUTUMN)["subjects"] if s["code"] == "33130")
    assert [bool(o["clash"]) for o in card["options"]] == [True, False, False]
    assert "41039 lecture" in card["options"][0]["clash"]


def test_overlapping_lectures_are_shown_as_a_clash_not_blocked(conn, two_subjects):
    set_classes(conn, "41039", "Autumn", ("Mon", 9, 2), [("Fri", 9, 1), ("Fri", 10, 1), ("Fri", 11, 1)])
    set_classes(conn, "33130", "Autumn", ("Mon", 10, 2), [("Tue", 9, 1), ("Tue", 10, 1), ("Tue", 11, 1)])
    t = get_timetable(conn, two_subjects, AUTUMN)
    assert len(t["clashes"]) == 1
    assert "33130 lecture (Mon 10:00-12:00) clashes with 41039 lecture (Mon 9:00-11:00)" in t["clashes"][0] or "41039 lecture (Mon 9:00-11:00) clashes with 33130 lecture (Mon 10:00-12:00)" in t["clashes"][0]


# --- errors -----------------------------------------------------------------------------------------------------

def test_cannot_choose_for_a_subject_you_are_not_enrolled_in(conn):
    some_class = conn.execute("SELECT id FROM classes WHERE subject_code = '41052' AND kind = 'tutorial'").fetchone()["id"]
    with pytest.raises(TimetableError, match="not enrolled in 41052"):
        choose_class(conn, 1, "41052", some_class)


def test_cannot_choose_for_a_completed_subject(conn):
    cid = conn.execute("SELECT id FROM classes WHERE subject_code = '41039' AND kind = 'tutorial'").fetchone()["id"]
    with pytest.raises(TimetableError, match="not enrolled in 41039"):
        choose_class(conn, 1, "41039", cid)


def test_the_class_must_belong_to_the_subject(conn):
    other = conn.execute("SELECT id FROM classes WHERE subject_code = '32144' AND kind = 'tutorial' AND season = 'Autumn'").fetchone()["id"]
    with pytest.raises(TimetableError, match="does not belong to 41026"):
        choose_class(conn, 1, "41026", other)
    with pytest.raises(TimetableError, match="does not belong"):
        choose_class(conn, 1, "41026", 999999)


def test_lectures_cannot_be_chosen(conn):
    lecture = conn.execute("SELECT id FROM classes WHERE subject_code = '41026' AND kind = 'lecture' AND season = 'Autumn'").fetchone()["id"]
    with pytest.raises(TimetableError, match="Lectures are added automatically"):
        choose_class(conn, 1, "41026", lecture)


def test_the_tutorial_must_run_in_the_session_you_are_enrolled_for(conn, student):
    enrol(conn, student, "43030", AUTUMN)
    spring_tutorial = conn.execute("SELECT id FROM classes WHERE subject_code = '43030' AND kind = 'tutorial' AND season = 'Spring'").fetchone()["id"]
    with pytest.raises(TimetableError, match="runs in Spring, but you are enrolled in 43030 Professional Practice in Computing for Autumn 2027"):
        choose_class(conn, student, "43030", spring_tutorial)


# --- dropping (Delete) --------------------------------------------------------------------------------------------

def test_dropping_a_tutorial_removes_the_choice(conn):
    t = get_timetable(conn, 1, AUTUMN)
    option = next(o for o in t["subjects"][2]["options"] if not o["clash"])
    choose_class(conn, 1, "41026", option["id"])
    assert drop_class(conn, 1, "41026")["label"] == "41026 Advanced Software Development"
    assert chosen_rows(conn, 1) == {}
    assert "41026" in get_timetable(conn, 1, AUTUMN)["needs_tutorial"]


def test_cannot_drop_a_tutorial_you_have_not_chosen(conn):
    with pytest.raises(TimetableError, match="have not chosen a tutorial for 41026"):
        drop_class(conn, 1, "41026")


# --- staying in step with enrolment ---------------------------------------------------------------------------------

def test_withdrawing_removes_the_tutorial_choice(conn):
    option = next(o for o in get_timetable(conn, 1, AUTUMN)["subjects"][2]["options"] if not o["clash"])
    choose_class(conn, 1, "41026", option["id"])
    withdraw(conn, 1, "41026")
    assert chosen_rows(conn, 1) == {}


def test_moving_to_another_session_removes_the_tutorial_choice(conn, student):
    enrol(conn, student, "43030", AUTUMN)
    option = next(o for o in get_timetable(conn, student, AUTUMN)["subjects"][0]["options"] if not o["clash"])
    choose_class(conn, student, "43030", option["id"])
    move_session(conn, student, "43030", SPRING)
    assert chosen_rows(conn, student) == {}
    assert [s["code"] for s in get_timetable(conn, student, SPRING)["subjects"]] == ["43030"]


def test_students_have_separate_timetables(conn, student):
    enrol(conn, student, "41039", AUTUMN)
    option = next(o for o in get_timetable(conn, student, AUTUMN)["subjects"][0]["options"] if not o["clash"])
    choose_class(conn, student, "41039", option["id"])
    assert chosen_rows(conn, 1) == {}
    assert [s["code"] for s in get_timetable(conn, 1, AUTUMN)["subjects"]] == ["31272", "32144", "41026", "41040"]


def test_a_student_cannot_choose_for_a_subject_only_someone_else_is_enrolled_in(conn, student):
    cid = conn.execute("SELECT id FROM classes WHERE subject_code = '41026' AND kind = 'tutorial' AND season = 'Autumn'").fetchone()["id"]
    with pytest.raises(TimetableError, match="not enrolled in 41026"):  # the demo student is, this student is not
        choose_class(conn, student, "41026", cid)


# --- the weekly grid -------------------------------------------------------------------------------------------------

def test_the_grid_covers_eight_to_seven_on_five_days(conn):
    grid = get_timetable(conn, 1, AUTUMN)["grid"]
    assert [r["hour"] for r in grid] == list(range(8, 19))
    assert all(len(r["cells"]) == 5 for r in grid)


def test_a_two_hour_lecture_is_one_cell_spanning_two_rows(conn, student):
    enrol(conn, student, "41039", AUTUMN)
    set_classes(conn, "41039", "Autumn", ("Tue", 13, 2), [("Fri", 9, 1), ("Fri", 10, 1), ("Fri", 11, 1)])
    grid = get_timetable(conn, student, AUTUMN)["grid"]
    row13 = next(r for r in grid if r["hour"] == 13)
    row14 = next(r for r in grid if r["hour"] == 14)
    assert row13["cells"][1]["rowspan"] == 2 and row13["cells"][1]["item"]["kind"] == "lecture"
    assert row14["cells"][1] == {"skip": True}
    assert row13["cells"][0] is None  # nothing on Monday


def test_a_chosen_tutorial_appears_in_the_grid(conn, student):
    enrol(conn, student, "41039", AUTUMN)
    a, _, _ = set_classes(conn, "41039", "Autumn", ("Tue", 13, 2), [("Fri", 9, 1), ("Fri", 10, 1), ("Fri", 11, 1)])
    choose_class(conn, student, "41039", a)
    row9 = next(r for r in get_timetable(conn, student, AUTUMN)["grid"] if r["hour"] == 9)
    assert row9["cells"][4]["item"]["name"] == "Tutorial A"


def test_overlapping_items_never_share_a_grid_cell():
    rows, left_out = service.build_grid([
        {"subject_code": "A", "kind": "lecture", "day": "Mon", "start_hour": 9, "duration": 2, "name": "Lecture", "room": "R", "subject_name": "A"},
        {"subject_code": "B", "kind": "lecture", "day": "Mon", "start_hour": 10, "duration": 2, "name": "Lecture", "room": "R", "subject_name": "B"},
    ])
    assert [i["subject_code"] for i in left_out] == ["B"]
    placed = [c for r in rows for c in r["cells"] if c and "item" in c]
    assert len(placed) == 1