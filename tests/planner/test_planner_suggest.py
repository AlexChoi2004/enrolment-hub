import pytest

from accounts.service import create_user
from degree_planner import service
from degree_planner.service import add_to_plan, clear_plan, get_plan, suggest_plan


@pytest.fixture()
def student(conn):
    return create_user(conn, "new.student@student.uni.edu.au", "Str0ng#Pass", "Autumn 2027")["id"]


def planned(conn, user_id):
    return {
        r["subject_code"]: r["session_label"]
        for r in conn.execute("SELECT subject_code, session_label FROM planned_subjects WHERE user_id = ?", (user_id,))
    }


def order(session):
    from enrolment.service import session_sort_key
    return session_sort_key(session)


def test_a_new_student_gets_a_complete_plan(conn, student):
    added, unplaced = suggest_plan(conn, student)
    plan = get_plan(conn, student)
    assert (added, unplaced) == (31, [])
    assert plan["planned_cp"] == 192 and plan["remaining_cp"] == 0
    assert plan["complete"] is True and plan["problems"] == []


def test_no_session_goes_over_the_limit(conn, student):
    suggest_plan(conn, student)
    assert all(s["load_cp"] <= 24 for s in get_plan(conn, student)["sessions"])


def test_the_degree_fits_in_eight_sessions(conn, student):
    suggest_plan(conn, student)
    used = {session for session in planned(conn, student).values()}
    assert len(used) == 8


def test_every_suggested_placement_passes_the_same_rules_as_a_manual_change(conn, student):
    suggest_plan(conn, student)
    state = service._state(conn, student)
    for code, session in state["plan"].items():
        assert service._check_placement(state, code, session, ignore_self=True) is None, (code, session)


def test_prerequisites_always_come_in_an_earlier_session(conn, student):
    suggest_plan(conn, student)
    plan = planned(conn, student)
    for subject, prereq in conn.execute("SELECT subject_code, prereq_code FROM prerequisites"):
        if subject in plan:
            assert order(plan[prereq]) < order(plan[subject]), (prereq, subject)


def test_elective_counts_are_exact(conn, student):
    suggest_plan(conn, student)
    plan = planned(conn, student)
    cats = {r["code"]: r["category"] for r in conn.execute("SELECT code, category FROM subjects")}
    chosen = [cats[c] for c in plan]
    assert chosen.count("major_elective") == 3 and chosen.count("general_elective") == 4


def test_the_supplied_honours_rule_is_followed_and_the_12_cp_project_is_in_autumn(conn, student):
    suggest_plan(conn, student)
    plan = planned(conn, student)
    assert order(plan["32144"]) < order(plan["32931"])  # Honours Project A needs Technology Research Preparation
    assert plan["31482"].startswith("Autumn")  # Honours Project B is Autumn only (no rule links it to A in the supplied data)


def test_suggestions_are_repeatable(conn, student):
    other = create_user(conn, "other.student@student.uni.edu.au", "Str0ng#Pass", "Autumn 2027")["id"]
    suggest_plan(conn, student)
    suggest_plan(conn, other)
    assert planned(conn, student) == planned(conn, other)


def test_suggesting_twice_adds_nothing_the_second_time(conn, student):
    suggest_plan(conn, student)
    assert suggest_plan(conn, student) == (0, [])


def test_the_demo_student_only_gets_what_is_still_needed(conn):
    added, unplaced = suggest_plan(conn, 1)
    plan = planned(conn, 1)
    assert (added, unplaced) == (11, [])  # nine required subjects and two more major electives
    assert "Autumn 2027" not in plan.values()  # already full
    assert not {"41039", "41026", "32144"} & set(plan)  # nothing completed or enrolled is planned
    assert get_plan(conn, 1)["complete"] is True


def test_an_existing_plan_is_kept(conn, student):
    add_to_plan(conn, student, "41039", "Autumn 2028")
    suggest_plan(conn, student)
    plan = planned(conn, student)
    assert plan["41039"] == "Autumn 2028"
    assert get_plan(conn, student)["complete"] is True


def test_a_suggestion_can_be_cleared(conn, student):
    suggest_plan(conn, student)
    assert clear_plan(conn, student) == 31
    assert get_plan(conn, student)["has_plan"] is False


def test_subjects_that_do_not_fit_are_reported(conn, student, monkeypatch):
    monkeypatch.setattr(service, "plan_sessions", lambda *a, **k: ["Autumn 2027", "Spring 2027"])
    added, unplaced = suggest_plan(conn, student)
    assert 0 < added < 31
    assert unplaced and all(" " in label for label in unplaced)