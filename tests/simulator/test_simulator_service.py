import pytest

from accounts.service import create_user
from degree_planner.service import add_to_plan, get_plan, move_in_plan, plan_sessions, suggest_plan
from enrolment.results import attempts_for, failed_subjects
from enrolment.service import (
    EnrolmentError, current_session_of, enrol, evaluate_subjects, get_record, next_session, open_sessions, semester_number,
)
from majors.service import choose_major
from simulator.service import (
    SimulatorError, check_choices, complete_semester, current_state, parse_choices, reset_demo_student,
)
from submajors.service import choose_submajor
from timetable.service import get_timetable, valid_session
from transcript.service import transcript

AUTUMN, SPRING = "Autumn 2027", "Spring 2027"


@pytest.fixture()
def student(conn):
    user = create_user(conn, "new.student@student.uni.edu.au", "Str0ng#Pass", AUTUMN)["id"]
    choose_major(conn, user, "MAJ03519")
    choose_submajor(conn, user, "SMJ10156")
    return user


def p(code):
    return {code: {"result": "passed", "mark": None}}


def f(code):
    return {code: {"result": "failed", "mark": None}}


def n(code):
    return {code: {"result": "none", "mark": None}}


def info(conn, user, code):
    return evaluate_subjects(conn, user)["subjects"][code]


# --- the calendar --------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("label,expected", [("Autumn 2027", "Spring 2027"), ("Spring 2027", "Autumn 2028"), ("Spring 2030", "Autumn 2031")])
def test_the_next_session_alternates_autumn_and_spring(label, expected):
    assert next_session(label) == expected


def test_autumn_is_semester_one_and_spring_is_semester_two():
    assert semester_number("Autumn 2027") == 1 and semester_number("Spring 2027") == 2


def test_the_demo_student_starts_in_year_three_semester_one(conn):
    state = current_state(conn, 1)
    assert (state["label"], state["year"], state["semester"]) == (AUTUMN, 3, 1)
    assert (state["next"], state["next_year"], state["next_semester"]) == (SPRING, 3, 2)


def test_the_state_lists_the_subjects_enrolled_this_session(conn):
    assert [s["code"] for s in current_state(conn, 1)["subjects"]] == ["31272", "32144", "41026", "41040"]


# --- Complete Semester ------------------------------------------------------------------------------------------------------

def test_completing_a_semester_records_each_result_and_advances_the_session(conn):
    choices = {**p("41026"), **p("31272"), **f("32144"), **p("41040")}
    done = complete_semester(conn, 1, choices)
    assert (done["from"], done["to"], done["year"], done["semester"]) == (AUTUMN, SPRING, 3, 2)
    assert len(done["results"]) == 4 and done["no_result"] == []
    assert current_session_of(conn, 1) == SPRING
    outcomes = {a["subject_code"]: a["outcome"] for a in attempts_for(conn, 1) if a["session_label"] == AUTUMN}
    assert outcomes == {"41026": "passed", "31272": "passed", "32144": "failed", "41040": "passed"}


def test_the_spec_example_three_passes_and_one_fail(conn, student):
    for code in ("33130", "31265", "37181", "41039"):
        enrol(conn, student, code, AUTUMN)
    before = get_record(conn, student)["completed_cp"]
    done = complete_semester(conn, student, {**p("33130"), **p("31265"), **f("41039"), **p("37181")})
    assert get_record(conn, student)["completed_cp"] == before + 18  # three passes; the fail adds nothing
    assert set(failed_subjects(conn, student)) == {"41039"}
    assert done["to"] == SPRING and done["semester"] == 2
    assert current_session_of(conn, student) == SPRING


def test_marks_can_be_entered_and_drive_the_grade(conn):
    complete_semester(conn, 1, {**p("41026"), **{"31272": {"result": "passed", "mark": 91}}, **f("32144"), **{"41040": {"result": "failed", "mark": 12}}})
    rows = {a["subject_code"]: (a["mark"], a["grade"]) for a in attempts_for(conn, 1) if a["session_label"] == AUTUMN}
    assert rows["31272"] == (91, "HD") and rows["41040"] == (12, "FL")


# --- Skip: no result yet ---------------------------------------------------------------------------------------------------------

def test_skipping_creates_no_passes_or_fails(conn):
    before = attempts_for(conn, 1)
    done = complete_semester(conn, 1, {**n("41026"), **n("31272"), **n("32144"), **n("41040")})
    assert done["results"] == [] and len(done["no_result"]) == 4
    assert attempts_for(conn, 1) == before  # nothing was invented
    assert current_session_of(conn, 1) == SPRING


def test_a_subject_with_no_result_is_an_outstanding_requirement_again(conn):
    complete_semester(conn, 1, {**n("41026"), **p("31272"), **p("32144"), **p("41040")})
    assert info(conn, 1, "41026")["status"] in ("available", "blocked") and info(conn, 1, "41026")["retake"] is False
    assert conn.execute("SELECT COUNT(*) FROM enrolments WHERE user_id = 1 AND subject_code = '41026'").fetchone()[0] == 0


def test_leaving_everything_unselected_is_the_same_as_no_result(conn):
    done = complete_semester(conn, 1, {})
    assert len(done["no_result"]) == 4 and done["results"] == []


def test_skipping_with_nothing_enrolled_only_advances_the_session(conn, student):
    assert current_state(conn, student)["subjects"] == []
    done = complete_semester(conn, student, {})
    assert done["results"] == [] and done["no_result"] == [] and current_session_of(conn, student) == SPRING


def test_a_subject_enrolled_for_a_later_session_is_left_alone(conn, student):
    enrol(conn, student, "33130", AUTUMN)
    enrol(conn, student, "41039", SPRING)
    complete_semester(conn, student, p("33130"))
    assert conn.execute("SELECT status, session_label FROM enrolments WHERE user_id = ? AND subject_code = '41039'", (student,)).fetchone()[:] == ("enrolled", SPRING)
    assert [s["code"] for s in current_state(conn, student)["subjects"]] == ["41039"]  # it is this session now


# --- the whole app follows the new session ------------------------------------------------------------------------------------

def test_after_advancing_only_the_new_sessions_are_open_to_enrol(conn, student):
    assert open_sessions(current_session_of(conn, student)) == [AUTUMN, SPRING]
    complete_semester(conn, student, {})
    assert open_sessions(current_session_of(conn, student)) == [SPRING]
    with pytest.raises(EnrolmentError, match="You can only enrol in Spring 2027"):
        enrol(conn, student, "41039", AUTUMN)
    enrol(conn, student, "41039", SPRING)


def test_the_planning_window_moves_with_the_session(conn, student):
    assert get_plan(conn, student)["sessions"][0]["label"] == AUTUMN
    complete_semester(conn, student, {})
    assert get_plan(conn, student)["sessions"][0]["label"] == SPRING
    assert plan_sessions(SPRING)[0] == SPRING


def test_the_plan_reports_the_period(conn, student):
    assert get_plan(conn, student)["period"] == {"label": AUTUMN, "year": 1, "semester": 1}
    complete_semester(conn, student, {})
    assert get_plan(conn, student)["period"] == {"label": SPRING, "year": 1, "semester": 2}


def test_the_timetable_falls_back_to_the_students_own_session(conn, student):
    complete_semester(conn, student, {})
    assert valid_session("Autumn 2027", current_session_of(conn, student)) == SPRING
    assert get_timetable(conn, student, SPRING)["subjects"] == []


def test_a_planned_subject_for_a_session_that_has_passed_is_flagged_for_rescheduling_not_deleted(conn, student):
    add_to_plan(conn, student, "41039", AUTUMN)
    done = complete_semester(conn, student, {})
    assert done["plans_to_reschedule"] == 1
    assert conn.execute("SELECT COUNT(*) FROM planned_subjects WHERE user_id = ?", (student,)).fetchone()[0] == 1
    plan = get_plan(conn, student)
    assert [(i["code"], i["session"]) for i in plan["past_plans"]] == [("41039", AUTUMN)] and plan["counts"]["past"] == 1
    assert "has passed" in plan["past_plans"][0]["problem"] and plan["past_plans"][0]["move_sessions"]
    move_in_plan(conn, student, "41039", SPRING)  # the stranded subject can be rescheduled
    assert get_plan(conn, student)["past_plans"] == []


# --- your scenarios, driven through the simulator ----------------------------------------------------------------------------------

def test_scenario_a_a_failed_prerequisite_blocks_the_dependant(conn, student):
    enrol(conn, student, "41039", AUTUMN)
    add_to_plan(conn, student, "48024", SPRING)
    complete_semester(conn, student, f("41039"))
    assert current_session_of(conn, student) == SPRING
    assert info(conn, student, "41039")["retake"] is True
    assert "(failed: retake it first)" in info(conn, student, "48024")["note"]
    with pytest.raises(EnrolmentError, match=r"failed: retake it first"):
        enrol(conn, student, "48024", SPRING)
    planned = [i for s in get_plan(conn, student)["sessions"] for i in s["planned"] if i["code"] == "48024"]
    assert planned and "(failed: retake it first)" in planned[0]["problem"]  # kept, with the reason


def test_scenario_b_a_successful_retake_unlocks_the_dependant(conn, student):
    enrol(conn, student, "41039", AUTUMN)
    complete_semester(conn, student, f("41039"))
    enrol(conn, student, "41039", SPRING)  # the retake, in the new current session
    complete_semester(conn, student, p("41039"))
    assert current_session_of(conn, student) == "Autumn 2028"
    assert info(conn, student, "41039")["status"] == "completed" and info(conn, student, "41039")["retake"] is False
    assert info(conn, student, "48024")["status"] == "available"
    enrol(conn, student, "48024", "Autumn 2028")


def test_scenario_c_credit_points_count_once_across_simulated_semesters(conn, student):
    start = get_record(conn, student)["completed_cp"]
    enrol(conn, student, "41039", AUTUMN)
    complete_semester(conn, student, f("41039"))
    assert get_record(conn, student)["completed_cp"] == start
    enrol(conn, student, "41039", SPRING)
    complete_semester(conn, student, p("41039"))
    assert get_record(conn, student)["completed_cp"] == start + 6
    assert len([a for a in attempts_for(conn, student) if a["subject_code"] == "41039"]) == 2  # history kept
    plan = get_plan(conn, student)
    assert plan["completed_cp"] + plan["enrolled_cp"] + plan["planned_cp"] + plan["remaining_cp"] == 192


def test_scenario_d_a_retake_reaches_the_timetable_in_the_new_session(conn, student):
    enrol(conn, student, "41039", AUTUMN)
    complete_semester(conn, student, f("41039"))
    enrol(conn, student, "41039", SPRING)
    assert any(c["code"] == "41039" for c in get_timetable(conn, student, SPRING)["subjects"])


def test_scenario_e_failing_the_same_subject_more_than_once(conn, student):
    session = AUTUMN
    for _ in range(2):
        enrol(conn, student, "41039", current_session_of(conn, student))
        complete_semester(conn, student, f("41039"))
    enrol(conn, student, "41039", current_session_of(conn, student))
    complete_semester(conn, student, p("41039"))
    rows = [(a["attempt_number"], a["outcome"]) for a in attempts_for(conn, student) if a["subject_code"] == "41039"]
    assert rows == [(1, "failed"), (2, "failed"), (3, "passed")]
    assert info(conn, student, "41039")["status"] == "completed"
    assert transcript(conn, student)["passed_cp"] == 6 and session == AUTUMN


def test_progressing_through_several_years(conn, student):
    for _ in range(6):
        complete_semester(conn, student, {})
    state = current_state(conn, student)
    assert (state["label"], state["year"], state["semester"]) == ("Autumn 2030", 4, 1)


# --- checking what is submitted --------------------------------------------------------------------------------------------------------

def test_parse_choices_reads_results_and_marks():
    subjects = [{"code": "41026", "name": "A"}, {"code": "31272", "name": "B"}]
    form = {"result_41026": "passed", "mark_41026": " 72 ", "result_31272": "failed"}
    choices, errors = parse_choices(subjects, form.get)
    assert errors == [] and choices == {"41026": {"result": "passed", "mark": 72}, "31272": {"result": "failed", "mark": None}}


@pytest.mark.parametrize("value", ["abc", "-5", "55.5", "1e2"])
def test_parse_choices_rejects_a_mark_that_is_not_a_whole_number(value):
    choices, errors = parse_choices([{"code": "41026", "name": "A"}], {"result_41026": "passed", "mark_41026": value}.get)
    assert choices == {} and "whole number from 0 to 100" in errors[0]


def test_parse_choices_rejects_an_unknown_result():
    _, errors = parse_choices([{"code": "41026", "name": "A"}], {"result_41026": "excellent"}.get)
    assert "choose Passed, Failed or No result yet" in errors[0]


def test_a_mark_must_agree_with_the_result_and_nothing_is_saved(conn):
    before = attempts_for(conn, 1)
    with pytest.raises(SimulatorError, match="A mark of 40 is a fail"):
        complete_semester(conn, 1, {**p("41026"), "31272": {"result": "passed", "mark": 40}})
    assert attempts_for(conn, 1) == before and current_session_of(conn, 1) == AUTUMN


def test_a_mark_with_no_result_is_refused(conn):
    with pytest.raises(SimulatorError, match="a mark can't be entered when there is no result yet"):
        complete_semester(conn, 1, {"41026": {"result": "none", "mark": 60}})


def test_a_subject_that_is_not_enrolled_this_session_is_refused(conn):
    with pytest.raises(SimulatorError, match="not one of the subjects you are enrolled in"):
        complete_semester(conn, 1, p("41039"))  # John completed this long ago


def test_check_choices_lists_every_problem():
    subjects = [{"code": "41026", "name": "A"}]
    assert len(check_choices(subjects, {"41026": {"result": "failed", "mark": 90}, "99999": {"result": "passed", "mark": None}})) == 2


# --- all or nothing --------------------------------------------------------------------------------------------------------------------

def test_a_failure_part_way_through_saves_nothing_and_does_not_advance(conn, monkeypatch):
    import simulator.service as service

    calls = []
    real = service.record_result

    def flaky(*args, **kwargs):
        calls.append(args[2])
        if len(calls) == 3:
            raise RuntimeError("disk failure")
        return real(*args, **kwargs)

    monkeypatch.setattr(service, "record_result", flaky)
    before = (attempts_for(conn, 1), current_session_of(conn, 1))
    snapshot = conn.execute("SELECT subject_code, status FROM enrolments WHERE user_id = 1 ORDER BY subject_code").fetchall()
    with pytest.raises(RuntimeError):
        complete_semester(conn, 1, {**p("31272"), **p("32144"), **p("41026"), **p("41040")})
    assert (attempts_for(conn, 1), current_session_of(conn, 1)) == before
    assert conn.execute("SELECT subject_code, status FROM enrolments WHERE user_id = 1 ORDER BY subject_code").fetchall() == snapshot


def test_other_students_are_never_touched(conn, student):
    other = [dict(r) for r in conn.execute("SELECT * FROM subject_attempts WHERE user_id = ?", (student,))]
    complete_semester(conn, 1, {**p("41026"), **f("31272")})
    assert [dict(r) for r in conn.execute("SELECT * FROM subject_attempts WHERE user_id = ?", (student,))] == other
    assert current_session_of(conn, student) == AUTUMN


# --- reset ----------------------------------------------------------------------------------------------------------------------------------

def snapshot(conn, user=1):
    tables = ("subject_attempts", "enrolments", "planned_subjects", "class_choices")
    data = {t: sorted(tuple(r) for r in conn.execute(f"SELECT * FROM {t} WHERE user_id = ?", (user,))) for t in tables}  # noqa: S608
    data["user"] = tuple(conn.execute("SELECT current_session, major_code, submajor_code, general_electives FROM users WHERE id = ?", (user,)).fetchone())
    return {k: ([row[1:] for row in v] if k != "user" else v) for k, v in data.items()}  # ignore autoincrement ids


def test_reset_restores_the_original_state_after_several_semesters(conn):
    original = snapshot(conn)
    complete_semester(conn, 1, {**f("41026"), **p("31272"), **p("32144"), **p("41040")})
    enrol(conn, 1, "31265", SPRING)
    complete_semester(conn, 1, f("31265"))
    add_to_plan(conn, 1, "41052", "Spring 2028")
    assert snapshot(conn) != original
    reset_demo_student(conn)
    assert snapshot(conn) == original


def test_reset_is_repeatable_and_works_straight_away(conn):
    original = snapshot(conn)
    reset_demo_student(conn)
    reset_demo_student(conn)
    assert snapshot(conn) == original


def test_reset_puts_the_swapped_major_and_sub_major_back(conn):
    choose_major(conn, 1, "MAJ10053")
    choose_submajor(conn, 1, "SMJ10157")
    reset_demo_student(conn)
    assert tuple(conn.execute("SELECT major_code, submajor_code FROM users WHERE id = 1").fetchone()) == ("MAJ03519", "SMJ10156")


def test_reset_never_touches_other_accounts(conn, student):
    enrol(conn, student, "33130", AUTUMN)
    complete_semester(conn, student, f("33130"))
    other = snapshot(conn, student)
    complete_semester(conn, 1, {})
    reset_demo_student(conn)
    assert snapshot(conn, student) == other and current_session_of(conn, student) == SPRING


def test_the_transcript_matches_the_original_again_after_a_reset(conn):
    before = transcript(conn, 1)
    complete_semester(conn, 1, {**f("41026"), **f("31272"), **f("32144"), **f("41040")})
    reset_demo_student(conn)
    assert transcript(conn, 1) == before


def test_a_suggested_plan_replans_what_was_stranded_in_a_past_session(conn, student):
    add_to_plan(conn, student, "41039", AUTUMN)
    complete_semester(conn, student, {})
    suggest_plan(conn, student)
    plan = get_plan(conn, student)
    assert plan["past_plans"] == []  # re-planned from the new current session
    assert any(i["code"] == "41039" for s in plan["sessions"] for i in s["planned"])


def test_removing_a_stranded_plan_item_is_allowed(conn, student):
    from degree_planner.service import remove_from_plan

    add_to_plan(conn, student, "41039", AUTUMN)
    complete_semester(conn, student, {})
    remove_from_plan(conn, student, "41039")
    assert get_plan(conn, student)["past_plans"] == []
