import re

import pytest

from features.accounts.service import create_user
from features.enrolment.results import record_result
from features.enrolment.service import enrol
from features.majors.service import choose_major
from features.submajors.service import choose_submajor
from features.transcript.service import transcript

AUTUMN = "Autumn 2027"
TOKEN = re.compile(r'name="csrf_token" value="([^"]+)"')


@pytest.fixture()
def student(conn):
    user = create_user(conn, "new.student@student.uni.edu.au", "Str0ng#Pass", AUTUMN)["id"]
    choose_major(conn, user, "MAJ03519")
    choose_submajor(conn, user, "SMJ10156")
    return user


def rows(result):
    return [(g["label"], r["code"], r["outcome"], r["attempt"]) for g in result["groups"] for r in g["rows"]]


# --- what the demo student's transcript holds ----------------------------------------------------------------------------

def test_the_transcript_is_grouped_by_session_oldest_first(conn):
    labels = [g["label"] for g in transcript(conn, 1)["groups"]]
    assert labels == ["Autumn 2025", "Spring 2025", "Autumn 2026", "Spring 2026", "Autumn 2027"]


def test_each_session_lists_four_results_with_marks_and_grades(conn):
    first = transcript(conn, 1)["groups"][0]
    assert first["year"] == "2025" and first["season"] == "Autumn" and len(first["rows"]) == 4
    for r in first["rows"]:
        assert r["outcome"] == "Passed" and 50 <= r["mark"] <= 89 and r["grade"] in ("HD", "D", "C", "P") and r["attempt"] == 1


def test_current_subjects_are_shown_as_in_progress_without_a_mark(conn):
    current = transcript(conn, 1)["groups"][-1]
    assert current["label"] == "Autumn 2027"
    assert all(r["outcome"] == "In Progress" and r["mark"] is None and r["grade"] is None for r in current["rows"])


def test_the_totals_count_each_subject_once(conn):
    result = transcript(conn, 1)
    assert result["passed_cp"] == 96 and result["attempt_count"] == 16
    assert result["failed_attempts"] == 0 and result["in_progress"] == 4 and result["retakes"] == []


# --- failing and retaking ----------------------------------------------------------------------------------------------------

def test_a_new_student_has_no_results(conn, student):
    result = transcript(conn, student)
    assert result["groups"] == [] and result["passed_cp"] == 0 and result["attempt_count"] == 0


def test_a_failed_attempt_and_the_later_pass_are_both_kept(conn, student):
    enrol(conn, student, "41039", AUTUMN)
    record_result(conn, student, "41039", AUTUMN, "failed", 44)
    enrol(conn, student, "41039", "Spring 2027")
    record_result(conn, student, "41039", "Spring 2027", "passed", 61)
    assert rows(transcript(conn, student)) == [
        (AUTUMN, "41039", "Failed", 1), ("Spring 2027", "41039", "Passed", 2),
    ]
    result = transcript(conn, student)
    assert result["passed_cp"] == 6 and result["failed_attempts"] == 1 and result["retakes"] == []


def test_a_retake_in_progress_is_shown_with_the_next_attempt_number(conn, student):
    enrol(conn, student, "41039", AUTUMN)
    record_result(conn, student, "41039", AUTUMN, "failed")
    enrol(conn, student, "41039", AUTUMN)
    assert rows(transcript(conn, student)) == [(AUTUMN, "41039", "Failed", 1), (AUTUMN, "41039", "In Progress", 2)]
    assert transcript(conn, student)["retakes"] == ["41039"]


def test_the_transcript_lists_every_attempt_of_a_subject_that_took_three_goes(conn, student):
    for outcome in ("failed", "failed", "passed"):
        enrol(conn, student, "41039", AUTUMN)
        record_result(conn, student, "41039", AUTUMN, outcome)
    assert [r[3] for r in rows(transcript(conn, student))] == [1, 2, 3]


def test_one_students_transcript_never_contains_anothers(conn, student):
    before = transcript(conn, 1)
    record_result(conn, student, "41039", AUTUMN, "failed")
    after = transcript(conn, 1)
    assert after["failed_attempts"] == 0 and rows(after) == rows(before)  # John's own Programming 1 is unchanged


# --- the page ------------------------------------------------------------------------------------------------------------------------

def test_the_results_page_needs_a_login(client):
    res = client.get("/transcript")
    assert res.status_code == 302 and "/login" in res.headers["Location"]


def test_the_page_says_it_is_simulated_data_and_shows_the_table(client, log_in):
    log_in()
    page = client.get("/transcript").get_data(as_text=True)
    assert "Simulated demonstration data" in page and "not genuine UTS academic records" in page
    for heading in ("<th>Code</th>", "<th>Mark</th>", "<th>Grade</th>", "<th>Outcome</th>", "<th>Attempt</th>"):
        assert heading in page
    assert "Autumn 2025" in page and "Programming 1" in page and "96 credit points passed" in page


def test_the_page_distinguishes_passed_and_in_progress(client, log_in):
    log_in()
    page = client.get("/transcript").get_data(as_text=True)
    assert 'st-completed">Passed' in page and 'st-enrolled">In Progress' in page and "Failed</span>" not in page


def test_a_failed_result_is_shown_with_the_failed_badge_and_a_retake_note(app, client):
    from shared import db

    conn = db.connect(app.config["DATABASE"])
    user = create_user(conn, "failed.student@student.uni.edu.au", "Str0ng#Pass", AUTUMN)["id"]
    choose_major(conn, user, "MAJ03519")
    record_result(conn, user, "41039", AUTUMN, "failed", 30)
    conn.close()
    token = TOKEN.search(client.get("/login").get_data(as_text=True)).group(1)
    client.post("/login", data={"email": "failed.student@student.uni.edu.au", "password": "Str0ng#Pass", "csrf_token": token})
    page = client.get("/transcript").get_data(as_text=True)
    assert 'st-retake">Failed' in page and ">FL<" in page.replace(" ", "") and "Retake needed: 41039" in page


def test_a_student_with_no_results_sees_a_message(client, register):
    register()
    assert "No results yet" in client.get("/transcript").get_data(as_text=True)


def test_the_page_is_not_cacheable(client, log_in):
    log_in()
    assert client.get("/transcript").headers["Cache-Control"] == "no-store"


def test_the_navigation_lists_results_after_record_only_when_logged_in(client, log_in):
    assert "Results" not in client.get("/").get_data(as_text=True)
    log_in()
    page = client.get("/subjects").get_data(as_text=True)
    assert page.index(">Record<") < page.index(">Results<") < page.index(">Profile<")


# --- newest first ----------------------------------------------------------------------------------------------------------------------

def test_the_service_can_list_newest_first(conn):
    oldest = [g["label"] for g in transcript(conn, 1)["groups"]]
    newest = [g["label"] for g in transcript(conn, 1, newest_first=True)["groups"]]
    assert newest == list(reversed(oldest)) and newest[0] == "Autumn 2027"


def test_the_page_shows_the_latest_session_at_the_top_by_default(client, log_in):
    log_in()
    page = client.get("/transcript").get_data(as_text=True).split("<main", 1)[1]  # the page body, below the header and simulation bar
    assert page.index("Autumn 2027") < page.index("Spring 2026") < page.index("Autumn 2025")
    assert "Newest session first" in page and "Show oldest first" in page


def test_the_page_can_show_oldest_first(client, log_in):
    log_in()
    page = client.get("/transcript?order=oldest").get_data(as_text=True).split("<main", 1)[1]
    assert page.index("Autumn 2025") < page.index("Spring 2026") < page.index("Autumn 2027")
    assert "Oldest session first" in page and "Show newest first" in page


def test_an_unknown_order_falls_back_to_newest_first(client, log_in):
    log_in()
    page = client.get("/transcript?order=sideways").get_data(as_text=True).split("<main", 1)[1]
    assert page.index("Autumn 2027") < page.index("Autumn 2025")
