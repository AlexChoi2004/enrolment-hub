"""The eight Transdisciplinary Electives: assessments, descriptions and sessions as the 2027 Handbook pages list them (supplied 9 November 2026)."""
import pytest

from features.subject_catalogue.assessments import load_assessment_info
from features.subject_catalogue.submajor_data import TD_AVAILABILITY
from features.workload.service import load_context
from shared import db

# (type as the app stores it, groupwork, weight) per task, in the Handbook's order. The Handbook gives categories and weightings only.
EXPECTED = {
    "95002": [("portfolio", "group_individual", 35), ("project", "group_individual", 30), ("project", "group_individual", 35)],
    "95003": [("report", "individual", 30), ("report", "individual", 40), ("presentation", "group_individual", 30)],
    "95004": [("quiz", "individual", 15), ("portfolio", "individual", 35), ("presentation", "group_individual", 50)],
    "95005": [],
    "95006": [("project", "individual", 30), ("project", "group", 30), ("essay", "individual", 40)],
    "95007": [("portfolio", "group_individual", 40), ("presentation", "group", 35), ("reflection", "individual", 25)],
    "95008": [("project", "group_individual", 65), ("project", "group_individual", 35)],
    "95009": [("design", "individual", 35), ("project", "group_individual", 25), ("demonstration", "group_individual", 40)],
}
SESSIONS = {"95002": "Autumn", "95003": "Spring", "95004": "Spring", "95005": "Autumn", "95006": "Autumn", "95007": "Spring", "95008": "Autumn", "95009": "Spring"}
OTHER = {"95002": "July session (block)", "95003": "February session (block)", "95005": "July session (block)", "95009": "December session (block)"}


@pytest.fixture(scope="module")
def conn(tmp_path_factory):
    path = tmp_path_factory.mktemp("td") / "t.db"
    db.build_database(str(path), demo_profile="fresh")
    c = db.connect(str(path))
    yield c
    c.close()


@pytest.mark.parametrize("code", EXPECTED)
def test_the_tasks_are_exactly_what_the_handbook_page_lists(conn, code):
    info = load_assessment_info(conn)[code]
    assert [(t["type"], t["groupwork"], t["weight"]) for t in info["tasks"]] == EXPECTED[code]


@pytest.mark.parametrize("code", [c for c, t in EXPECTED.items() if t])
def test_the_weightings_add_up_to_100_and_every_task_has_a_type(conn, code):
    info = load_assessment_info(conn)[code]
    assert info["total_weight"] == 100 and info["status"] == "indicative" and all(t["type_label"] and t["group_label"] for t in info["tasks"])
    assert info["exam_weight"] == 0 and info["year"] == 2027  # none of the eight has an exam


def test_group_weights_follow_the_handbooks_group_classification(conn):
    info = load_assessment_info(conn)
    assert {c: info[c]["group_weight"] for c in ("95002", "95003", "95004", "95006", "95007", "95008", "95009")} == {
        "95002": 100, "95003": 30, "95004": 50, "95006": 30, "95007": 75, "95008": 100, "95009": 65}


def test_the_source_year_and_date_are_recorded_and_not_passed_off_as_something_else(conn):
    info = load_assessment_info(conn)["95003"]
    assert info["year"] == 2027 and info["retrieved_on"] == "2026-11-09" and "2027" in info["source"] and "supplied by the student" in info["source"]
    assert "indicative" in info["banner"].lower() or "handbook" in info["banner"].lower()


def test_95005_is_recorded_as_listing_no_assessment_and_gets_no_invented_tasks(conn):
    info = load_assessment_info(conn)["95005"]
    assert info["tasks"] == [] and info["status"] == "none" and info["published_none"] is True
    assert load_context(conn)["load"]["95005"]["score"] is None  # not enough information, not an average
    assert all(not load_assessment_info(conn)[c]["published_none"] for c in EXPECTED if c != "95005")


def test_an_assessment_load_rating_is_worked_out_for_each_subject_with_tasks(conn):
    load = load_context(conn)["load"]
    scores = {c: load[c]["score"] for c in EXPECTED}
    assert scores["95005"] is None and all(1 <= s <= 5 for c, s in scores.items() if c != "95005")
    assert scores["95008"] == 2 and "one task is worth 65% of the marks" in load["95008"]["reasons"]  # the only one with a task worth most of the marks
    assert all(scores[c] == 1 for c in ("95002", "95003", "95004", "95006", "95007", "95009"))  # no exam, no hurdle, three tasks, no known prerequisite chain


def test_every_subject_has_a_description_in_our_own_words_and_tags(conn):
    info = load_assessment_info(conn)
    for code in EXPECTED:
        assert 60 < len(info[code]["summary"]) < 260 and info[code]["tags"], code
    assert len({info[c]["summary"] for c in EXPECTED}) == 8


@pytest.mark.parametrize("code", EXPECTED)
def test_the_session_is_the_handbooks_autumn_or_spring_and_marked_as_such(conn, code):
    row = conn.execute("SELECT sessions_offered, sessions_source, sessions_note FROM subjects WHERE code = ?", (code,)).fetchone()
    assert (row[0], row[1], row[2]) == (SESSIONS[code], "handbook", OTHER.get(code)) and TD_AVAILABILITY[code][0] == SESSIONS[code]


def test_only_the_transdisciplinary_subjects_have_handbook_sessions_all_others_stay_illustrative(conn):
    handbook = {r[0] for r in conn.execute("SELECT code FROM subjects WHERE sessions_source = 'handbook'")}
    assert handbook == set(EXPECTED) and conn.execute("SELECT COUNT(*) FROM subjects WHERE sessions_source = 'illustrative'").fetchone()[0] == 189 - 8


def test_a_transdisciplinary_subject_can_only_be_planned_in_its_own_session(conn):
    from features.accounts.service import create_user
    from features.degree_planner.service import PlanError, add_to_plan
    from features.enrolment.results import record_result
    from features.majors.service import choose_major
    from features.submajors.service import choose_electives
    user = create_user(conn, "td.session@student.uni.edu.au", "Str0ng#Pass", "Autumn 2027")["id"]
    choose_major(conn, user, "MAJ03519")
    choose_electives(conn, user)
    for code in ("33130", "37181", "41039", "31265", "33230", "31271"):  # the 36 completed credit points a transdisciplinary subject needs
        record_result(conn, user, code, "Autumn 2026", "passed")
    with pytest.raises(PlanError, match="not offered in Autumn 2029"):
        add_to_plan(conn, user, "95003", "Autumn 2029")  # a Spring subject
    assert "95003" in add_to_plan(conn, user, "95003", "Spring 2029")


def test_seeding_again_keeps_one_current_structure_per_transdisciplinary_subject(conn):
    from features.subject_catalogue.seed import seed_catalogue
    seed_catalogue(conn)
    seed_catalogue(conn)
    for code in EXPECTED:
        assert conn.execute("SELECT COUNT(*) FROM assessment_structures WHERE subject_code = ? AND is_current = 1", (code,)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM subject_descriptions WHERE subject_code = ?", (code,)).fetchone()[0] == 1


def test_an_older_database_gets_the_availability_columns_and_keeps_its_data():
    import sqlite3
    old = sqlite3.connect(":memory:")
    old.executescript("CREATE TABLE subjects (code TEXT PRIMARY KEY, name TEXT, sessions_offered TEXT); INSERT INTO subjects VALUES ('95003', 'TD', 'Both');")
    db.add_missing_columns(old)
    db.add_missing_columns(old)
    assert old.execute("SELECT code, sessions_offered, sessions_source, sessions_note FROM subjects").fetchall() == [("95003", "Both", "illustrative", None)]


def test_pages_say_where_the_sessions_come_from_and_mention_the_other_sessions(client, log_in):
    log_in()
    page = client.get("/subjects/95009", follow_redirects=True).get_data(as_text=True)
    assert "Offered: Spring" in page and "Handbook 2027" in page and "also lists a December session (block)" in page and "only plans Autumn and Spring" in page
    illustrative = client.get("/subjects/31251", follow_redirects=True).get_data(as_text=True)
    assert "Offered:" in illustrative and 'class="badge">illustrative</span>' in illustrative and "Handbook 2027" not in illustrative.split("<h2>Assessment</h2>")[0]


def test_a_subject_whose_page_lists_no_assessment_says_so(client, log_in):
    log_in()
    page = client.get("/subjects/95005", follow_redirects=True).get_data(as_text=True)
    assert "The 2027 Handbook page lists no assessment information for this subject" in page and "Not yet populated: the assessment" not in page


def test_a_subject_with_tasks_shows_the_table_the_load_badge_and_the_estimate_warning(client, log_in):
    log_in()
    page = client.get("/subjects/95008", follow_redirects=True).get_data(as_text=True)
    assert "Assessment load 2 of 5" in page and "App estimate, not a UTS rating" in page and "one task is worth 65% of the marks" in page
    assert page.count("Combination 1") == 1 and "65%" in page and "Group work, marked individually" in page


def test_the_help_page_explains_session_availability(client, log_in):
    log_in()
    page = client.get("/help", follow_redirects=True).get_data(as_text=True)
    assert "<dt>Session availability</dt>" in page and "illustrative</strong> for most subjects" in page and "2027 Handbook</strong> pages" in page
    assert "February, July and December" in page
