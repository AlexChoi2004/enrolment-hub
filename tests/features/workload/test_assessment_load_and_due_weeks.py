import pytest

from features.subject_catalogue.assessments import EXAM_WEEK, assessment_info, ai_context, illustrative_due_weeks
from features.subject_catalogue.assessment_load import estimate, prerequisite_depths
from features.subject_catalogue.service import get_subject, list_subjects, load_prerequisites
from features.workload.service import load_context


def score(conn, code):
    return load_context(conn)["load"][code]["score"]


# --- prerequisite depth ----------------------------------------------------------------------------------------------

def test_depth_counts_how_deep_a_prerequisite_chain_goes():
    rules = {"B": [{"codes": ["A"], "concurrent": False}], "C": [{"codes": ["B"], "concurrent": False}]}
    assert prerequisite_depths(rules) == {"A": 0, "B": 1, "C": 2}


def test_alternatives_count_by_their_shortest_route():
    rules = {"B": [{"codes": ["A"], "concurrent": False}],
             "C": [{"codes": ["A", "B"], "concurrent": False}]}  # A or B: A is the shorter route
    assert prerequisite_depths(rules)["C"] == 1


def test_a_cycle_never_loops_forever():
    rules = {"A": [{"codes": ["B"], "concurrent": False}], "B": [{"codes": ["A"], "concurrent": False}]}
    assert set(prerequisite_depths(rules)) == {"A", "B"}


# --- the estimate -------------------------------------------------------------------------------------------------------

def test_every_known_subject_gets_a_score_from_1_to_5_and_every_score_is_used(conn):
    scores = [d["score"] for d in load_context(conn)["load"].values() if d["score"] is not None]
    assert scores and all(1 <= s <= 5 for s in scores)
    assert set(scores) == {1, 2, 3, 4, 5}


def test_a_subject_without_an_assessment_breakdown_gets_no_score_not_an_average(conn):
    unknown = [c for c, d in load_context(conn)["load"].items() if d["score"] is None]
    assert len(unknown) == 82 and "41759" in unknown  # the Capstone has no confirmed breakdown
    assert load_context(conn)["load"]["41759"]["reasons"] == ["Not enough information: there is no confirmed assessment breakdown."]


def test_a_deeper_subject_with_more_assessments_scores_higher_than_an_introductory_one(conn):
    assert score(conn, "41039") < score(conn, "31251")  # Programming 1 versus Data Structures and Algorithms


def test_a_big_exam_adds_to_the_score(conn):
    info = assessment_info(conn, "33230")  # Mathematics 2: the final exam is 50%
    with_exam, reasons = estimate(info, 0, 6, "core")
    without_exam, _ = estimate({**info, "exam_weight": 0}, 0, 6, "core")
    assert with_exam > without_exam and any("the exam is 50%" in r for r in reasons)


def test_a_hurdle_is_mentioned_in_the_reasons(conn):
    assert any("hurdle" in r for r in load_context(conn)["load"]["33130"]["reasons"])


def test_the_reasons_explain_the_score(conn):
    reasons = load_context(conn)["load"]["31251"]["reasons"]
    assert any("prerequisite chain" in r for r in reasons) and any("exam" in r for r in reasons)


def test_assessment_load_is_attached_to_every_subject(conn):
    subject = get_subject(conn, "31251")
    assert subject["assessment_load"]["score"] == score(conn, "31251")
    assert all("assessment_load" in s for s in list_subjects(conn))


# --- illustrative due weeks ------------------------------------------------------------------------------------------------

TASKS = [("Quiz", "quiz", "individual", 10), ("Project", "project", "group", 40), ("Report", "report", "individual", 20),
         ("Extension", "project", "individual", None), ("Exam", "exam", "individual", 30)]


def test_due_weeks_are_repeatable():
    assert illustrative_due_weeks("99999", TASKS) == illustrative_due_weeks("99999", TASKS)


def test_exams_go_in_the_exam_period_and_other_tasks_fall_within_the_session():
    weeks = illustrative_due_weeks("99999", TASKS)
    assert weeks[4] == EXAM_WEEK == 14
    assert all(2 <= w <= 13 for i, w in enumerate(weeks) if i != 4)


def test_a_mandatory_task_with_no_marks_is_due_early():
    assert illustrative_due_weeks("99999", TASKS)[3] == 3


def test_later_tasks_fall_later_in_the_session():
    quiz, project, report = illustrative_due_weeks("99999", TASKS)[:3]
    assert quiz <= project <= report + 1  # allowing the small per-task nudge


def test_different_subjects_peak_in_different_weeks():
    patterns = {tuple(illustrative_due_weeks(code, TASKS)) for code in ("31251", "41052", "33230", "48730", "41039", "31005")}
    assert len(patterns) > 1


def test_the_stored_weeks_match_the_generator(conn):
    stored = [r["due_week"] for r in conn.execute(
        "SELECT a.due_week FROM assessments a JOIN assessment_structures s ON s.id = a.structure_id"
        " WHERE s.subject_code = '41039' ORDER BY a.position")]
    info = assessment_info(conn, "41039")
    expected = illustrative_due_weeks("41039", [(t["name"], t["type"], t["groupwork"], t["weight"]) for t in info["tasks"]])
    assert stored == expected


def test_the_ai_is_told_due_weeks_are_illustrative(conn):
    assert "(illustrative)" in ai_context(conn, "41039")["text"]


def test_an_unverified_subject_has_no_weeks_at_all(conn):
    assert assessment_info(conn, "41759")["tasks"] == []
    assert not ai_context(conn, "41759")["assessments_known"]
