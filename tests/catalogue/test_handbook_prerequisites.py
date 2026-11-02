import pytest

from accounts.service import create_user
from degree_planner.service import PlanError, add_to_plan, get_plan, suggest_plan
from enrolment.service import evaluate_subjects
from majors.service import choose_major
from submajors.service import choose_submajor

AUTUMN = "Autumn 2027"
MAJORS = ["MAJ03519", "MAJ10053", "MAJ02080", "MAJ02900", "MAJ02092", "MAJ01156", "MAJ03445", "MAJ02901"]


@pytest.fixture()
def student(conn):
    return create_user(conn, "new.student@student.uni.edu.au", "Str0ng#Pass", AUTUMN)["id"]


def complete(conn, user_id, *codes, session="Autumn 2026"):
    for code in codes:
        conn.execute(
            "INSERT INTO enrolments (user_id, subject_code, status, session_label) VALUES (?, ?, 'completed', ?)",
            (user_id, code, session),
        )
    conn.commit()


def info(conn, user_id, code):
    return evaluate_subjects(conn, user_id)["subjects"][code]


# --- names now match the handbook ---------------------------------------------------------------------------------

@pytest.mark.parametrize("code,name", [
    ("31482", "Honours Project"), ("32931", "Technology Research Methods"), ("35007", "Real Analysis"),
    ("37234", "Complex Analysis"), ("68416", "Computational Physics"),
])
def test_subject_names_match_the_handbook(conn, code, name):
    assert conn.execute("SELECT name FROM subjects WHERE code = ?", (code,)).fetchone()[0] == name


# --- rules that came from the handbook --------------------------------------------------------------------------------

def test_a_handbook_prerequisite_blocks_until_it_is_completed(conn, student):
    choose_major(conn, student, "MAJ03519")
    assert info(conn, student, "31271")["note"] == "Needs 41039 Programming 1"  # Database Fundamentals
    complete(conn, student, "41039")
    assert info(conn, student, "31271")["status"] == "available"


def test_a_second_route_from_the_handbook_is_accepted(conn, student):
    choose_major(conn, student, "MAJ03519")
    assert info(conn, student, "41001")["status"] == "blocked"  # Cloud Computing: 48024 OR 31271
    complete(conn, student, "31271")
    assert info(conn, student, "41001")["status"] == "available"


def test_honours_project_now_needs_technology_research_methods(conn):
    reasons = info(conn, 1, "31482")["reasons"]  # John Doe has not completed 32931
    assert reasons == ["Needs 32931 Technology Research Methods"]


def test_a_subject_without_a_handbook_prerequisite_has_none(conn, student):
    choose_major(conn, student, "MAJ03519")
    assert info(conn, student, "31260")["status"] == "available"  # Fundamentals of Interaction Design


def test_32146_is_not_blocked_for_business_information_systems(conn, student):
    choose_major(conn, student, "MAJ02080")
    assert info(conn, student, "32146")["status"] == "available"  # its handbook rule is only a note here


# --- credit points of completed study in the whole degree ------------------------------------------------------------------

def test_a_degree_wide_credit_condition_is_reported(conn, student):
    choose_major(conn, student, "MAJ03519")
    assert info(conn, student, "41078")["reasons"] == ["Needs 36 credit points completed in your degree (you have 0)"]


def test_meeting_the_degree_wide_condition_unlocks_the_subject(conn, student):
    choose_major(conn, student, "MAJ03519")
    complete(conn, student, "41039", "33130", "31268", "37181", "31265", "41092")  # 36 cp
    assert info(conn, student, "41078")["status"] == "available"  # Autumn 2027 is open and offers it


def test_enrolled_credit_does_not_count_towards_the_degree_wide_condition(conn, student):
    choose_major(conn, student, "MAJ03519")
    complete(conn, student, "41039", "33130", "31268", "37181", "31265")  # 30 cp
    conn.execute("INSERT INTO enrolments (user_id, subject_code, status, session_label) VALUES (?, '41092', 'enrolled', ?)", (student, AUTUMN))
    conn.commit()
    assert info(conn, student, "41078")["status"] == "blocked"


def test_planning_counts_credit_planned_in_earlier_sessions(conn, student):
    choose_major(conn, student, "MAJ03519")
    with pytest.raises(PlanError, match=r"Needs 36 credit points completed in your degree \(0 completed, or planned in earlier sessions\)"):
        add_to_plan(conn, student, "41078", "Autumn 2028")
    for code, session in [("41039", "Autumn 2027"), ("33130", "Autumn 2027"), ("31268", "Autumn 2027"), ("37181", "Autumn 2027"),
                          ("31265", "Spring 2027"), ("41092", "Spring 2027")]:
        add_to_plan(conn, student, code, session)
    add_to_plan(conn, student, "41078", "Autumn 2028")


# --- the whole degree still works ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("major", MAJORS)
def test_every_major_still_plans_in_full_under_the_handbook_rules(conn, major):
    uid = create_user(conn, "m.student@student.uni.edu.au", "Str0ng#Pass", AUTUMN)["id"]
    choose_major(conn, uid, major)
    choose_submajor(conn, uid, "SMJ10156")  # Innovation and Entrepreneurship: four core subjects
    added, unplaced = suggest_plan(conn, uid)
    plan = get_plan(conn, uid)
    assert unplaced == [] and plan["complete"] is True and plan["remaining_cp"] == 0
    assert all(s["load_cp"] <= 24 for s in plan["sessions"])


def test_the_demo_students_enrolled_subjects_are_all_still_allowed(conn):
    result = evaluate_subjects(conn, 1)["subjects"]
    for code in ("41026", "31272", "32144", "41040"):
        assert result[code]["status"] == "enrolled"


def test_the_demo_student_moved_two_subjects_to_keep_the_history_valid(conn):
    sessions = {r["subject_code"]: r["session_label"] for r in conn.execute(
        "SELECT subject_code, session_label FROM enrolments WHERE user_id = 1")}
    assert sessions["31268"] == "Autumn 2025" and sessions["31271"] == "Autumn 2026"  # Database Fundamentals needs Programming 1 first
