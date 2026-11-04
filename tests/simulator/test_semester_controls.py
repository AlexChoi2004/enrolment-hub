import re

import pytest

from accounts.service import create_user
from degree_planner.service import add_to_plan
from enrolment.service import current_session_of, enrol
from shared import db
from simulator.service import (
    SimulatorError, can_roll_back, complete_semester, current_state, period, reset_demo_student, roll_back_semester, rollback_preview,
)
from timetable.service import choose_class, get_timetable

TOKEN = re.compile(r'name="csrf_token" value="([^"]+)"')
AUTUMN = "Autumn 2027"
FOUR = ("31272", "32144", "41026", "41040")  # what John is enrolled in during Autumn 2027


def snap(conn, user=1):
    """Everything a semester touches, without the auto-increment ids."""
    out = {}
    for table, columns in (("enrolments", "subject_code, status, session_label"), ("class_choices", "subject_code, component, class_id"),
                           ("planned_subjects", "subject_code, session_label"),
                           ("subject_attempts", "subject_code, session_label, attempt_number, outcome, mark, grade, source")):
        out[table] = sorted(tuple(r) for r in conn.execute(f"SELECT {columns} FROM {table} WHERE user_id = ?", (user,)))  # noqa: S608
    out["session"] = conn.execute("SELECT current_session FROM users WHERE id = ?", (user,)).fetchone()[0]
    return out


def mixed(*results):
    return {code: {"result": r, "mark": None} for code, r in zip(FOUR, results)}


# --- the log -----------------------------------------------------------------------------------------------------------------------------

def test_there_is_nothing_to_roll_back_at_first(conn):
    assert can_roll_back(conn, 1) is False and rollback_preview(conn, 1) is None
    with pytest.raises(SimulatorError, match="no completed semester to roll back"):
        roll_back_semester(conn, 1)


def test_completing_a_semester_makes_it_possible_to_roll_back(conn):
    complete_semester(conn, 1, mixed("passed", "passed", "passed", "passed"))
    assert can_roll_back(conn, 1) is True


def test_a_failed_completion_logs_nothing(conn):
    with pytest.raises(SimulatorError):
        complete_semester(conn, 1, {"31272": {"result": "passed", "mark": 10}})  # a pass cannot have a mark of 10
    assert can_roll_back(conn, 1) is False and current_session_of(conn, 1) == AUTUMN


# --- the round trip ---------------------------------------------------------------------------------------------------------------------------

def test_rolling_back_puts_everything_exactly_as_it_was(conn):
    before = snap(conn)
    complete_semester(conn, 1, mixed("failed", "none", "passed", "passed"))
    assert snap(conn) != before
    done = roll_back_semester(conn, 1)
    assert snap(conn) == before and done == {"from": "Spring 2027", "to": AUTUMN, "removed_results": 3, "restored": 4, "back_to_plan": 0}


def test_class_choices_and_plan_entries_come_back_too(conn):
    card = [c for c in get_timetable(conn, 1, AUTUMN)["subjects"] if c["code"] == "41026"][0]
    choose_class(conn, 1, "41026", card["components"][0]["options"][0]["id"])
    assert conn.execute("SELECT COUNT(*) FROM class_choices WHERE user_id = 1").fetchone()[0] >= 1
    add_to_plan(conn, 1, "41052", "Spring 2027")
    conn.execute("INSERT OR IGNORE INTO planned_subjects (user_id, subject_code, session_label) VALUES (1, '41040', 'Spring 2027')")
    conn.commit()
    before = snap(conn)
    assert before["planned_subjects"]
    complete_semester(conn, 1, mixed("passed", "passed", "passed", "passed"))
    assert not any(r[0] == "41040" for r in snap(conn)["planned_subjects"])  # a pass removes its plan entry
    roll_back_semester(conn, 1)
    assert snap(conn) == before and ("41040", "Spring 2027") in snap(conn)["planned_subjects"]


def test_a_semester_with_nothing_enrolled_rolls_back_to_the_session(conn):
    reset_demo_student(conn, "fresh")
    complete_semester(conn, 1, {})
    assert current_session_of(conn, 1) == "Spring 2027"
    roll_back_semester(conn, 1)
    assert current_session_of(conn, 1) == AUTUMN and can_roll_back(conn, 1) is False


def test_semesters_roll_back_one_at_a_time_in_reverse_order(conn):
    complete_semester(conn, 1, mixed("passed", "passed", "passed", "passed"))
    after_one = snap(conn)
    complete_semester(conn, 1, {})
    roll_back_semester(conn, 1)
    assert snap(conn) == after_one and current_session_of(conn, 1) == "Spring 2027"
    roll_back_semester(conn, 1)
    assert current_session_of(conn, 1) == AUTUMN and can_roll_back(conn, 1) is False
    with pytest.raises(SimulatorError):
        roll_back_semester(conn, 1)


def test_a_failed_subject_can_be_rolled_back_even_after_a_retake_was_started(conn):
    student = create_user(conn, "retake.student@student.uni.edu.au", "Str0ng#Pass", AUTUMN)["id"]
    enrol(conn, student, "41039", AUTUMN)  # Programming 1 runs in both sessions
    complete_semester(conn, student, {"41039": {"result": "failed", "mark": None}})
    enrol(conn, student, "41039", "Spring 2027")  # the retake
    roll_back_semester(conn, student)
    row = conn.execute("SELECT status, session_label FROM enrolments WHERE user_id = ? AND subject_code = '41039'", (student,)).fetchone()
    assert tuple(row) == ("enrolled", AUTUMN)
    assert conn.execute("SELECT COUNT(*) FROM enrolments WHERE user_id = ? AND subject_code = '41039'", (student,)).fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM subject_attempts WHERE user_id = ?", (student,)).fetchone()[0] == 0


def test_an_enrolment_that_would_be_too_far_ahead_goes_back_into_the_plan(conn):
    complete_semester(conn, 1, mixed("passed", "passed", "passed", "passed"))   # now Spring 2027
    complete_semester(conn, 1, {})                                              # now Autumn 2028
    conn.execute("INSERT INTO enrolments (user_id, subject_code, status, session_label) VALUES (1, '41052', 'enrolled', 'Autumn 2028')")
    conn.commit()
    done = roll_back_semester(conn, 1)  # back to Spring 2027, where Autumn 2028 is two sessions away
    assert done["back_to_plan"] == 1
    assert conn.execute("SELECT COUNT(*) FROM enrolments WHERE user_id = 1 AND subject_code = '41052'").fetchone()[0] == 0
    assert tuple(conn.execute("SELECT session_label FROM planned_subjects WHERE user_id = 1 AND subject_code = '41052'").fetchone()) == ("Autumn 2028",)


def test_rolling_back_is_all_or_nothing(conn):
    complete_semester(conn, 1, mixed("passed", "passed", "passed", "passed"))
    after = snap(conn)
    import json

    log = conn.execute("SELECT id, snapshot FROM semester_log WHERE user_id = 1").fetchone()
    broken = json.loads(log["snapshot"])
    broken["class_choices"].append({"subject_code": "41026", "component": "tutorial", "class_id": 999999})  # a class that does not exist
    conn.execute("UPDATE semester_log SET snapshot = ? WHERE id = ?", (json.dumps(broken), log["id"]))
    conn.commit()
    with pytest.raises(Exception):  # noqa: B017 (an integrity error from the database)
        roll_back_semester(conn, 1)
    assert snap(conn) == after and can_roll_back(conn, 1) is True  # nothing changed and the log is still there


def test_one_students_rollback_never_touches_another(conn):
    other = create_user(conn, "other.student@student.uni.edu.au", "Str0ng#Pass", AUTUMN)["id"]
    complete_semester(conn, other, {})
    complete_semester(conn, 1, mixed("passed", "passed", "passed", "passed"))
    other_before = snap(conn, other)
    roll_back_semester(conn, 1)
    assert snap(conn, other) == other_before and can_roll_back(conn, other) is True and current_session_of(conn, other) == "Spring 2027"


def test_a_reset_clears_the_log(conn):
    complete_semester(conn, 1, mixed("passed", "passed", "passed", "passed"))
    reset_demo_student(conn, "sample")
    assert can_roll_back(conn, 1) is False


def test_the_preview_says_what_will_be_undone(conn):
    complete_semester(conn, 1, mixed("failed", "none", "passed", "passed"))
    preview = rollback_preview(conn, 1)
    assert preview["session"] == AUTUMN and preview["from"] == "Spring 2027"
    assert [(a["subject_code"], a["outcome"]) for a in preview["attempts"]] == [("31272", "failed"), ("41026", "passed"), ("41040", "passed")]
    assert [s["code"] for s in preview["no_result"]] == ["32144"] and len(preview["subjects"]) == 4


def test_the_period_helper_matches_the_state(conn):
    assert period(conn, 1) == {"label": AUTUMN, "year": 3, "semester": 1}
    complete_semester(conn, 1, {})
    assert period(conn, 1) == {"label": "Spring 2027", "year": 3, "semester": 2}


# --- the controls on every page ----------------------------------------------------------------------------------------------------------

def token(client, path="/profile"):
    return TOKEN.search(client.get(path).get_data(as_text=True)).group(1)


def html(client, url):
    return client.get(url, follow_redirects=True).get_data(as_text=True)


def finish(client, **fields):
    return client.post("/simulator/finish", data={"csrf_token": token(client), **{f"result_{c}": "passed" for c in FOUR}, **fields})


PAGES = ["/subjects", "/planner", "/timetable", "/students/me", "/transcript", "/profile", "/help", "/major/MAJ10053", "/submajor/electives"]


@pytest.mark.parametrize("url", PAGES)
def test_the_demo_student_sees_the_three_controls_on_every_page(client, log_in, url):
    log_in()
    page = html(client, url)
    assert 'class="demo-bar"' in page and "Simulation: <strong>Autumn 2027</strong> (Year 3, Semester 1)" in page
    assert ">Complete semester</a>" in page and "Roll back a semester</span>" in page and ">Reset</a>" in page


def test_roll_back_is_greyed_out_until_a_semester_has_been_completed(client, log_in):
    log_in()
    before = html(client, "/planner")
    assert 'class="btn btn-secondary is-disabled"' in before and "rollback" not in before
    finish(client)
    after = html(client, "/planner")
    assert "is-disabled" not in after and 'href="/simulator/rollback"' in after and ">Roll back a semester</a>" in after


def test_the_bar_follows_the_current_session(client, log_in):
    log_in()
    finish(client)
    assert "Simulation: <strong>Spring 2027</strong> (Year 3, Semester 2)" in html(client, "/subjects")


def test_other_students_and_visitors_never_see_the_bar(client, register):
    assert "demo-bar" not in html(client, "/login") and "demo-bar" not in html(client, "/help")
    register()
    for url in ("/planner", "/subjects", "/help"):
        assert "demo-bar" not in html(client, url)


def test_skip_to_next_semester_is_gone_everywhere(client, log_in):
    log_in()
    for url in PAGES + ["/simulator", "/simulator/results", "/simulator/reset"]:
        assert "Skip to next semester" not in html(client, url) and ">Simulator<" not in html(client, url)


def test_finishing_a_semester_lands_on_the_planner(client, log_in):
    log_in()
    res = finish(client)
    assert res.status_code == 303 and res.headers["Location"].endswith("/planner")


def test_resetting_lands_on_the_planner_and_cancel_goes_there_too(client, log_in):
    log_in()
    assert 'href="/planner">Cancel</a>' in html(client, "/simulator/reset")
    res = client.post("/simulator/reset", data={"csrf_token": token(client), "confirm": "yes", "profile": "fresh"})
    assert res.status_code == 303 and res.headers["Location"].endswith("/planner")


# --- the rollback pages --------------------------------------------------------------------------------------------------------------------

def test_the_rollback_page_without_a_completed_semester_says_so(client, log_in):
    log_in()
    res = client.get("/simulator/rollback")
    assert res.status_code == 303 and "no completed semester to roll back" in html(client, "/planner")


def test_the_rollback_page_shows_what_will_be_undone(client, log_in):
    log_in()
    finish(client, result_31272="failed", result_32144="none")
    page = html(client, "/simulator/rollback")
    assert "Roll back a semester</h1>" in page and "undoes the last semester you completed, <strong>Autumn 2027</strong>" in page
    assert "These results will be removed" in page and "31272 Project Management and the Professional" in page and "Failed" in page
    assert "32144 Technology Research Preparation" in page and "Roll back to Autumn 2027" in page


def test_rolling_back_from_the_page_restores_the_semester(app, client, log_in):
    log_in()
    finish(client, result_31272="failed")
    res = client.post("/simulator/rollback", data={"csrf_token": token(client)})
    assert res.status_code == 303 and res.headers["Location"].endswith("/planner")
    conn = db.connect(app.config["DATABASE"])
    assert current_session_of(conn, 1) == AUTUMN and conn.execute("SELECT COUNT(*) FROM subject_attempts WHERE user_id = 1").fetchone()[0] == 16
    conn.close()
    page = html(client, "/planner")
    assert "Rolled back to Autumn 2027: removed 4 result(s) and put 4 subject(s) back as enrolled." in page
    assert "Simulation: <strong>Autumn 2027</strong>" in page and "is-disabled" in page


def test_rolling_back_needs_a_csrf_token_and_changes_nothing_without_one(app, client, log_in):
    log_in()
    finish(client)
    assert client.post("/simulator/rollback", data={}).status_code == 400
    assert client.post("/simulator/rollback", data={"csrf_token": "forged"}).status_code == 400
    conn = db.connect(app.config["DATABASE"])
    assert current_session_of(conn, 1) == "Spring 2027"
    conn.close()


def test_a_second_rollback_with_nothing_left_is_refused_politely(client, log_in):
    log_in()
    finish(client)
    client.post("/simulator/rollback", data={"csrf_token": token(client)})
    client.post("/simulator/rollback", data={"csrf_token": token(client)})
    assert "There is no completed semester to roll back." in html(client, "/planner")


def test_only_the_demo_student_can_roll_back(client, register):
    register()
    assert client.get("/simulator/rollback").status_code == 403
    assert client.post("/simulator/rollback", data={"csrf_token": token(client)}).status_code == 403


def test_the_rollback_pages_need_a_login(client):
    assert client.get("/simulator/rollback").status_code == 302 and client.post("/simulator/rollback", data={}).status_code == 302


def test_the_rollback_pages_are_not_cacheable(client, log_in):
    log_in()
    finish(client)
    assert client.get("/simulator/rollback").headers["Cache-Control"] == "no-store"
