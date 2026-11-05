import sqlite3

import pytest

from features.accounts.service import create_user
from features.degree_planner.service import add_to_plan
from features.enrolment.results import ResultError, attempts_for, default_mark, failed_subjects, grade_for, record_result
from features.enrolment.service import enrol, get_record
from features.majors.service import choose_major
from features.submajors.service import choose_submajor

AUTUMN = "Autumn 2027"


@pytest.fixture()
def student(conn):
    user = create_user(conn, "new.student@student.uni.edu.au", "Str0ng#Pass", AUTUMN)["id"]
    choose_major(conn, user, "MAJ03519")
    choose_submajor(conn, user, "SMJ10156")
    return user


def enrolments(conn, user):
    return {r["subject_code"]: r["status"] for r in conn.execute("SELECT subject_code, status FROM enrolments WHERE user_id = ?", (user,))}


def assert_consistent(conn, user):
    """The two tables never disagree: completed in enrolments <=> exactly one passed attempt; numbers are 1, 2, 3..."""
    passed = [r["subject_code"] for r in conn.execute("SELECT subject_code FROM subject_attempts WHERE user_id = ? AND outcome = 'passed'", (user,))]
    assert len(passed) == len(set(passed))  # a subject is passed at most once
    completed = {c for c, s in enrolments(conn, user).items() if s == "completed"}
    assert completed == set(passed)
    for code in {r["subject_code"] for r in conn.execute("SELECT subject_code FROM subject_attempts WHERE user_id = ?", (user,))}:
        numbers = [r[0] for r in conn.execute("SELECT attempt_number FROM subject_attempts WHERE user_id = ? AND subject_code = ? ORDER BY attempt_number", (user, code))]
        assert numbers == list(range(1, len(numbers) + 1))


# --- grades and marks -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("mark,grade", [(0, "FL"), (49, "FL"), (50, "P"), (64, "P"), (65, "C"), (74, "C"), (75, "D"), (84, "D"), (85, "HD"), (100, "HD")])
def test_grade_boundaries(mark, grade):
    assert grade_for(mark) == grade


def test_default_marks_are_plausible_and_repeatable():
    for code in ("41039", "48024", "33130"):
        for number in (1, 2, 3):
            assert 50 <= default_mark(2, code, number, "passed") <= 89
            assert 20 <= default_mark(2, code, number, "failed") <= 49
            assert default_mark(2, code, number, "passed") == default_mark(2, code, number, "passed")


# --- passing and failing -----------------------------------------------------------------------------------------------

def test_a_pass_makes_the_subject_completed_and_counts_its_credit_points(conn, student):
    enrol(conn, student, "41039", AUTUMN)
    before = get_record(conn, student)["completed_cp"]
    attempt = record_result(conn, student, "41039", AUTUMN, "passed", 72)
    assert attempt == {"subject_code": "41039", "attempt_number": 1, "outcome": "passed", "mark": 72, "grade": "C", "session_label": AUTUMN}
    assert enrolments(conn, student)["41039"] == "completed"
    assert get_record(conn, student)["completed_cp"] == before + 6
    assert_consistent(conn, student)


def test_a_pass_removes_the_subject_from_the_plan(conn, student):
    add_to_plan(conn, student, "41039", "Autumn 2027")
    record_result(conn, student, "41039", AUTUMN, "passed")
    assert conn.execute("SELECT COUNT(*) FROM planned_subjects WHERE user_id = ?", (student,)).fetchone()[0] == 0


def test_a_fail_counts_for_zero_credit_points_and_ends_the_enrolment(conn, student):
    enrol(conn, student, "41039", AUTUMN)
    before = get_record(conn, student)["completed_cp"]
    record_result(conn, student, "41039", AUTUMN, "failed", 41)
    assert "41039" not in enrolments(conn, student)  # an outstanding requirement again
    assert get_record(conn, student)["completed_cp"] == before
    assert attempts_for(conn, student)[0]["grade"] == "FL" and attempts_for(conn, student)[0]["outcome"] == "failed"
    assert_consistent(conn, student)


def test_a_failed_subject_needs_a_retake(conn, student):
    record_result(conn, student, "41039", AUTUMN, "failed", 30)
    assert failed_subjects(conn, student)["41039"]["failures"] == 1
    assert failed_subjects(conn, student)["41039"]["last_mark"] == 30


def test_a_fail_removes_the_class_choices(conn, student):
    enrol(conn, student, "41039", AUTUMN)
    cls = conn.execute("SELECT id, component FROM classes WHERE subject_code = '41039' AND component <> 'lecture' AND season = 'Autumn' LIMIT 1").fetchone()
    conn.execute("INSERT INTO class_choices (user_id, subject_code, component, class_id) VALUES (?, '41039', ?, ?)", (student, cls["component"], cls["id"]))
    conn.commit()
    record_result(conn, student, "41039", AUTUMN, "failed")
    assert conn.execute("SELECT COUNT(*) FROM class_choices WHERE user_id = ?", (student,)).fetchone()[0] == 0


def test_results_work_without_a_marks_being_given(conn, student):
    attempt = record_result(conn, student, "41039", AUTUMN, "failed")
    assert 20 <= attempt["mark"] <= 49 and attempt["grade"] == "FL"


# --- retakes: nothing is ever overwritten ----------------------------------------------------------------------------------

def test_a_retake_adds_an_attempt_and_keeps_the_old_one(conn, student):
    record_result(conn, student, "41039", AUTUMN, "failed", 40)
    enrol(conn, student, "41039", AUTUMN)
    record_result(conn, student, "41039", AUTUMN, "passed", 68)
    rows = attempts_for(conn, student)
    assert [(r["attempt_number"], r["outcome"], r["mark"]) for r in rows] == [(1, "failed", 40), (2, "passed", 68)]
    assert enrolments(conn, student)["41039"] == "completed"
    assert failed_subjects(conn, student) == {}  # no longer needs a retake
    assert_consistent(conn, student)


def test_credit_points_are_counted_exactly_once_however_many_attempts(conn, student):
    for _ in range(2):
        enrol(conn, student, "41039", AUTUMN)
        record_result(conn, student, "41039", AUTUMN, "failed")
    enrol(conn, student, "41039", AUTUMN)
    record_result(conn, student, "41039", AUTUMN, "passed")
    assert len(attempts_for(conn, student)) == 3
    assert get_record(conn, student)["completed_cp"] == 6


def test_the_attempts_are_numbered_in_order(conn, student):
    for outcome in ("failed", "failed", "passed"):
        record_result(conn, student, "41039", AUTUMN, outcome)
    assert [r["attempt_number"] for r in attempts_for(conn, student)] == [1, 2, 3]


def test_a_subject_cannot_be_passed_twice(conn, student):
    record_result(conn, student, "41039", AUTUMN, "passed")
    with pytest.raises(ResultError, match="already passed"):
        record_result(conn, student, "41039", AUTUMN, "passed")
    with pytest.raises(ResultError, match="already passed"):
        record_result(conn, student, "41039", AUTUMN, "failed")
    assert len(attempts_for(conn, student)) == 1


# --- checking what is asked -----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("outcome,mark", [("passed", 49), ("failed", 50), ("passed", 0), ("failed", 100)])
def test_a_mark_must_agree_with_the_result(conn, student, outcome, mark):
    with pytest.raises(ResultError, match=r"is a (pass|fail), not a"):
        record_result(conn, student, "41039", AUTUMN, outcome, mark)
    assert attempts_for(conn, student) == []


@pytest.mark.parametrize("mark", [-1, 101, 55.5, "70", True])
def test_a_mark_must_be_a_whole_number_from_0_to_100(conn, student, mark):
    with pytest.raises(ResultError, match="whole number from 0 to 100"):
        record_result(conn, student, "41039", AUTUMN, "passed", mark)


def test_an_unknown_outcome_or_subject_is_refused_and_nothing_is_written(conn, student):
    with pytest.raises(ResultError, match="passed or failed"):
        record_result(conn, student, "41039", AUTUMN, "excellent")
    with pytest.raises(ResultError, match="does not exist"):
        record_result(conn, student, "00000", AUTUMN, "passed")
    assert attempts_for(conn, student) == [] and "41039" not in enrolments(conn, student)


def test_a_failure_part_way_leaves_nothing_half_written(conn):
    with pytest.raises(sqlite3.IntegrityError):
        record_result(conn, 999, "41039", AUTUMN, "passed")  # there is no student 999
    assert conn.execute("SELECT COUNT(*) FROM subject_attempts WHERE user_id = 999").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM enrolments WHERE user_id = 999").fetchone()[0] == 0


# --- students are separate -----------------------------------------------------------------------------------------------

def test_one_students_results_never_touch_another(conn, student):
    before = attempts_for(conn, 1)
    record_result(conn, student, "41039", AUTUMN, "failed")
    assert attempts_for(conn, 1) == before and failed_subjects(conn, 1) == {}
    assert_consistent(conn, 1)


# --- the database itself --------------------------------------------------------------------------------------------------

def test_the_database_refuses_a_pass_with_a_failing_grade_or_the_reverse(conn, student):
    sql = ("INSERT INTO subject_attempts (user_id, subject_code, session_label, attempt_number, outcome, mark, grade)"
           " VALUES (?, '41039', 'Autumn 2027', 1, ?, ?, ?)")
    for outcome, mark, grade in [("passed", 70, "FL"), ("failed", 40, "P"), ("passed", 40, "P"), ("failed", 70, "FL")]:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(sql, (student, outcome, mark, grade))


def test_the_database_refuses_a_repeated_attempt_number_and_a_mark_over_100(conn, student):
    record_result(conn, student, "41039", AUTUMN, "failed")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO subject_attempts (user_id, subject_code, session_label, attempt_number, outcome, mark, grade) VALUES (?, '41039', 'Autumn 2027', 1, 'failed', 10, 'FL')", (student,))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO subject_attempts (user_id, subject_code, session_label, attempt_number, outcome, mark, grade) VALUES (?, '33130', 'Autumn 2027', 1, 'passed', 101, 'HD')", (student,))


# --- the seeded data ----------------------------------------------------------------------------------------------------------

def test_the_demo_students_completed_subjects_each_have_one_seeded_passed_attempt(conn):
    rows = attempts_for(conn, 1)
    assert len(rows) == 16 and all(r["outcome"] == "passed" and r["source"] == "seed" and r["attempt_number"] == 1 for r in rows)
    assert_consistent(conn, 1)


def test_the_seeded_results_are_plausible(conn):
    for r in attempts_for(conn, 1):
        assert 50 <= r["mark"] <= 89 and r["grade"] == grade_for(r["mark"])
