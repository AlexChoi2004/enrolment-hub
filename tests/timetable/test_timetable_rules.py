import pytest

from accounts.service import create_user
from enrolment.service import enrol, move_session, withdraw
from timetable import service
from timetable.service import TimetableError, choose_class, drop_class, get_timetable, layout_days

AUTUMN, SPRING = "Autumn 2027", "Spring 2027"
LABELS = {"tutorial": "Tutorial", "tutorial2": "Tutorial 2", "workshop": "Workshop"}


@pytest.fixture()
def student(conn):
    return create_user(conn, "new.student@student.uni.edu.au", "Str0ng#Pass", AUTUMN)["id"]


def set_classes(conn, code, season, lecture, parts):
    """Replace a subject's generated classes with exact ones, so a test controls the times.

    lecture is (day, start, duration) or None; parts maps a component to its options as
    (day, start, duration) tuples. Returns {component: [class ids]}.
    """
    conn.execute("DELETE FROM class_choices WHERE subject_code = ?", (code,))
    conn.execute("DELETE FROM classes WHERE subject_code = ? AND season = ?", (code, season))
    if lecture:
        conn.execute(
            "INSERT INTO classes (subject_code, season, component, kind, name, day, start_hour, duration, room)"
            " VALUES (?, ?, 'lecture', 'lecture', 'Lecture', ?, ?, ?, 'Room T1')", (code, season, *lecture))
    ids = {}
    for component, options in parts.items():
        kind = "workshop" if component == "workshop" else "tutorial"
        ids[component] = []
        for i, (day, start, duration) in enumerate(options):
            cur = conn.execute(
                "INSERT INTO classes (subject_code, season, component, kind, name, day, start_hour, duration, room)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Room T2')",
                (code, season, component, kind, f"{LABELS[component]} {'ABCDEFGHIJ'[i]}", day, start, duration))
            ids[component].append(cur.lastrowid)
    conn.commit()
    return ids


def free_options(n=5):
    """n options on Friday afternoon, away from the lectures used below."""
    return [("Fri", 9 + i, 1) for i in range(n)]


def chosen_rows(conn, user_id):
    return {(r["subject_code"], r["component"]): r["class_id"] for r in conn.execute(
        "SELECT subject_code, component, class_id FROM class_choices WHERE user_id = ?", (user_id,))}


@pytest.fixture()
def two_subjects(conn, student):
    """A new student enrolled in Programming 1 (A) and Mathematics 1 (B) for Autumn 2027."""
    enrol(conn, student, "41039", AUTUMN)
    enrol(conn, student, "33130", AUTUMN)
    return student


def flagged(timetable):
    return {(i["subject_code"], i["name"]): i["clash"] for col in timetable["columns"] for i in col["items"]}


# --- reading -------------------------------------------------------------------------------------------

def test_the_demo_students_autumn_timetable_lists_each_subject_with_its_classes(conn):
    t = get_timetable(conn, 1, AUTUMN)
    assert [s["code"] for s in t["subjects"]] == ["31272", "32144", "41026", "41040"]
    for s in t["subjects"]:
        assert s["lecture"] and s["components"]
        assert all(5 <= len(c["options"]) <= 10 for c in s["components"])
    assert t["needs_choice"] and t["clashes"] == []


def test_each_subject_in_a_session_gets_its_own_colour(conn):
    t = get_timetable(conn, 1, AUTUMN)
    assert [s["colour"] for s in t["subjects"]] == [0, 1, 2, 3]


def test_the_lecture_and_chosen_classes_of_a_subject_share_its_colour(conn):
    t = get_timetable(conn, 1, AUTUMN)
    option = t["subjects"][0]["components"][0]["options"][0]
    choose_class(conn, 1, "31272", option["id"])
    after = get_timetable(conn, 1, AUTUMN)
    colours = {i["colour"] for col in after["columns"] for i in col["items"] if i["subject_code"] == "31272"}
    assert colours == {0}


def test_a_session_with_no_enrolments_is_empty(conn):
    t = get_timetable(conn, 1, SPRING)
    assert t["subjects"] == [] and t["clashes"] == [] and t["needs_choice"] == []


def test_the_session_tabs_only_offer_open_sessions():
    assert service.valid_session("Spring 2027") == "Spring 2027"
    assert service.valid_session("Winter 2099") == "Autumn 2027"
    assert service.valid_session("") == "Autumn 2027"


# --- choosing (Create) and changing (Update) ------------------------------------------------------------

def test_choosing_a_class_adds_it_to_the_timetable(conn, two_subjects):
    ids = set_classes(conn, "41039", "Autumn", ("Mon", 9, 2), {"tutorial": free_options()})
    result = choose_class(conn, two_subjects, "41039", ids["tutorial"][0])
    assert result["label"] == "41039 Programming 1" and result["updated"] is False and result["clashes"] == []
    assert chosen_rows(conn, two_subjects) == {("41039", "tutorial"): ids["tutorial"][0]}
    t = get_timetable(conn, two_subjects, AUTUMN)
    card = next(s for s in t["subjects"] if s["code"] == "41039")
    assert card["components"][0]["chosen"]["id"] == ids["tutorial"][0]
    assert "41039 Tutorial" not in t["needs_choice"]


def test_choosing_again_changes_the_class_and_keeps_one_row(conn, two_subjects):
    ids = set_classes(conn, "41039", "Autumn", ("Mon", 9, 2), {"tutorial": free_options()})
    choose_class(conn, two_subjects, "41039", ids["tutorial"][0])
    result = choose_class(conn, two_subjects, "41039", ids["tutorial"][1])
    assert result["updated"] is True
    assert chosen_rows(conn, two_subjects) == {("41039", "tutorial"): ids["tutorial"][1]}


def test_each_component_is_chosen_separately(conn, two_subjects):
    ids = set_classes(conn, "41039", "Autumn", ("Mon", 9, 2),
                      {"tutorial": free_options(5), "tutorial2": [("Thu", 9 + i, 1) for i in range(5)], "workshop": [("Wed", 9 + 2 * i, 2) for i in range(5)]})
    for component in ("tutorial", "tutorial2", "workshop"):
        choose_class(conn, two_subjects, "41039", ids[component][0])
    assert len(chosen_rows(conn, two_subjects)) == 3
    choose_class(conn, two_subjects, "41039", ids["workshop"][1])  # changing one leaves the others alone
    rows = chosen_rows(conn, two_subjects)
    assert rows[("41039", "workshop")] == ids["workshop"][1] and rows[("41039", "tutorial")] == ids["tutorial"][0]
    card = next(s for s in get_timetable(conn, two_subjects, AUTUMN)["subjects"] if s["code"] == "41039")
    assert [c["label"] for c in card["components"]] == ["Tutorial", "Tutorial 2", "Workshop"]


def test_a_replacement_may_use_the_slot_of_the_class_it_replaces(conn, two_subjects):
    ids = set_classes(conn, "41039", "Autumn", ("Mon", 9, 2), {"tutorial": [("Tue", 10, 1), ("Tue", 10, 1), ("Thu", 9, 1), ("Thu", 10, 1), ("Thu", 11, 1)]})
    choose_class(conn, two_subjects, "41039", ids["tutorial"][0])
    result = choose_class(conn, two_subjects, "41039", ids["tutorial"][1])  # same time as the one it replaces
    assert result["clashes"] == []


# --- clashes: allowed, reported and shown ---------------------------------------------------------------------

def clash_setup(conn):
    set_classes(conn, "41039", "Autumn", ("Mon", 9, 2), {"tutorial": free_options()})
    return set_classes(conn, "33130", "Autumn", ("Thu", 15, 2), {"tutorial": [("Mon", 10, 1), ("Mon", 11, 1), ("Tue", 10, 1), ("Tue", 11, 1), ("Wed", 10, 1)]})


def test_a_clashing_class_is_allowed_but_reported(conn, two_subjects):
    ids = clash_setup(conn)
    result = choose_class(conn, two_subjects, "33130", ids["tutorial"][0])  # Mon 10-11 overlaps the 41039 lecture
    assert result["clashes"] == ["41039 lecture (Mon 9:00-11:00)"]
    assert chosen_rows(conn, two_subjects) == {("33130", "tutorial"): ids["tutorial"][0]}


def test_both_overlapping_classes_are_flagged_in_the_timetable(conn, two_subjects):
    ids = clash_setup(conn)
    choose_class(conn, two_subjects, "33130", ids["tutorial"][0])
    t = get_timetable(conn, two_subjects, AUTUMN)
    marks = flagged(t)
    assert marks[("41039", "Lecture")] is True and marks[("33130", "Tutorial A")] is True
    assert marks[("33130", "Lecture")] is False
    assert len(t["clashes"]) == 1 and "33130 tutorial a (Mon 10:00-11:00)" in t["clashes"][0]


def test_fixing_a_clash_clears_it(conn, two_subjects):
    ids = clash_setup(conn)
    choose_class(conn, two_subjects, "33130", ids["tutorial"][0])
    choose_class(conn, two_subjects, "33130", ids["tutorial"][2])  # Tue 10-11
    t = get_timetable(conn, two_subjects, AUTUMN)
    assert t["clashes"] == [] and not any(flagged(t).values())


def test_classes_that_only_touch_or_are_on_other_days_do_not_clash(conn, two_subjects):
    ids = clash_setup(conn)
    assert choose_class(conn, two_subjects, "33130", ids["tutorial"][1])["clashes"] == []  # starts at 11:00, lecture ends at 11:00
    assert choose_class(conn, two_subjects, "33130", ids["tutorial"][2])["clashes"] == []  # another day


def test_two_chosen_classes_that_overlap_are_a_clash(conn, two_subjects):
    a = set_classes(conn, "41039", "Autumn", ("Mon", 9, 2), {"tutorial": [("Wed", 10, 1)] + free_options(4)})
    b = set_classes(conn, "33130", "Autumn", ("Thu", 15, 2), {"tutorial": [("Wed", 10, 1)] + [("Tue", 9 + i, 1) for i in range(4)]})
    choose_class(conn, two_subjects, "41039", a["tutorial"][0])
    result = choose_class(conn, two_subjects, "33130", b["tutorial"][0])
    assert result["clashes"] == ["41039 tutorial a (Wed 10:00-11:00)"]


def test_a_class_can_clash_with_its_own_subjects_lecture(conn, two_subjects):
    ids = set_classes(conn, "41039", "Autumn", ("Mon", 9, 2), {"tutorial": [("Mon", 10, 1)] + free_options(4)})
    assert choose_class(conn, two_subjects, "41039", ids["tutorial"][0])["clashes"] == ["41039 lecture (Mon 9:00-11:00)"]


def test_two_components_of_the_same_subject_can_clash_with_each_other(conn, two_subjects):
    ids = set_classes(conn, "41039", "Autumn", ("Mon", 9, 2),
                      {"tutorial": [("Fri", 9, 1)] + [("Thu", 9 + i, 1) for i in range(4)],
                       "workshop": [("Fri", 9, 2)] + [("Wed", 9 + 2 * i, 2) for i in range(4)]})
    choose_class(conn, two_subjects, "41039", ids["tutorial"][0])
    result = choose_class(conn, two_subjects, "41039", ids["workshop"][0])
    assert result["clashes"] == ["41039 tutorial a (Fri 9:00-10:00)"]


def test_options_that_would_clash_are_marked_but_not_blocked(conn, two_subjects):
    clash_setup(conn)
    card = next(s for s in get_timetable(conn, two_subjects, AUTUMN)["subjects"] if s["code"] == "33130")
    options = card["components"][0]["options"]
    assert [bool(o["clash"]) for o in options] == [True, False, False, False, False]
    assert options[0]["clash"] == "clashes with 41039 lecture (Mon 9:00-11:00)"


def test_overlapping_lectures_are_shown_as_a_clash(conn, two_subjects):
    set_classes(conn, "41039", "Autumn", ("Mon", 9, 2), {"tutorial": free_options()})
    set_classes(conn, "33130", "Autumn", ("Mon", 10, 2), {"tutorial": [("Tue", 9 + i, 1) for i in range(5)]})
    t = get_timetable(conn, two_subjects, AUTUMN)
    assert len(t["clashes"]) == 1
    assert all(flagged(t)[(code, "Lecture")] for code in ("41039", "33130"))


# --- errors -----------------------------------------------------------------------------------------------------

def test_cannot_choose_for_a_subject_you_are_not_enrolled_in(conn):
    some = conn.execute("SELECT id FROM classes WHERE subject_code = '41052' AND component != 'lecture'").fetchone()["id"]
    with pytest.raises(TimetableError, match="not enrolled in 41052"):
        choose_class(conn, 1, "41052", some)


def test_cannot_choose_for_a_completed_subject(conn):
    some = conn.execute("SELECT id FROM classes WHERE subject_code = '41039' AND component != 'lecture'").fetchone()["id"]
    with pytest.raises(TimetableError, match="not enrolled in 41039"):
        choose_class(conn, 1, "41039", some)


def test_the_class_must_belong_to_the_subject(conn):
    other = conn.execute("SELECT id FROM classes WHERE subject_code = '32144' AND season = 'Autumn' AND component != 'lecture'").fetchone()["id"]
    with pytest.raises(TimetableError, match="does not belong to 41026"):
        choose_class(conn, 1, "41026", other)
    with pytest.raises(TimetableError, match="does not belong"):
        choose_class(conn, 1, "41026", 999999)


def test_lectures_cannot_be_chosen(conn):
    lecture = conn.execute("SELECT id FROM classes WHERE subject_code = '41026' AND season = 'Autumn' AND component = 'lecture'").fetchone()["id"]
    with pytest.raises(TimetableError, match="Lectures are added automatically"):
        choose_class(conn, 1, "41026", lecture)


def test_the_class_must_run_in_the_session_you_are_enrolled_for(conn, student):
    enrol(conn, student, "43030", AUTUMN)
    spring = conn.execute("SELECT id FROM classes WHERE subject_code = '43030' AND season = 'Spring' AND component != 'lecture'").fetchone()["id"]
    with pytest.raises(TimetableError, match="runs in Spring, but you are enrolled in 43030 Professional Practice in Computing for Autumn 2027"):
        choose_class(conn, student, "43030", spring)


# --- dropping (Delete) --------------------------------------------------------------------------------------------

def test_dropping_removes_only_that_component(conn, two_subjects):
    ids = set_classes(conn, "41039", "Autumn", ("Mon", 9, 2), {"tutorial": free_options(), "workshop": [("Thu", 9 + 2 * i, 2) for i in range(5)]})
    choose_class(conn, two_subjects, "41039", ids["tutorial"][0])
    choose_class(conn, two_subjects, "41039", ids["workshop"][0])
    result = drop_class(conn, two_subjects, "41039", "workshop")
    assert result["label"] == "41039 Programming 1" and result["class"] == "Workshop"
    assert list(chosen_rows(conn, two_subjects)) == [("41039", "tutorial")]
    assert "41039 Workshop" in get_timetable(conn, two_subjects, AUTUMN)["needs_choice"]


def test_cannot_drop_a_class_you_have_not_chosen(conn):
    with pytest.raises(TimetableError, match="have not chosen that class for 41026"):
        drop_class(conn, 1, "41026", "tutorial")


# --- staying in step with enrolment ---------------------------------------------------------------------------------

def test_withdrawing_removes_the_choices(conn, two_subjects):
    ids = set_classes(conn, "41039", "Autumn", ("Mon", 9, 2), {"tutorial": free_options()})
    choose_class(conn, two_subjects, "41039", ids["tutorial"][0])
    withdraw(conn, two_subjects, "41039")
    assert chosen_rows(conn, two_subjects) == {}


def test_moving_to_another_session_removes_the_choices(conn, student):
    enrol(conn, student, "43030", AUTUMN)
    card = get_timetable(conn, student, AUTUMN)["subjects"][0]
    choose_class(conn, student, "43030", card["components"][0]["options"][0]["id"])
    move_session(conn, student, "43030", SPRING)
    assert chosen_rows(conn, student) == {}
    assert [s["code"] for s in get_timetable(conn, student, SPRING)["subjects"]] == ["43030"]


def test_students_have_separate_timetables(conn, student):
    enrol(conn, student, "41039", AUTUMN)
    card = get_timetable(conn, student, AUTUMN)["subjects"][0]
    choose_class(conn, student, "41039", card["components"][0]["options"][0]["id"])
    assert chosen_rows(conn, 1) == {}
    assert [s["code"] for s in get_timetable(conn, 1, AUTUMN)["subjects"]] == ["31272", "32144", "41026", "41040"]


def test_a_student_cannot_choose_for_a_subject_only_someone_else_is_enrolled_in(conn, student):
    cid = conn.execute("SELECT id FROM classes WHERE subject_code = '41026' AND season = 'Autumn' AND component != 'lecture'").fetchone()["id"]
    with pytest.raises(TimetableError, match="not enrolled in 41026"):
        choose_class(conn, student, "41026", cid)


# --- the weekly layout -------------------------------------------------------------------------------------------------

def block(code, day, start, duration, component="lecture", name="Lecture"):
    return {"subject_code": code, "subject_name": code, "component": component, "name": name, "room": "R",
            "day": day, "start_hour": start, "duration": duration, "colour": 0}


def by_code(columns, day):
    col = next(c for c in columns if c["day"] == day)
    return {i["subject_code"]: i for i in col["items"]}


def test_there_is_one_column_per_weekday_in_order():
    assert [c["day"] for c in layout_days([])] == ["Mon", "Tue", "Wed", "Thu", "Fri"]


def test_overlapping_classes_sit_side_by_side_and_are_flagged():
    cols = layout_days([block("A", "Mon", 9, 2), block("B", "Mon", 10, 2)])
    a, b = by_code(cols, "Mon")["A"], by_code(cols, "Mon")["B"]
    assert (a["lane"], a["lanes"], b["lane"], b["lanes"]) == (0, 2, 1, 2)
    assert a["clash"] and b["clash"]


def test_classes_that_only_touch_do_not_share_a_lane_or_clash():
    cols = layout_days([block("A", "Mon", 9, 2), block("B", "Mon", 11, 1)])
    a, b = by_code(cols, "Mon")["A"], by_code(cols, "Mon")["B"]
    assert (a["lane"], a["lanes"], b["lane"], b["lanes"]) == (0, 1, 0, 1)
    assert not a["clash"] and not b["clash"]


def test_a_chain_of_overlaps_reuses_lanes_and_flags_the_middle_class():
    cols = layout_days([block("A", "Mon", 9, 2), block("B", "Mon", 10, 2), block("C", "Mon", 11, 2)])
    items = by_code(cols, "Mon")
    assert (items["A"]["lane"], items["B"]["lane"], items["C"]["lane"]) == (0, 1, 0)
    assert all(i["lanes"] == 2 for i in items.values())
    assert items["A"]["clash"] and items["B"]["clash"] and items["C"]["clash"]  # C overlaps B


def test_three_classes_at_once_need_three_lanes():
    cols = layout_days([block("A", "Tue", 9, 2), block("B", "Tue", 9, 2), block("C", "Tue", 10, 1)])
    assert {i["lanes"] for i in by_code(cols, "Tue").values()} == {3}


def test_classes_on_different_days_never_clash():
    cols = layout_days([block("A", "Mon", 9, 2), block("B", "Tue", 9, 2)])
    assert not any(i["clash"] for c in cols for i in c["items"])


def test_the_timetable_columns_carry_lanes_for_real_data(conn, two_subjects):
    clash_setup(conn)
    ids = [r["id"] for r in conn.execute("SELECT id FROM classes WHERE subject_code = '33130' AND component = 'tutorial' ORDER BY id")]
    choose_class(conn, two_subjects, "33130", ids[0])
    monday = next(c for c in get_timetable(conn, two_subjects, AUTUMN)["columns"] if c["day"] == "Mon")
    assert {i["lanes"] for i in monday["items"]} == {2} and all(i["clash"] for i in monday["items"])