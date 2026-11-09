"""Every transdisciplinary elective needs at least 36 credit points completed in a bachelor's degree (2027 Handbook, as supplied)."""
import pytest

from features.accounts.service import create_user
from features.degree_planner.board import build_board
from features.degree_planner.service import PlanError, add_to_plan
from features.enrolment.results import record_result
from features.enrolment.service import evaluate_subjects
from features.majors.service import choose_major
from features.subject_catalogue.seed import seed_catalogue
from features.subject_catalogue.service import prerequisite_lines
from features.submajors.service import choose_electives
from shared import db

TD = [f"9500{n}" for n in range(2, 10)]
SIX = ("33130", "37181", "41039", "31265", "33230", "31271")  # six 6 cp core subjects = 36 credit points
NEEDS = "Needs 36 credit points completed in your degree"


@pytest.fixture()
def conn(tmp_path):
    path = tmp_path / "t.db"
    db.build_database(str(path), demo_profile="fresh")
    c = db.connect(str(path))
    yield c
    c.close()


@pytest.fixture()
def student(conn):
    user = create_user(conn, "td.prereq@student.uni.edu.au", "Str0ng#Pass", "Autumn 2027")["id"]
    choose_major(conn, user, "MAJ03519")
    choose_electives(conn, user)
    return user


def reasons(conn, user, code):
    return evaluate_subjects(conn, user)["subjects"][code]["reasons"]


def complete(conn, user, codes, session="Autumn 2026"):
    for code in codes:
        record_result(conn, user, code, session, "passed")


# --- the stored rule -------------------------------------------------------------------------------------------------------------------------------

def test_all_eight_have_the_same_requirement_stored_against_the_whole_degree(conn):
    rows = conn.execute("SELECT subject_code, major_code, min_cp FROM credit_requirements WHERE subject_code LIKE '9500%' ORDER BY subject_code").fetchall()
    assert [(r[0], r[1], r[2]) for r in rows] == [(code, None, 36) for code in TD]  # no major: credit points completed anywhere in the degree


def test_they_are_now_marked_as_having_a_requisite_not_unknown(conn):
    assert {r[0] for r in conn.execute("SELECT prereq_status FROM subjects WHERE category = 'td_elective'")} == {"required"}


@pytest.mark.parametrize("code", TD)
def test_the_subject_page_data_states_the_requirement_and_its_source(conn, code):
    assert prerequisite_lines(conn, code) == ["36 credit points completed in your degree"]
    note = conn.execute("SELECT note FROM prerequisite_notes WHERE subject_code = ?", (code,)).fetchone()[0]
    assert "36 credit points completed in a bachelor's degree" in note and "2027 Handbook" in note


def test_seeding_again_does_not_duplicate_the_rule_or_the_note(conn):
    seed_catalogue(conn)
    seed_catalogue(conn)
    assert conn.execute("SELECT COUNT(*) FROM credit_requirements WHERE subject_code LIKE '9500%'").fetchone()[0] == 8
    assert conn.execute("SELECT COUNT(*) FROM prerequisite_notes WHERE subject_code LIKE '9500%'").fetchone()[0] == 8


def test_no_other_subject_was_given_this_requirement(conn):
    others = {r[0] for r in conn.execute("SELECT subject_code FROM credit_requirements WHERE major_code IS NULL AND min_cp = 36")} - set(TD)
    assert "95003" not in others and not (others & set(TD))


# --- enforcement when enrolling ----------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("code", TD)
def test_a_student_with_no_credit_points_cannot_take_any_of_them(conn, student, code):
    assert reasons(conn, student, code) == [f"{NEEDS} (you have 0)"]
    assert evaluate_subjects(conn, student)["subjects"][code]["status"] == "blocked"


def test_thirty_credit_points_is_not_enough_and_thirty_six_is(conn, student):
    complete(conn, student, SIX[:5])
    assert reasons(conn, student, "95003") == [f"{NEEDS} (you have 30)"]
    complete(conn, student, SIX[5:])
    assert reasons(conn, student, "95003") == [] and evaluate_subjects(conn, student)["subjects"]["95003"]["status"] == "available"


def test_a_failed_subject_does_not_count_towards_the_36(conn, student):
    complete(conn, student, SIX[:5])
    record_result(conn, student, SIX[5], "Autumn 2026", "failed")
    assert reasons(conn, student, "95003") == [f"{NEEDS} (you have 30)"]


def test_credit_points_count_from_anywhere_in_the_degree_not_one_category(conn, student):
    complete(conn, student, ["33130", "37181", "41039", "31265", "33230", "41052"])  # five core subjects and a major option
    assert reasons(conn, student, "95008") == []


def test_the_requirement_applies_on_the_sub_major_route_too(conn):
    from features.submajors.service import choose_submajor
    user = create_user(conn, "hum.prereq@student.uni.edu.au", "Str0ng#Pass", "Autumn 2027")["id"]
    choose_major(conn, user, "MAJ03519")
    choose_submajor(conn, user, "SMJ10196")
    assert reasons(conn, user, "95003") == [f"{NEEDS} (you have 0)"]
    complete(conn, user, SIX)
    assert reasons(conn, user, "95003") == []


# --- enforcement in the planner ------------------------------------------------------------------------------------------------------------------------

def test_the_planner_refuses_a_transdisciplinary_subject_too_early_with_the_reason(conn, student):
    with pytest.raises(PlanError, match=r"Needs 36 credit points completed in your degree \(0 completed, or planned in earlier sessions\)"):
        add_to_plan(conn, student, "95003", "Spring 2027")


def test_subjects_planned_in_earlier_sessions_count_but_not_the_same_session(conn, student):
    complete(conn, student, SIX[:3])  # 18 completed
    for code in ("SYN103", "SYN106", "SYN109"):
        add_to_plan(conn, student, code, "Spring 2027")  # 18 more, planned in Spring 2027
    with pytest.raises(PlanError, match=r"\(18 completed, or planned in earlier sessions\)"):
        add_to_plan(conn, student, "95003", "Spring 2027")  # planned in the same session does not count
    assert "95003" in add_to_plan(conn, student, "95003", "Spring 2028")  # 18 completed + 18 planned in an earlier session = 36


def test_the_board_offers_no_session_until_the_student_has_the_credit_points(conn, student):
    todo = {c["code"]: c for c in build_board(conn, student)["to_place"] if c["category_key"] == "td_elective"}
    assert set(todo) == set(TD) and all(c["valid_sessions"] == [] for c in todo.values())
    complete(conn, student, SIX)
    todo = {c["code"]: c for c in build_board(conn, student)["to_place"] if c["category_key"] == "td_elective"}
    assert all(c["valid_sessions"] for c in todo.values())
    assert all(s.startswith("Spring") for s in todo["95003"]["valid_sessions"]) and all(s.startswith("Autumn") for s in todo["95006"]["valid_sessions"])


# --- the pages --------------------------------------------------------------------------------------------------------------------------------------------

def test_the_subject_page_shows_the_requirement_and_where_it_comes_from(client, log_in):
    log_in()
    page = client.get("/subjects/95003", follow_redirects=True).get_data(as_text=True)
    assert "At least 36 credit points completed in your degree" in page and "at least 36 credit points completed in a bachelor&#39;s degree" in page
    assert "Prerequisites for this subject are not in the supplied data" not in page


def test_the_electives_page_and_the_help_page_mention_it(client, log_in):
    log_in()
    assert "<strong>36 credit points completed</strong>" in client.get("/submajor/electives", follow_redirects=True).get_data(as_text=True)
    assert "needs 36 completed credit points first" in client.get("/help", follow_redirects=True).get_data(as_text=True)


def test_the_demo_student_has_enough_credit_points_for_one(client, log_in):
    log_in()  # John has 96 completed credit points
    page = client.get("/subjects/95003", follow_redirects=True).get_data(as_text=True)
    assert "Needs 36 credit points" not in page
