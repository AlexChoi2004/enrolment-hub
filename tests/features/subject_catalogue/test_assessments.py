import re

import pytest

from shared import db
from features.subject_catalogue.assessments import (
    NO_BREAKDOWN,
    NOT_ENOUGH,
    ai_context,
    assessment_info,
    explain,
    load_assessment_info,
    replace_structure,
)
from features.subject_catalogue.seed import seed_assessments

UNVERIFIED = ["40007", "41759", "43030", "43036", "43037", "68746"]
HISTORICAL = ["32009", "41020"]
TOKEN = re.compile(r'name="csrf_token" value="([^"]+)"')


def count(conn, sql, *args):
    return conn.execute(sql, args).fetchone()[0]


# --- the stored data -----------------------------------------------------------------------------------------

def test_every_subject_has_exactly_one_current_structure_and_the_researched_ones_have_a_description(conn):
    subjects = count(conn, "SELECT COUNT(*) FROM subjects")
    assert subjects == 181
    assert count(conn, "SELECT COUNT(*) FROM subject_descriptions") == 105  # the 76 sub-major-only subjects are not researched yet
    assert count(conn, "SELECT COUNT(*) FROM assessment_structures WHERE is_current = 1") == subjects
    assert count(conn, "SELECT COUNT(DISTINCT subject_code) FROM assessment_structures WHERE is_current = 1") == subjects


def test_the_verification_labels_are_split_as_expected(conn):
    counts = dict(conn.execute("SELECT verification, COUNT(*) FROM assessment_structures GROUP BY verification").fetchall())
    assert counts == {"indicative": 85, "historical": 2, "unverified": 6 + 76, "synthetic": 12}


def test_the_weights_of_every_structure_with_tasks_add_up_to_100(conn):
    rows = conn.execute(
        "SELECT s.subject_code, COALESCE(SUM(a.weight), 0) AS total FROM assessment_structures s"
        " JOIN assessments a ON a.structure_id = s.id GROUP BY s.id"
    ).fetchall()
    assert len(rows) == 99  # the 85 indicative, 2 historical and 12 sample ones; every unverified structure has no tasks
    assert [r["subject_code"] for r in rows if r["total"] != 100] == []


@pytest.mark.parametrize("code", UNVERIFIED)
def test_unverified_subjects_have_no_assessment_tasks_at_all(conn, code):
    structure = conn.execute("SELECT id, verification FROM assessment_structures WHERE subject_code = ?", (code,)).fetchone()
    assert structure["verification"] == "unverified"
    assert count(conn, "SELECT COUNT(*) FROM assessments WHERE structure_id = ?", structure["id"]) == 0


def test_the_two_historical_structures_are_marked_2024_with_a_warning_note(conn):
    for code in HISTORICAL:
        s = conn.execute("SELECT * FROM assessment_structures WHERE subject_code = ?", (code,)).fetchone()
        assert s["verification"] == "historical" and s["academic_year"] == 2024
        assert "Verify the 2027 assessment structure" in s["note"]


def test_the_supplied_historical_assessments_are_stored_exactly(conn):
    def tasks(code):
        return [tuple(r) for r in conn.execute(
            "SELECT a.name, a.weight, a.groupwork FROM assessments a JOIN assessment_structures s ON s.id = a.structure_id"
            " WHERE s.subject_code = ? ORDER BY a.position", (code,))]
    assert tasks("32009") == [
        ("Weekly chapter online tests", 10, "individual"), ("Mid-semester quiz", 20, "individual"),
        ("Skills-based practical assessment", 30, "individual"), ("End-of-semester quiz", 40, "individual"),
    ]
    assert tasks("41020") == [
        ("Quiz", 10, "individual"), ("Interview research poster", 30, "group_individual"),
        ("Probe design report", 10, "individual"), ("Research paper and video on probe study", 50, "individual"),
    ]


def test_the_supplied_descriptions_are_stored_as_given(conn):
    text = conn.execute("SELECT description FROM subject_descriptions WHERE subject_code = '41759'").fetchone()[0]
    assert text.startswith("A culminating project subject")
    assert "OSPF, EIGRP and BGP" in conn.execute(
        "SELECT description FROM subject_descriptions WHERE subject_code = '32009'").fetchone()[0]


def test_descriptions_live_apart_from_assessments(conn):
    conn.execute("DELETE FROM assessments")
    conn.commit()
    assert count(conn, "SELECT COUNT(*) FROM subject_descriptions") == 105
    assert assessment_info(conn, "41039")["summary"]  # the description survives; the tasks are gone
    assert assessment_info(conn, "41039")["status"] == "none"


def test_a_mandatory_task_with_no_marks_is_stored_without_a_weight(conn):
    info = assessment_info(conn, "41039")  # Programming 1 has a mandatory Extension task
    extension = [t for t in info["tasks"] if t["name"] == "Extension"][0]
    assert extension["weight"] is None and extension["weight_text"] == "Mandatory, no marks"
    assert info["total_weight"] == 100


def test_due_weeks_are_stored_but_always_labelled_illustrative(conn):
    assert count(conn, "SELECT COUNT(*) FROM assessments WHERE due_week IS NOT NULL AND due_week_source <> 'illustrative'") == 0
    assert count(conn, "SELECT COUNT(*) FROM assessments WHERE due_week IS NULL") == 0  # every stored task has an illustrative week
    assert count(conn, "SELECT COUNT(*) FROM assessments WHERE due_week < 2 OR due_week > 14") == 0


def test_the_database_refuses_a_bad_type_group_or_weight(conn):
    sid = count(conn, "SELECT id FROM assessment_structures LIMIT 1")
    for type_, group, weight in [("nonsense", "individual", 10), ("quiz", "nonsense", 10), ("quiz", "individual", 101)]:
        with pytest.raises(Exception, match="CHECK"):
            conn.execute(
                "INSERT INTO assessments (structure_id, position, name, description, type, weight, groupwork)"
                " VALUES (?, 99, 'x', 'x', ?, ?, ?)", (sid, type_, weight, group))
        conn.rollback()


def test_the_database_refuses_an_unknown_verification_label(conn):
    with pytest.raises(Exception, match="CHECK"):
        conn.execute("INSERT INTO assessment_structures (subject_code, source, verification) VALUES ('41039', 's', 'sure')")


def test_seeding_twice_adds_nothing(conn):
    before = [count(conn, f"SELECT COUNT(*) FROM {t}") for t in ("subject_descriptions", "assessment_structures", "assessments")]
    seed_assessments(conn)
    conn.commit()
    assert [count(conn, f"SELECT COUNT(*) FROM {t}") for t in ("subject_descriptions", "assessment_structures", "assessments")] == before


def test_every_task_has_a_short_explanation(conn):
    assert count(conn, "SELECT COUNT(*) FROM assessments WHERE description = ''") == 0
    assert explain("exam", "individual") == "A timed exam covering the subject."
    assert explain("project", "group_individual").endswith("Done as a team, with individual marks.")


# --- what a student is shown -------------------------------------------------------------------------------------

def test_handbook_information_is_labelled_indicative_with_its_source_and_date(conn):
    info = assessment_info(conn, "41039")
    assert info["status"] == "indicative"
    assert info["banner"].startswith("Source: UTS Handbook (handbook.uts.edu.au) (indicative), retrieved 2 Nov 2026.")
    assert "Check your subject outline" in info["banner"]
    assert [t["name"] for t in info["tasks"]][:2] == ["Lab Assessments", "Code Comprehension"]


def test_group_and_exam_shares_are_worked_out_from_the_tasks(conn):
    programming_1 = assessment_info(conn, "41039")
    assert (programming_1["group_weight"], programming_1["exam_weight"]) == (0, 20)
    software = assessment_info(conn, "41026")  # three team releases of 20, 30 and 30
    assert (software["group_weight"], software["exam_weight"]) == (80, 0)


def test_historical_information_says_it_may_have_changed(conn):
    info = assessment_info(conn, "32009")
    assert info["status"] == "historical"
    assert "Historical information from 2024" in info["banner"] and "may have changed" in info["banner"]


@pytest.mark.parametrize("code", UNVERIFIED)
def test_a_subject_without_a_breakdown_says_there_is_none(conn, code):
    info = assessment_info(conn, code)
    assert info["status"] == "none" and info["tasks"] == [] and info["banner"] == NO_BREAKDOWN
    assert "find out when you enrol" in NO_BREAKDOWN


def test_the_student_reported_tasks_for_43030_are_never_exposed(conn):
    info = assessment_info(conn, "43030")
    shown = repr({k: v for k, v in info.items() if k != "internal_note"})
    assert "job advertisement" not in shown.lower() and "portfolio" not in shown.lower()
    assert "student-reported" in info["internal_note"]  # kept for whoever verifies it later


def test_style_tags_are_readable_labels(conn):
    assert assessment_info(conn, "41039")["tags"] == ["Code-based"]
    assert "Group work" in assessment_info(conn, "41026")["tags"]
    assert assessment_info(conn, "41759")["tags"] == []  # nothing is guessed for an unverified subject


# --- what the AI features may use --------------------------------------------------------------------------------

@pytest.mark.parametrize("code", UNVERIFIED)
def test_the_ai_says_not_enough_context_for_an_unconfirmed_subject(conn, code):
    context = ai_context(conn, code)
    assert context["assessments_known"] is False
    assert context["text"].startswith(NOT_ENOUGH)
    assert "%" not in context["text"]  # no weightings of any kind


def test_the_ai_never_receives_the_unconfirmed_43030_tasks(conn):
    text = ai_context(conn, "43030")["text"].lower()
    assert "job advertisement" not in text and "skills audit" not in text and "development portfolio" not in text
    assert "professional standards" in text  # the supplied description is still available


def test_the_ai_gets_the_tasks_and_a_caveat_for_indicative_information(conn):
    context = ai_context(conn, "41039")
    assert context["assessments_known"] is True and context["status"] == "indicative"
    assert "Exam (20%, individual, exam, due week 14 (illustrative))" in context["text"] and "subject outline is authoritative" in context["text"]


def test_the_ai_is_told_historical_information_is_unconfirmed(conn):
    context = ai_context(conn, "41020")
    assert context["assessments_known"] is True and context["status"] == "historical"
    assert "Historical information from 2024" in context["text"] and "unconfirmed" in context["text"]
    assert "Interview research poster (30%, group work, marked individually" in context["text"]


def test_an_unknown_subject_is_not_enough_context(conn):
    assert ai_context(conn, "00000")["text"].startswith(NOT_ENOUGH)


# --- updating when an official outline arrives --------------------------------------------------------------------

NEW_TASKS = [("Quiz", "quiz", "individual", 20), ("Project", "project", "group", 50), ("Exam", "exam", "individual", 30)]


def test_a_new_official_outline_replaces_the_current_structure_and_keeps_the_old_one(conn):
    replace_structure(conn, "41759", NEW_TASKS, source="UTS subject outline", year=2027, session="Autumn")
    info = assessment_info(conn, "41759")
    assert info["status"] == "verified_current" and [t["name"] for t in info["tasks"]] == ["Quiz", "Project", "Exam"]
    assert "verified against the official outline" in info["banner"]
    assert count(conn, "SELECT COUNT(*) FROM assessment_structures WHERE subject_code = '41759'") == 2
    assert count(conn, "SELECT COUNT(*) FROM assessment_structures WHERE subject_code = '41759' AND is_current = 1") == 1


def test_once_verified_the_ai_can_use_it(conn):
    replace_structure(conn, "41759", NEW_TASKS, source="UTS subject outline", year=2027)
    context = ai_context(conn, "41759")
    assert context["assessments_known"] is True and "Verified against the official subject outline" in context["text"]


def test_updating_a_historical_subject_shows_the_new_year(conn):
    replace_structure(conn, "32009", NEW_TASKS, source="UTS subject outline", year=2027)
    info = assessment_info(conn, "32009")
    assert info["status"] == "verified_current" and info["year"] == 2027


def test_a_new_structure_must_add_up_and_use_known_values(conn):
    with pytest.raises(ValueError, match="add up to 100"):
        replace_structure(conn, "41759", [("Quiz", "quiz", "individual", 60)], source="x")
    with pytest.raises(ValueError, match="Unknown assessment type"):
        replace_structure(conn, "41759", [("Quiz", "nonsense", "individual", 100)], source="x")
    with pytest.raises(ValueError, match="Unknown groupwork"):
        replace_structure(conn, "41759", [("Quiz", "quiz", "nope", 100)], source="x")
    assert assessment_info(conn, "41759")["status"] == "none"  # nothing was changed


def test_loading_all_assessment_information_covers_every_subject(conn):
    assert len(load_assessment_info(conn)) == 181


# --- the pages ------------------------------------------------------------------------------------------------------

def html(client, url):
    return client.get(url, follow_redirects=True).get_data(as_text=True)


def card(page, code):
    start = page.rindex("<details", 0, page.index(f'<span class="code">{code}</span>'))
    return page[start: page.index("</details>", start)]


def choose_major(client, code):
    token = TOKEN.search(client.get("/subjects").get_data(as_text=True)).group(1)
    client.post(f"/major/{code}/choose", data={"csrf_token": token})


def test_a_subject_shows_its_description_tags_and_assessment_table(client, log_in):
    log_in()
    page = card(html(client, "/subjects"), "41039")
    assert "Learn core programming with Java" in page and "Code-based" in page
    assert "<h3>Assessment</h3>" in page and "Lab Assessments" in page and "30%" in page
    assert "Individual" in page and "Mandatory, no marks" in page
    assert "Source: UTS Handbook (handbook.uts.edu.au) (indicative), retrieved 2 Nov 2026." in page
    assert "Group work counts for 0% of the marks and exams for 20%." in page


def test_each_task_has_a_short_explanation_on_the_page(client, log_in):
    log_in()
    assert "A timed exam covering the subject." in card(html(client, "/subjects"), "41039")


def test_a_group_assessment_is_labelled(client, log_in):
    log_in()
    page = card(html(client, "/subjects"), "41026")
    assert "Group work, marked individually" in page and "Project Release 1" in page


def test_an_unverified_subject_says_there_is_no_breakdown_and_shows_no_table(client, log_in):
    log_in()
    page = card(html(client, "/subjects"), "41759")  # Capstone
    assert "No assessment breakdown has been published yet" in page and "find out when you enrol" in page
    assert "<table" not in page and "Source:" not in page
    assert "A culminating project subject" in page  # the description is still shown


def test_unconfirmed_tasks_for_43030_are_not_shown_to_students(client, log_in):
    log_in()
    page = card(html(client, "/subjects"), "43030")
    assert "No assessment breakdown has been published yet" in page
    assert "job advertisement" not in page.lower() and "development portfolio" not in page.lower()


def test_a_historical_subject_is_shown_with_a_warning(client, register):
    register()
    choose_major(client, "MAJ03445")
    page = card(html(client, "/subjects"), "32009")
    assert "Historical information from 2024" in page and "Weekly chapter online tests" in page
    assert "Source: UTS Handbook" not in page and "(indicative)" not in page


def test_the_detail_page_shows_the_same_information(client, log_in):
    log_in()
    page = html(client, "/subjects/41039")
    assert "Lab Assessments" in page and "(indicative)" in page


def test_a_student_cannot_see_unverified_data_as_confirmed(client, log_in):
    log_in()
    page = html(client, "/subjects")
    assert "verified against the official outline" not in page  # nothing is verified-current yet


def test_the_new_sub_major_subjects_have_no_confirmed_assessment_information(conn):
    for code in ("37242", "97101", "48080"):
        info = assessment_info(conn, code)
        assert info["status"] == "none" and info["tasks"] == []
        assert ai_context(conn, code)["text"].startswith(NOT_ENOUGH)


def test_the_sample_electives_are_labelled_as_invented(conn):
    for code in [f"SYN{n}" for n in range(101, 113)]:
        info = assessment_info(conn, code)
        assert info["status"] == "synthetic" and "invented" in info["banner"]


def test_the_ai_is_told_sample_data_is_invented(conn):
    assert "invented" in ai_context(conn, "SYN101")["text"]


def test_a_sample_elective_says_it_is_invented(client, register):
    register()
    token_ = TOKEN.search(client.get("/subjects").get_data(as_text=True)).group(1)
    client.post("/submajor/electives/choose", data={"csrf_token": token_})
    page = card(html(client, "/subjects"), "SYN101")
    assert "Sample data invented for this prototype" in page
