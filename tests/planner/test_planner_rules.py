import pytest

from accounts.service import create_user
from degree_planner import service
from degree_planner.service import PlanError, add_to_plan, clear_plan, get_plan, move_in_plan, remove_from_plan
from enrolment.service import enrol, evaluate_subjects, withdraw

AUTUMN_27, SPRING_27 = "Autumn 2027", "Spring 2027"


@pytest.fixture()
def student(conn):
    """A brand new student with nothing completed, enrolled or planned."""
    return create_user(conn, "new.student@student.uni.edu.au", "Str0ng#Pass", AUTUMN_27)["id"]


def planned(conn, user_id=1):
    return {
        r["subject_code"]: r["session_label"]
        for r in conn.execute("SELECT subject_code, session_label FROM planned_subjects WHERE user_id = ?", (user_id,))
    }


# --- the planning window ---------------------------------------------------------------------------

def test_the_window_starts_at_the_current_session_and_runs_five_years():
    sessions = service.plan_sessions()
    assert sessions[0] == "Autumn 2027" and sessions[1] == "Spring 2027"
    assert len(sessions) == 10 and sessions[-1] == "Spring 2031"


# --- adding (Create) -----------------------------------------------------------------------------------

def test_a_valid_subject_can_be_planned(conn):
    assert add_to_plan(conn, 1, "41052", "Spring 2028") == "41052 Advanced Algorithms"
    assert planned(conn) == {"41052": "Spring 2028"}


def test_planning_is_not_enrolling(conn):
    add_to_plan(conn, 1, "41052", "Spring 2028")
    assert evaluate_subjects(conn, 1)["subjects"]["41052"]["status"] == "available"
    assert conn.execute("SELECT 1 FROM enrolments WHERE user_id = 1 AND subject_code = '41052'").fetchone() is None


def test_unknown_subject_is_refused(conn):
    with pytest.raises(PlanError, match="does not exist"):
        add_to_plan(conn, 1, "99999", "Spring 2028")


def test_completed_and_enrolled_subjects_cannot_be_planned(conn):
    with pytest.raises(PlanError, match="already completed"):
        add_to_plan(conn, 1, "41039", "Spring 2028")
    with pytest.raises(PlanError, match="already enrolled"):
        add_to_plan(conn, 1, "41026", "Spring 2028")


def test_a_subject_cannot_be_planned_twice(conn):
    add_to_plan(conn, 1, "41052", "Spring 2028")
    with pytest.raises(PlanError, match="already planned for Spring 2028"):
        add_to_plan(conn, 1, "41052", "Spring 2029")


@pytest.mark.parametrize("session_label", ["", "Winter 2028", "Autumn 2026", "Spring 2040", "Autumn 2028; DROP"])
def test_only_sessions_in_the_window_are_accepted(conn, session_label):
    with pytest.raises(PlanError, match="Choose a session from Autumn 2027 to Spring 2031"):
        add_to_plan(conn, 1, "41052", session_label)


def test_the_subject_must_be_offered_in_that_session(conn, student):
    with pytest.raises(PlanError, match="is not offered in Spring 2028"):
        add_to_plan(conn, student, "31777", "Spring 2028")  # Autumn only


def test_a_session_cannot_go_over_24_credit_points(conn, student):
    for code in ["41039", "33130", "31271", "31265"]:
        add_to_plan(conn, student, code, "Autumn 2028")
    with pytest.raises(PlanError, match="Autumn 2028 would go over 24 credit points"):
        add_to_plan(conn, student, "37181", "Autumn 2028")


def test_enrolled_credit_points_count_towards_the_limit(conn):
    with pytest.raises(PlanError, match=r"Autumn 2027 would go over 24 credit points \(24 already enrolled or planned\)"):
        add_to_plan(conn, 1, "43030", AUTUMN_27)


# --- prerequisites ---------------------------------------------------------------------------------------

def test_prerequisites_must_be_completed_or_planned_earlier(conn, student):
    with pytest.raises(PlanError, match="Needs 41039 Programming 1 completed or planned in an earlier session"):
        add_to_plan(conn, student, "48024", AUTUMN_27)


def test_a_planned_prerequisite_in_an_earlier_session_is_enough(conn, student):
    add_to_plan(conn, student, "41039", AUTUMN_27)
    add_to_plan(conn, student, "48024", SPRING_27)
    assert planned(conn, student) == {"41039": AUTUMN_27, "48024": SPRING_27}


def test_the_same_session_is_not_enough(conn, student):
    add_to_plan(conn, student, "41039", "Autumn 2028")
    with pytest.raises(PlanError, match="Needs 41039"):
        add_to_plan(conn, student, "48024", "Autumn 2028")


def test_a_prerequisite_planned_later_is_not_enough(conn, student):
    add_to_plan(conn, student, "41039", "Autumn 2029")
    with pytest.raises(PlanError, match="Needs 41039"):
        add_to_plan(conn, student, "48024", "Spring 2028")


def test_an_enrolled_prerequisite_counts_from_the_next_session(conn):
    add_to_plan(conn, 1, "32931", SPRING_27)  # needs 32144, which the demo student is enrolled in for Autumn 2027


def test_an_enrolled_prerequisite_does_not_count_in_its_own_session(conn, student):
    conn.execute(
        "INSERT INTO enrolments (user_id, subject_code, status, session_label) VALUES (?, '41039', 'enrolled', ?)",
        (student, AUTUMN_27),
    )
    with pytest.raises(PlanError, match="Needs 41039"):
        add_to_plan(conn, student, "48024", AUTUMN_27)
    add_to_plan(conn, student, "48024", SPRING_27)


# --- electives -------------------------------------------------------------------------------------------

def test_a_finished_elective_requirement_cannot_be_exceeded(conn):
    with pytest.raises(PlanError, match=r"General electives requirement would be exceeded \(24 of 24"):
        add_to_plan(conn, 1, "SYN102", "Autumn 2028")  # an Autumn elective


def test_planned_electives_count_towards_the_requirement(conn):
    add_to_plan(conn, 1, "41052", "Spring 2028")  # the demo student is already enrolled in one major elective
    add_to_plan(conn, 1, "32113", "Spring 2028")
    with pytest.raises(PlanError, match="Major electives requirement would be exceeded"):
        add_to_plan(conn, 1, "31260", "Spring 2029")


def test_four_general_electives_can_be_planned_but_not_a_fifth(conn, student):
    for code in ["SYN101", "SYN103", "SYN106", "SYN109"]:
        add_to_plan(conn, student, code, "Spring 2028" if code != "SYN101" else "Autumn 2028")
    with pytest.raises(PlanError, match="General electives requirement would be exceeded"):
        add_to_plan(conn, student, "SYN111", "Spring 2029")


# --- moving (Update) ---------------------------------------------------------------------------------------

def test_a_planned_subject_can_move_to_another_session(conn):
    add_to_plan(conn, 1, "31260", "Spring 2028")
    assert move_in_plan(conn, 1, "31260", "Autumn 2028") == "31260 Fundamentals of Interaction Design"
    assert planned(conn) == {"31260": "Autumn 2028"}


def test_moving_to_the_same_session_is_refused(conn):
    add_to_plan(conn, 1, "31260", "Spring 2028")
    with pytest.raises(PlanError, match="already planned for Spring 2028"):
        move_in_plan(conn, 1, "31260", "Spring 2028")


def test_cannot_move_something_that_is_not_planned(conn):
    with pytest.raises(PlanError, match="not in your plan"):
        move_in_plan(conn, 1, "31260", "Autumn 2028")


def test_cannot_move_to_a_session_where_it_is_not_offered(conn):
    add_to_plan(conn, 1, "41052", "Spring 2028")
    with pytest.raises(PlanError, match="is not offered in Autumn 2028"):
        move_in_plan(conn, 1, "41052", "Autumn 2028")


def test_cannot_move_before_its_own_prerequisites(conn, student):
    add_to_plan(conn, student, "41039", AUTUMN_27)
    add_to_plan(conn, student, "48024", "Spring 2028")
    with pytest.raises(PlanError, match="Needs 41039"):
        move_in_plan(conn, student, "48024", AUTUMN_27)


def test_cannot_move_a_prerequisite_later_than_what_needs_it(conn, student):
    add_to_plan(conn, student, "41039", AUTUMN_27)
    add_to_plan(conn, student, "48024", SPRING_27)
    with pytest.raises(PlanError, match=r"Can't move 41039 Programming 1 to Spring 2027: 48024 Programming 2 is planned for Spring 2027 and needs"):
        move_in_plan(conn, student, "41039", SPRING_27)


def test_cannot_move_into_a_full_session(conn, student):
    for code in ["41039", "33130", "31271", "31265"]:
        add_to_plan(conn, student, code, "Autumn 2028")
    add_to_plan(conn, student, "37181", "Spring 2028")
    with pytest.raises(PlanError, match="Autumn 2028 would go over 24 credit points"):
        move_in_plan(conn, student, "37181", "Autumn 2028")


def test_moving_frees_room_in_the_old_session(conn, student):
    for code in ["41039", "33130", "31271", "31265"]:
        add_to_plan(conn, student, code, "Autumn 2028")
    move_in_plan(conn, student, "31265", "Spring 2028")
    add_to_plan(conn, student, "37181", "Autumn 2028")  # room again


# --- removing (Delete) -----------------------------------------------------------------------------------------

def test_a_planned_subject_can_be_removed(conn):
    add_to_plan(conn, 1, "41052", "Spring 2028")
    assert remove_from_plan(conn, 1, "41052") == "41052 Advanced Algorithms"
    assert planned(conn) == {}


def test_cannot_remove_something_that_is_not_planned(conn):
    with pytest.raises(PlanError, match="not in your plan"):
        remove_from_plan(conn, 1, "41052")


def test_cannot_remove_a_subject_that_something_planned_needs(conn, student):
    add_to_plan(conn, student, "41039", AUTUMN_27)
    add_to_plan(conn, student, "48024", SPRING_27)
    with pytest.raises(PlanError, match="48024 Programming 2 is planned for Spring 2027 and needs 41039"):
        remove_from_plan(conn, student, "41039")
    remove_from_plan(conn, student, "48024")
    remove_from_plan(conn, student, "41039")
    assert planned(conn, student) == {}


def test_clearing_only_removes_the_students_own_plan(conn, student):
    add_to_plan(conn, student, "41039", AUTUMN_27)
    add_to_plan(conn, 1, "41052", "Spring 2028")
    assert clear_plan(conn, student) == 1
    assert planned(conn, student) == {}
    assert planned(conn) == {"41052": "Spring 2028"}


# --- the plan and the rest of the app ---------------------------------------------------------------------------

def test_plans_are_private_to_each_student(conn, student):
    add_to_plan(conn, student, "41039", AUTUMN_27)
    assert get_plan(conn, 1)["planned_cp"] == 0
    assert get_plan(conn, student)["planned_cp"] == 6


def test_enrolling_in_a_planned_subject_removes_it_from_the_plan(conn):
    add_to_plan(conn, 1, "41052", "Spring 2028")
    enrol(conn, 1, "41052", SPRING_27)
    assert planned(conn) == {}
    assert evaluate_subjects(conn, 1)["subjects"]["41052"]["status"] == "enrolled"


def test_withdrawing_a_prerequisite_flags_the_plan(conn):
    add_to_plan(conn, 1, "32931", SPRING_27)
    assert get_plan(conn, 1)["problems"] == []
    withdraw(conn, 1, "32144")
    plan = get_plan(conn, 1)
    assert any("32931" in p and "Needs 32144" in p for p in plan["problems"])
    item = next(i for s in plan["sessions"] for i in s["planned"] if i["code"] == "32931")
    assert "Needs 32144" in item["problem"]


# --- reading the plan (Read) --------------------------------------------------------------------------------------

def test_the_plan_lists_ten_sessions_with_enrolled_subjects_in_place(conn):
    plan = get_plan(conn, 1)
    assert [s["label"] for s in plan["sessions"]] == service.plan_sessions()
    first = plan["sessions"][0]
    assert first["load_cp"] == 24
    assert sorted(e["code"] for e in first["enrolled"]) == ["31272", "32144", "41026", "41040"]


def test_totals_for_the_demo_student(conn):
    plan = get_plan(conn, 1)
    assert (plan["completed_cp"], plan["enrolled_cp"], plan["planned_cp"]) == (96, 24, 0)
    assert plan["remaining_cp"] == 72 and plan["degree_total_cp"] == 192
    assert plan["complete"] is False and plan["has_plan"] is False


def test_totals_always_add_up_to_the_degree(conn, student):
    add_to_plan(conn, student, "41039", AUTUMN_27)
    add_to_plan(conn, student, "SYN101", "Spring 2028")
    plan = get_plan(conn, student)
    assert plan["completed_cp"] + plan["enrolled_cp"] + plan["planned_cp"] + plan["remaining_cp"] == 192


def test_outstanding_required_subjects_for_the_demo_student(conn):
    codes = {o["code"] for o in get_plan(conn, 1)["outstanding"]}
    assert codes == {"31265", "37181", "41092", "41080", "43030", "41079", "32931", "31482", "41759"}


def test_each_outstanding_subject_lists_the_sessions_it_could_go_in(conn):
    outstanding = {o["code"]: o for o in get_plan(conn, 1)["outstanding"]}
    assert outstanding["32931"]["sessions"][0] == "Spring 2027"  # after the enrolled prerequisite
    assert all(s.startswith("Spring") for s in outstanding["32931"]["sessions"])
    assert "Autumn 2027" not in outstanding["31482"]["sessions"]  # Autumn 2027 is full
    assert outstanding["31482"]["sessions"][0] == "Autumn 2028"


def test_elective_needs_for_the_demo_student(conn):
    needs = get_plan(conn, 1)["elective_needs"]
    assert [n["label"] for n in needs] == ["Major electives"]
    assert needs[0]["need"] == 2
    codes = {c["code"] for c in needs[0]["candidates"]}
    assert "41052" in codes and "41040" not in codes  # 41040 is already enrolled


def test_elective_needs_for_a_new_student(conn, student):
    needs = {n["label"]: n["need"] for n in get_plan(conn, student)["elective_needs"]}
    assert needs == {"Major electives": 3, "General electives": 4}


def test_a_subject_whose_prerequisites_are_not_planned_has_no_sessions_yet(conn, student):
    candidates = {c["code"]: c for n in get_plan(conn, student)["elective_needs"] for c in n["candidates"]}
    assert candidates["41052"]["sessions"] == []  # needs 31251, which needs 48024, which needs 41039


def test_a_plan_with_too_many_electives_is_reported(conn):
    add_to_plan(conn, 1, "31260", "Spring 2028")
    enrol(conn, 1, "41052", SPRING_27)
    enrol(conn, 1, "32113", SPRING_27)  # now three major electives are enrolled, plus one planned
    assert any("more major electives" in p for p in get_plan(conn, 1)["problems"])