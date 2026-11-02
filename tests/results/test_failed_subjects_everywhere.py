import re

import pytest

from accounts.service import create_user
from degree_planner.service import add_to_plan, get_plan
from enrolment.results import record_result
from enrolment.service import EnrolmentError, enrol, evaluate_subjects, get_record
from majors.service import choose_major
from submajors.service import choose_submajor
from subject_catalogue.service import Filters, attach_status, filter_by_status, list_subjects
from timetable.service import get_timetable

AUTUMN, SPRING = "Autumn 2027", "Spring 2027"
TOKEN = re.compile(r'name="csrf_token" value="([^"]+)"')


@pytest.fixture()
def student(conn):
    user = create_user(conn, "new.student@student.uni.edu.au", "Str0ng#Pass", AUTUMN)["id"]
    choose_major(conn, user, "MAJ03519")
    choose_submajor(conn, user, "SMJ10156")
    return user


@pytest.fixture()
def blocked_setup(conn, student):
    """Programming 1 is enrolled and Programming 2 (which needs it) is already planned for the next session."""
    enrol(conn, student, "41039", AUTUMN)
    add_to_plan(conn, student, "48024", SPRING)
    return student


def info(conn, user, code):
    return evaluate_subjects(conn, user)["subjects"][code]


# --- Scenario A: a failed prerequisite ---------------------------------------------------------------------------------------

def test_failing_a_prerequisite_flags_the_planned_dependant_with_a_reason_and_keeps_it(conn, blocked_setup):
    user = blocked_setup
    assert get_plan(conn, user)["counts"]["blocked"] == 0
    record_result(conn, user, "41039", AUTUMN, "failed", 38)
    plan = get_plan(conn, user)
    planned = [p for s in plan["sessions"] for p in s["planned"] if p["code"] == "48024"]
    assert planned and planned[0]["problem"].startswith("Needs 41039 Programming 1 (failed: retake it first)")
    assert plan["counts"]["blocked"] == 1  # flagged, not deleted
    assert conn.execute("SELECT COUNT(*) FROM planned_subjects WHERE user_id = ? AND subject_code = '48024'", (user,)).fetchone()[0] == 1


def test_the_failed_subject_can_be_added_back_to_the_plan(conn, blocked_setup):
    user = blocked_setup
    record_result(conn, user, "41039", AUTUMN, "failed")
    retake = [r for r in get_plan(conn, user)["retakes"] if r["code"] == "41039"][0]
    assert retake["stage"] == "needs" and retake["sessions"] and retake["attempts"] == 1
    add_to_plan(conn, user, "41039", retake["sessions"][0])
    assert [r for r in get_plan(conn, user)["retakes"] if r["code"] == "41039"][0]["stage"] == "planned"


def test_the_student_cannot_enrol_in_the_dependant_before_the_retake_is_passed(conn, blocked_setup):
    record_result(conn, blocked_setup, "41039", AUTUMN, "failed")
    assert info(conn, blocked_setup, "48024")["status"] == "blocked"
    with pytest.raises(EnrolmentError, match=r"Needs 41039 Programming 1 \(failed: retake it first\)"):
        enrol(conn, blocked_setup, "48024", SPRING)


def test_the_catalogue_says_the_dependant_is_ineligible_because_of_the_failed_subject(conn, blocked_setup):
    record_result(conn, blocked_setup, "41039", AUTUMN, "failed")
    assert "Needs 41039 Programming 1 (failed: retake it first)" in info(conn, blocked_setup, "48024")["note"]


# --- Scenario B: a successful retake ------------------------------------------------------------------------------------------

def test_passing_the_retake_makes_the_dependant_available_again(conn, blocked_setup):
    user = blocked_setup
    record_result(conn, user, "41039", AUTUMN, "failed")
    assert info(conn, user, "48024")["status"] == "blocked"
    enrol(conn, user, "41039", AUTUMN)  # the retake
    assert info(conn, user, "41039")["note"] == "In progress in Autumn 2027 (retake, attempt 2)"
    record_result(conn, user, "41039", AUTUMN, "passed", 66)
    assert info(conn, user, "41039")["status"] == "completed" and info(conn, user, "41039")["retake"] is False
    assert info(conn, user, "48024")["status"] in ("available",)
    assert get_plan(conn, user)["counts"]["blocked"] == 0


def test_a_planned_dependant_is_unblocked_once_the_retake_is_enrolled_or_planned_earlier(conn, blocked_setup):
    user = blocked_setup
    record_result(conn, user, "41039", AUTUMN, "failed")
    assert get_plan(conn, user)["counts"]["blocked"] == 1
    enrol(conn, user, "41039", AUTUMN)
    assert get_plan(conn, user)["counts"]["blocked"] == 0  # planning accepts a prerequisite enrolled in an earlier session


# --- Scenario C: credit points ---------------------------------------------------------------------------------------------------

def test_a_failed_subject_adds_zero_and_a_retake_pass_adds_exactly_one_subject(conn, student):
    start = get_record(conn, student)["completed_cp"]
    enrol(conn, student, "41039", AUTUMN)
    record_result(conn, student, "41039", AUTUMN, "failed")
    assert get_record(conn, student)["completed_cp"] == start
    enrol(conn, student, "41039", AUTUMN)
    record_result(conn, student, "41039", AUTUMN, "passed")
    assert get_record(conn, student)["completed_cp"] == start + 6
    assert conn.execute("SELECT COUNT(*) FROM subject_attempts WHERE user_id = ?", (student,)).fetchone()[0] == 2  # history kept


def test_the_degree_total_always_adds_up_to_192_through_fails_and_passes(conn, student):
    def total():
        plan = get_plan(conn, student)
        return plan["completed_cp"] + plan["enrolled_cp"] + plan["planned_cp"] + plan["remaining_cp"]

    assert total() == 192
    enrol(conn, student, "41039", AUTUMN)
    assert total() == 192
    record_result(conn, student, "41039", AUTUMN, "failed")
    assert total() == 192
    enrol(conn, student, "41039", AUTUMN)
    record_result(conn, student, "41039", AUTUMN, "passed")
    assert total() == 192


# --- Scenario D: the retake reaches the timetable --------------------------------------------------------------------------------

def test_a_retaken_subject_gets_a_class_and_appears_in_the_timetable(conn, student):
    enrol(conn, student, "41039", AUTUMN)
    record_result(conn, student, "41039", AUTUMN, "failed")
    assert all(card["code"] != "41039" for card in get_timetable(conn, student, AUTUMN)["subjects"])
    enrol(conn, student, "41039", AUTUMN)  # the same checks as any enrolment: prerequisites, session, room
    cards = get_timetable(conn, student, AUTUMN)["subjects"]
    assert any(card["code"] == "41039" for card in cards)


def test_a_retake_is_still_refused_when_the_session_is_full(conn, student):
    for code in ("33130", "31265", "37181", "31268"):
        enrol(conn, student, code, AUTUMN)
    with pytest.raises(EnrolmentError, match="is full"):
        enrol(conn, student, "41039", AUTUMN)  # 24 credit points already; a retake gets no special treatment


# --- Scenario E: several attempts -------------------------------------------------------------------------------------------------

def test_failing_twice_then_passing_keeps_every_attempt_and_completes_the_subject(conn, student):
    for outcome in ("failed", "failed", "passed"):
        enrol(conn, student, "41039", AUTUMN)
        record_result(conn, student, "41039", AUTUMN, outcome)
    rows = conn.execute("SELECT attempt_number, outcome FROM subject_attempts WHERE user_id = ? ORDER BY attempt_number", (student,)).fetchall()
    assert [(r[0], r[1]) for r in rows] == [(1, "failed"), (2, "failed"), (3, "passed")]
    assert info(conn, student, "41039")["status"] == "completed"
    assert get_plan(conn, student)["retakes"] == []


# --- the catalogue ----------------------------------------------------------------------------------------------------------------

def test_a_failed_subject_is_marked_for_retake_in_the_catalogue(conn, student):
    record_result(conn, student, "41039", AUTUMN, "failed", 33)
    entry = info(conn, student, "41039")
    assert entry["retake"] is True and entry["status"] == "available"
    assert entry["note"] == "Failed in Autumn 2027 (mark 33): retake needed"


def test_a_failed_subject_that_cannot_be_retaken_yet_says_both_things(conn, student):
    record_result(conn, student, "48024", AUTUMN, "failed", 30)  # Programming 2, and Programming 1 is not passed
    assert info(conn, student, "48024")["note"].startswith("Failed in Autumn 2027 (mark 30): retake needed · Needs 41039")


def test_the_retake_filter_lists_only_failed_subjects(conn, student):
    record_result(conn, student, "41039", AUTUMN, "failed")
    progress = evaluate_subjects(conn, student)
    subjects = attach_status(list_subjects(conn, Filters(), user_id=student), progress)
    assert [s["code"] for s in filter_by_status(subjects, "retake")] == ["41039"]


def test_a_passed_subject_is_not_a_retake(conn, student):
    record_result(conn, student, "41039", AUTUMN, "failed")
    record_result(conn, student, "41039", AUTUMN, "passed")
    assert info(conn, student, "41039")["retake"] is False


def test_an_ordinary_subject_has_no_retake_flag(conn, student):
    assert info(conn, student, "33130")["retake"] is False and info(conn, student, "33130")["attempts"] == 0


# --- the pages ---------------------------------------------------------------------------------------------------------------------

def login(client, email, password):
    token = TOKEN.search(client.get("/login").get_data(as_text=True)).group(1)
    client.post("/login", data={"email": email, "password": password, "csrf_token": token})


@pytest.fixture()
def failed_client(app, client):
    from shared import db

    conn = db.connect(app.config["DATABASE"])
    user = create_user(conn, "failed.student@student.uni.edu.au", "Str0ng#Pass", AUTUMN)["id"]
    choose_major(conn, user, "MAJ03519")
    choose_submajor(conn, user, "SMJ10156")
    enrol(conn, user, "41039", AUTUMN)
    add_to_plan(conn, user, "48024", SPRING)
    record_result(conn, user, "41039", AUTUMN, "failed", 35)
    conn.close()
    login(client, "failed.student@student.uni.edu.au", "Str0ng#Pass")
    return client


def test_the_subjects_page_shows_the_retake_badge_and_filter(failed_client):
    page = failed_client.get("/subjects").get_data(as_text=True)
    assert "Failed: retake needed" in page and 'value="retake"' in page
    only = failed_client.get("/subjects?status=retake").get_data(as_text=True)
    assert "1 subject" in only and "Programming 1" in only


def test_the_planner_shows_the_failed_subject_and_the_blocked_dependant(failed_client):
    page = failed_client.get("/planner").get_data(as_text=True)
    assert "Failed, retake needed 1" in page and "Planned but blocked 1" in page
    assert "Add retake to plan" in page and "41039 Programming 1" in page
    assert "(failed: retake it first)" in page  # the reason the planned subject is blocked
