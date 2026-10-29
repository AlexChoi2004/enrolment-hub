import pytest

from accounts.service import create_user
from enrolment.service import (
    EnrolmentError,
    enrol,
    evaluate_subjects,
    move_session,
    open_sessions,
    withdraw,
)

AUTUMN = "Autumn 2027"
SPRING = "Spring 2027"


def rows(conn, user_id=1):
    return {
        r["subject_code"]: (r["status"], r["session_label"])
        for r in conn.execute("SELECT subject_code, status, session_label FROM enrolments WHERE user_id = ?", (user_id,))
    }


@pytest.fixture()
def student(conn):
    """A brand new student with nothing enrolled."""
    return create_user(conn, "new.student@student.uni.edu.au", "Str0ng#Pass", AUTUMN)["id"]


# --- the open sessions -----------------------------------------------------------------------

def test_from_autumn_a_student_can_plan_autumn_and_spring():
    assert open_sessions("Autumn 2027") == ["Autumn 2027", "Spring 2027"]


def test_from_spring_only_spring_is_open():
    assert open_sessions("Spring 2027") == ["Spring 2027"]


# --- enrolling (Create) --------------------------------------------------------------------------

def test_demo_student_can_enrol_in_a_spring_subject(conn):
    label = enrol(conn, 1, "41052", SPRING)  # Advanced Algorithms
    assert label == "41052 Advanced Algorithms"
    assert rows(conn)["41052"] == ("enrolled", SPRING)
    assert evaluate_subjects(conn, 1)["subjects"]["41052"]["status"] == "enrolled"


def test_new_student_can_enrol_in_a_subject_with_no_prerequisites(conn, student):
    enrol(conn, student, "41039", AUTUMN)
    assert rows(conn, student) == {"41039": ("enrolled", AUTUMN)}


def test_enrolment_is_recorded_for_the_right_student_only(conn, student):
    enrol(conn, student, "43030", AUTUMN)
    assert "43030" in rows(conn, student)
    assert "43030" not in rows(conn, 1)  # the demo student's record is untouched


def test_prerequisites_must_be_completed_first(conn, student):
    with pytest.raises(EnrolmentError, match="Needs 41039 Programming 1"):
        enrol(conn, student, "48024", SPRING)
    assert rows(conn, student) == {}


def test_being_enrolled_in_a_prerequisite_is_not_enough(conn, student):
    enrol(conn, student, "41039", AUTUMN)
    with pytest.raises(EnrolmentError, match="Needs 41039 Programming 1"):
        enrol(conn, student, "48024", SPRING)


def test_completing_the_prerequisite_unlocks_the_next_subject(conn, student):
    conn.execute(
        "INSERT INTO enrolments (user_id, subject_code, status, session_label)"
        " VALUES (?, '41039', 'completed', 'Autumn 2026')",
        (student,),
    )
    enrol(conn, student, "48024", SPRING)
    assert rows(conn, student)["48024"] == ("enrolled", SPRING)


def test_cannot_enrol_twice(conn, student):
    enrol(conn, student, "41039", AUTUMN)
    with pytest.raises(EnrolmentError, match="already enrolled"):
        enrol(conn, student, "41039", SPRING)


def test_cannot_enrol_in_a_completed_subject(conn):
    with pytest.raises(EnrolmentError, match="already completed"):
        enrol(conn, 1, "41039", SPRING)


def test_unknown_subject_is_refused(conn):
    with pytest.raises(EnrolmentError, match="does not exist"):
        enrol(conn, 1, "99999", SPRING)


@pytest.mark.parametrize("session_label", ["", "Winter 2027", "Autumn 2026", "Spring 2028", "Autumn 2027; DROP"])
def test_only_the_open_sessions_are_accepted(conn, student, session_label):
    with pytest.raises(EnrolmentError, match="You can only enrol in Autumn 2027 or Spring 2027"):
        enrol(conn, student, "41039", session_label)
    assert rows(conn, student) == {}


def test_subject_must_be_offered_in_the_chosen_session(conn, student):
    with pytest.raises(EnrolmentError, match="is not offered in Spring 2027"):
        enrol(conn, student, "31777", SPRING)  # Advanced Interaction Design is Autumn only


# --- the load limit ----------------------------------------------------------------------------------------

def test_a_full_session_refuses_more_subjects(conn):
    with pytest.raises(EnrolmentError, match=r"Autumn 2027 is full \(24 of 24 credit points\)"):
        enrol(conn, 1, "43030", AUTUMN)  # demo student's Autumn is already full
    assert "43030" not in rows(conn)


def test_a_full_session_still_accepts_the_other_session(conn):
    enrol(conn, 1, "43030", SPRING)  # offered in both sessions
    assert rows(conn)["43030"] == ("enrolled", SPRING)


def test_four_subjects_fit_in_a_session_but_not_a_fifth(conn):
    for code in ["41079", "43030", "31265", "37181"]:  # four 6 cp core subjects
        enrol(conn, 1, code, SPRING)
    with pytest.raises(EnrolmentError, match=r"Spring 2027 is full \(24 of 24 credit points\)"):
        enrol(conn, 1, "41092", SPRING)
    assert "41092" not in rows(conn)


def test_the_limit_counts_credit_points_not_subjects(conn):
    conn.execute(
        "INSERT INTO enrolments (user_id, subject_code, status, session_label)"
        " VALUES (1, '31482', 'enrolled', 'Spring 2027')"  # Honours Project B is 12 cp
    )
    enrol(conn, 1, "43030", SPRING)
    enrol(conn, 1, "31265", SPRING)  # 12 + 6 + 6 = 24
    with pytest.raises(EnrolmentError, match="full"):
        enrol(conn, 1, "37181", SPRING)


def test_a_student_can_plan_a_whole_year_of_eight_subjects(conn, student):
    autumn = ["33130", "41039", "31265", "37181"]
    spring = ["31271", "31268", "31269", "41092"]
    for code in autumn:
        enrol(conn, student, code, AUTUMN)
    for code in spring:
        enrol(conn, student, code, SPRING)
    sessions = [session for _, session in rows(conn, student).values()]
    assert sessions.count(AUTUMN) == 4 and sessions.count(SPRING) == 4
    loads = evaluate_subjects(conn, student)["session_loads"]
    assert loads == {AUTUMN: 24, SPRING: 24}


def test_a_ninth_subject_is_refused_because_both_sessions_are_full(conn, student):
    for code in ["33130", "41039", "31265", "37181"]:
        enrol(conn, student, code, AUTUMN)
    for code in ["31271", "31268", "31269", "41092"]:
        enrol(conn, student, code, SPRING)
    with pytest.raises(EnrolmentError, match="Autumn 2027 is full .* and Spring 2027 is full"):
        enrol(conn, student, "43030", SPRING)
    assert len(rows(conn, student)) == 8


def test_elective_limits_still_apply(conn):
    with pytest.raises(EnrolmentError, match="General electives requirement already complete"):
        enrol(conn, 1, "SYN102", SPRING)


# --- withdrawing (Delete) ----------------------------------------------------------------------------------------

def test_demo_student_can_withdraw_from_a_seeded_enrolment(conn):
    assert withdraw(conn, 1, "41026") == "41026 Advanced Software Development"
    assert "41026" not in rows(conn)
    result = evaluate_subjects(conn, 1)
    assert result["session_loads"][AUTUMN] == 18
    assert result["subjects"]["41026"]["status"] == "available"  # can enrol again


def test_withdrawing_frees_room_in_the_session(conn):
    withdraw(conn, 1, "41040")
    enrol(conn, 1, "43030", AUTUMN)
    assert rows(conn)["43030"] == ("enrolled", AUTUMN)


def test_withdrawing_an_elective_reopens_the_elective_requirement(conn):
    for code in ["41052", "32113"]:
        enrol(conn, 1, code, SPRING)  # with 41040 that makes three major electives
    with pytest.raises(EnrolmentError, match="Major electives requirement already complete"):
        enrol(conn, 1, "31260", SPRING)
    withdraw(conn, 1, "41052")
    enrol(conn, 1, "31260", SPRING)


def test_cannot_withdraw_from_a_subject_you_are_not_in(conn):
    with pytest.raises(EnrolmentError, match="not enrolled"):
        withdraw(conn, 1, "41052")


def test_cannot_withdraw_a_completed_subject(conn):
    with pytest.raises(EnrolmentError, match="completed and can't be withdrawn"):
        withdraw(conn, 1, "41039")
    assert rows(conn)["41039"][0] == "completed"


def test_withdrawing_only_touches_the_students_own_row(conn, student):
    enrol(conn, student, "41039", AUTUMN)
    with pytest.raises(EnrolmentError, match="not enrolled"):
        withdraw(conn, student, "41026")  # that enrolment belongs to the demo student
    assert rows(conn)["41026"] == ("enrolled", AUTUMN)


# --- moving between sessions (Update) --------------------------------------------------------------------------

def test_an_enrolment_can_move_to_the_other_session(conn, student):
    enrol(conn, student, "43030", AUTUMN)
    assert move_session(conn, student, "43030", SPRING) == "43030 Professional Practice in Computing"
    assert rows(conn, student)["43030"] == ("enrolled", SPRING)


def test_cannot_move_to_the_session_it_is_already_in(conn, student):
    enrol(conn, student, "43030", AUTUMN)
    with pytest.raises(EnrolmentError, match="already in Autumn 2027"):
        move_session(conn, student, "43030", AUTUMN)


def test_cannot_move_to_a_session_the_subject_is_not_offered_in(conn):
    with pytest.raises(EnrolmentError, match="is not offered in Spring 2027"):
        move_session(conn, 1, "41026", SPRING)  # Autumn only


def test_cannot_move_into_a_full_session(conn, student):
    for code in ["31271", "31268", "31269", "41092"]:
        enrol(conn, student, code, SPRING)
    enrol(conn, student, "43030", AUTUMN)
    with pytest.raises(EnrolmentError, match="Spring 2027 is full"):
        move_session(conn, student, "43030", SPRING)
    assert rows(conn, student)["43030"] == ("enrolled", AUTUMN)


def test_cannot_move_a_completed_subject(conn):
    with pytest.raises(EnrolmentError, match="completed and can't be moved"):
        move_session(conn, 1, "41039", SPRING)


def test_cannot_move_a_subject_you_are_not_in(conn):
    with pytest.raises(EnrolmentError, match="not enrolled"):
        move_session(conn, 1, "43030", SPRING)


def test_move_options_are_offered_only_where_there_is_room(conn, student):
    enrol(conn, student, "43030", AUTUMN)
    assert evaluate_subjects(conn, student)["subjects"]["43030"]["move_sessions"] == [SPRING]
    assert evaluate_subjects(conn, 1)["subjects"]["41026"]["move_sessions"] == []  # Autumn-only subject