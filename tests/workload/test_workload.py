import pytest

from accounts.service import create_user
from degree_planner.service import add_to_plan, get_plan, move_in_plan, suggest_plan
from majors.service import choose_major
from submajors.service import choose_submajor
from workload.service import context_for_ai, load_context, rank, session_workload, suggest_moves


@pytest.fixture()
def ctx(conn):
    return load_context(conn)


def fake_ctx(subjects):
    """subjects = {code: (load, [(name, weight, due_week, exam?)])}: a tiny hand-made context."""
    infos, load, names = {}, {}, {}
    for code, (score, tasks) in subjects.items():
        names[code] = f"Subject {code}"
        load[code] = {"score": score, "reasons": []}
        task_rows = [{"name": n, "weight": w, "due_week": wk, "type": "exam" if exam else "project"} for n, w, wk, exam in tasks]
        infos[code] = {
            "tasks": task_rows, "group_weight": 0,
            "exam_weight": sum(t["weight"] for t in task_rows if t["type"] == "exam"),
        }
    return {"infos": infos, "load": load, "names": names}


def spread(offset):
    """Four equal tasks; a different offset per subject so their deadlines do not all land in the same weeks."""
    return [("T1", 25, 3 + offset, False), ("T2", 25, 7 + offset, False), ("T3", 25, 10 + offset, False), ("Exam", 25, 14, True)]


SPREAD = spread(0)
HIGH = {c: (5, spread(i)) for i, c in enumerate("ABCD")}


# --- the verdicts: both the good and the bad news ------------------------------------------------------------------------

def test_a_first_year_session_is_balanced_with_positives(ctx):
    w = session_workload(ctx, ["41039", "33130", "31265", "37181"])
    assert w["status"] == "balanced" and w["label"] == "Balanced"
    assert "No high-load subjects" in w["positives"] and w["high_load"] == []


def test_the_demo_students_current_session_is_heavy_because_of_bunched_deadlines(conn, ctx):
    w = session_workload(ctx, ["41026", "31272", "32144", "41040"])
    assert w["status"] == "heavy" and w["crunch_weeks"] == [8, 11]
    assert any(x.startswith("Crunch week 8:") for x in w["warnings"])
    assert not any("No crunch weeks" in p for p in w["positives"])


def test_four_high_load_subjects_together_are_too_heavy(ctx):
    w = session_workload(ctx, ["33230", "31251", "41052", "37233"])
    assert w["status"] == "too_heavy" and len(w["high_load"]) == 4
    assert any(x.startswith("4 high-load subjects (assessment load 4 or 5):") for x in w["warnings"])


def test_a_single_easy_subject_is_light(ctx):
    w = session_workload(ctx, ["31265"])
    assert w["status"] == "light" and w["warnings"] == []
    assert any("No crunch weeks" in p for p in w["positives"])


def test_the_verdict_never_gets_lighter_as_high_load_subjects_are_added(ctx):
    order = ["31265", "33230", "31251", "41052", "37233"]
    ranks = [rank(session_workload(ctx, order[:n])["status"]) for n in range(1, 6)]
    assert ranks == sorted(ranks)


def test_a_session_with_no_assessment_information_is_not_rated(ctx):
    w = session_workload(ctx, ["41759"])  # Capstone: no confirmed breakdown
    assert w["status"] is None and w["label"] == "Not enough information"
    assert any("no assessment information" in x for x in w["warnings"])
    assert context_for_ai(ctx, "Autumn 2027", ["41759"]).startswith("Not enough context")


def test_unknown_subjects_are_reported_not_averaged_in(ctx):
    with_unknown = session_workload(ctx, ["31265", "41759"])
    alone = session_workload(ctx, ["31265"])
    assert with_unknown["average_load"] == alone["average_load"] and with_unknown["unknown"] == ["41759"]
    assert any("may be understated" in x for x in with_unknown["warnings"])


def test_an_empty_session_is_not_rated(ctx):
    assert session_workload(ctx, [])["status"] is None


def test_exams_are_in_the_exam_period_and_never_count_as_a_crunch_week(ctx):
    w = session_workload(fake_ctx({c: (3, [("Exam", 100, 14, True)]) for c in "ABCDE"}), list("ABCDE"))
    assert w["crunch_weeks"] == [] and w["weeks"] == {}


def test_enough_deadlines_in_one_week_is_a_crunch_week():
    ctx = fake_ctx({c: (3, [("T", 20, 9, False), ("Exam", 80, 14, True)]) for c in "ABCD"})
    w = session_workload(ctx, list("ABCD"))
    assert w["crunch_weeks"] == [9] and w["weeks"][9]["count"] == 4 and w["weeks"][9]["weight"] == 80


def test_the_ai_context_carries_the_caveats(ctx):
    text = context_for_ai(ctx, "Autumn 2027", ["41026", "31272", "32144", "41040"])
    assert text.startswith("Autumn 2027: Heavy workload") and "Concern: Crunch week 8" in text
    assert "app estimate" in text and "not a UTS rating" in text and "illustrative" in text


# --- suggested moves -----------------------------------------------------------------------------------------------------

def test_a_heavy_session_gets_a_move_that_lightens_it():
    ctx = fake_ctx(HIGH)
    sessions = {"S1": list("ABCD"), "S2": []}
    found = suggest_moves(ctx, sessions, "S1", [(c, ["S2"]) for c in "ABCD"])
    assert found and found[0]["to"] == "S2" and found[0]["from"] == "S1"
    before = session_workload(ctx, sessions["S1"])
    assert rank(session_workload(ctx, ["B", "C", "D"])["status"]) <= rank(before["status"])
    assert "would go from" in found[0]["reason"]


def test_suggestions_are_limited_and_never_repeat_a_subject():
    ctx = fake_ctx(HIGH)
    found = suggest_moves(ctx, {"S1": list("ABCD"), "S2": [], "S3": []}, "S1", [(c, ["S2", "S3"]) for c in "ABCD"])
    assert len(found) <= 2 and len({f["code"] for f in found}) == len(found)


def test_a_session_that_is_not_heavy_gets_no_suggestions():
    ctx = fake_ctx({"A": (2, SPREAD), "B": (2, SPREAD)})
    assert suggest_moves(ctx, {"S1": ["A", "B"], "S2": []}, "S1", [("A", ["S2"])]) == []


def test_a_move_into_a_session_that_would_be_just_as_heavy_is_not_suggested():
    ctx = fake_ctx({**HIGH, **{c: (5, SPREAD) for c in "EFGH"}})
    assert suggest_moves(ctx, {"S1": list("ABCD"), "S2": list("EFGH")}, "S1", [(c, ["S2"]) for c in "ABCD"]) == []


def test_only_the_movable_subjects_are_ever_suggested():
    ctx = fake_ctx(HIGH)
    found = suggest_moves(ctx, {"S1": list("ABCD"), "S2": []}, "S1", [("C", ["S2"])])  # the others are enrolled
    assert [f["code"] for f in found] == ["C"]


def test_enrolled_subjects_are_never_offered_as_moves(conn):
    first = get_plan(conn, 1)["sessions"][0]  # John's Autumn 2027 is Heavy, but every subject is enrolled
    assert first["workload"]["status"] == "heavy" and first["suggestions"] == []


# --- the planner -----------------------------------------------------------------------------------------------------------

def test_every_planner_session_carries_a_workload_and_suggestions(conn):
    for s in get_plan(conn, 1)["sessions"]:
        assert "workload" in s and "suggestions" in s


def test_the_demo_students_planner_shows_his_heavy_session(conn):
    first = get_plan(conn, 1)["sessions"][0]
    assert first["label"] == "Autumn 2027" and first["workload"]["label"] == "Heavy"


def test_a_planned_session_is_rated_and_every_suggestion_can_really_be_applied(conn):
    user = create_user(conn, "new.student@student.uni.edu.au", "Str0ng#Pass", "Autumn 2027")["id"]
    choose_major(conn, user, "MAJ03519")
    choose_submajor(conn, user, "SMJ10156")
    suggest_plan(conn, user)
    plan = get_plan(conn, user)
    assert any(s["workload"]["status"] for s in plan["sessions"])
    for s in plan["sessions"]:
        for sg in s["suggestions"]:
            move_in_plan(conn, user, sg["code"], sg["to"])  # raises if the move is not allowed
            return
