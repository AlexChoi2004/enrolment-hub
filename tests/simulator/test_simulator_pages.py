import re

import pytest

from shared import db

TOKEN = re.compile(r'name="csrf_token" value="([^"]+)"')


def token(client, path="/simulator/results"):
    return TOKEN.search(client.get(path).get_data(as_text=True)).group(1)


def html(client, url):
    return client.get(url, follow_redirects=True).get_data(as_text=True)


def review(client, mode="complete", **fields):
    return client.post("/simulator/review", data={"csrf_token": token(client), "mode": mode, **fields})


def finish(client, **fields):
    return client.post("/simulator/finish", data={"csrf_token": token(client), **fields})


ALL_PASSED = {"result_41026": "passed", "result_31272": "passed", "result_32144": "passed", "result_41040": "passed"}
ONE_FAILED = {**ALL_PASSED, "result_41026": "failed"}
NONE = {f"result_{c}": "none" for c in ("41026", "31272", "32144", "41040")}


def state(app):
    conn = db.connect(app.config["DATABASE"])
    try:
        return (
            conn.execute("SELECT current_session FROM users WHERE id = 1").fetchone()[0],
            conn.execute("SELECT COUNT(*) FROM subject_attempts WHERE user_id = 1").fetchone()[0],
        )
    finally:
        conn.close()


# --- who can use it ----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("url", ["/simulator", "/simulator/results", "/simulator/reset"])
def test_anonymous_visitors_are_sent_to_login(client, url):
    res = client.get(url)
    assert res.status_code == 302 and "/login" in res.headers["Location"]


@pytest.mark.parametrize("url", ["/simulator/review", "/simulator/finish", "/simulator/reset"])
def test_anonymous_visitors_cannot_post(client, url):
    res = client.post(url, data={})
    assert res.status_code == 302 and "/login" in res.headers["Location"]


def test_only_the_demo_student_can_use_the_simulator(client, register):
    register()  # an ordinary new account
    for url in ("/simulator", "/simulator/results", "/simulator/reset"):
        assert client.get(url).status_code == 403
    assert client.post("/simulator/finish", data={"csrf_token": "x"}).status_code == 403
    assert client.post("/simulator/reset", data={"csrf_token": "x", "confirm": "yes"}).status_code == 403


def test_the_nav_and_planner_buttons_appear_only_for_the_demo_student(client, register):
    register()
    assert ">Simulator<" not in html(client, "/subjects") and "Complete semester" not in html(client, "/planner")


def test_the_demo_student_sees_the_simulation_bar_instead_of_a_nav_link(client, log_in):
    log_in()
    assert ">Simulator<" not in html(client, "/subjects")
    page = html(client, "/planner")
    assert "Year 3, Semester 1" in page and "Complete semester" in page and "Skip to next semester" not in page


def test_posts_need_a_csrf_token(app, client, log_in):
    log_in()
    assert client.post("/simulator/review", data={}).status_code == 400
    assert client.post("/simulator/finish", data={"csrf_token": "forged", **ALL_PASSED}).status_code == 400
    assert client.post("/simulator/reset", data={"confirm": "yes"}).status_code == 400
    assert state(app) == ("Autumn 2027", 16)


def test_the_pages_are_not_cacheable(client, log_in):
    log_in()
    assert client.get("/simulator").headers["Cache-Control"] == "no-store"


# --- the screens -----------------------------------------------------------------------------------------------------------------

def test_the_dashboard_shows_the_period_and_the_subjects(client, log_in):
    log_in()
    page = html(client, "/simulator")
    assert "Year 3, Semester 1" in page and "Autumn 2027" in page and "41026 Advanced Software Development" in page
    assert "Complete semester" in page and "Skip to next semester" in page and "Simulated" in page or "simulated" in page


def test_complete_defaults_every_subject_to_passed(client, log_in):
    log_in()
    assert html(client, "/simulator/results").count('<option value="passed" selected>') == 4
    assert html(client, "/simulator/results?mode=skip").count('<option value="passed" selected>') == 4  # an old Skip link is just Complete


def test_the_results_screen_offers_passed_failed_and_no_result_for_every_subject(client, log_in):
    log_in()
    page = html(client, "/simulator/results")
    for label in ("Passed", "Failed", "No result yet"):
        assert page.count(f">{label}</option>") == 4
    assert 'name="mark_41026"' in page and "Review" in page


def test_the_review_screen_lists_what_will_be_saved_and_asks_for_confirmation(client, log_in):
    log_in()
    res = review(client, **ONE_FAILED, mark_31272="88")
    page = res.get_data(as_text=True)
    assert res.status_code == 200 and "Check before saving" in page and "Spring 2027" in page
    assert "Confirm and save" in page and "88" in page and "automatic" in page
    assert 'name="result_41026" value="failed"' in page


def test_nothing_is_saved_until_the_confirmation(app, client, log_in):
    log_in()
    review(client, **ONE_FAILED)
    assert state(app) == ("Autumn 2027", 16)


def test_a_bad_mark_sends_the_student_back_with_the_problem(app, client, log_in):
    log_in()
    res = review(client, **ALL_PASSED, mark_41026="40")
    assert res.status_code == 400 and "A mark of 40 is a fail" in res.get_data(as_text=True)
    res = review(client, **ALL_PASSED, mark_41026="abc")
    assert res.status_code == 400 and "whole number from 0 to 100" in res.get_data(as_text=True)
    assert state(app) == ("Autumn 2027", 16)


def test_the_screens_say_the_data_is_simulated(client, log_in):
    log_in()
    assert "not genuine UTS academic records" in html(client, "/simulator/results")


# --- finishing a semester ---------------------------------------------------------------------------------------------------------

def test_confirming_saves_the_results_and_advances(app, client, log_in):
    log_in()
    res = finish(client, **ONE_FAILED)
    assert res.status_code == 303 and res.headers["Location"].endswith("/planner")  # back to where the student works
    assert state(app) == ("Spring 2027", 20)
    page = html(client, "/planner")
    assert "Autumn 2027 finished: 3 passed, 1 failed, 0 with no result." in page and "Year 3, Semester 2" in page


def test_the_whole_app_reacts_to_a_failed_subject(client, log_in):
    log_in()
    finish(client, **ONE_FAILED)
    assert "Failed" in html(client, "/transcript") and "41026" in html(client, "/transcript")
    planner = html(client, "/planner")
    assert "Failed, retake needed 1" in planner and "Add retake to plan" in planner and "Year 3, Semester 2" in planner
    assert "Failed: retake needed" in html(client, "/subjects")
    assert "Spring 2027" in html(client, "/timetable") and "Autumn 2027" not in html(client, "/timetable").split("tt-tabs")[1][:400] if "tt-tabs" in html(client, "/timetable") else True


def test_choosing_no_result_for_everything_records_nothing(app, client, log_in):
    log_in()
    finish(client, **NONE)
    assert state(app) == ("Spring 2027", 16)  # the session moved on; no attempts were invented
    assert "0 passed, 0 failed, 4 with no result" in html(client, "/planner")


def test_the_record_and_profile_show_the_new_period(client, log_in):
    log_in()
    finish(client, **ALL_PASSED)
    assert "Year 3" in html(client, "/students/me") and "Spring 2027" in html(client, "/students/me")
    assert "Spring 2027" in html(client, "/profile")


def test_a_stranded_plan_is_shown_with_the_needs_rescheduling_section(client, log_in):
    log_in()
    t = token(client, "/planner")
    client.post("/planner/add", data={"subject_code": "41052", "session_label": "Spring 2027", "csrf_token": t})
    finish(client, **ALL_PASSED)  # now in Spring 2027, where it is planned
    client.post("/simulator/finish", data={"csrf_token": token(client)})  # on to Autumn 2028: Spring 2027 has passed
    page = html(client, "/planner")
    assert "Needs rescheduling" in page and "which has passed" in page


def test_finishing_twice_in_a_row_moves_two_sessions(app, client, log_in):
    log_in()
    finish(client, **ALL_PASSED)
    page = html(client, "/simulator")
    assert "Year 3, Semester 2" in page and "not enrolled in anything this session" in page
    client.post("/simulator/finish", data={"csrf_token": token(client)})
    assert state(app)[0] == "Autumn 2028"


# --- reset -----------------------------------------------------------------------------------------------------------------------------

def test_the_reset_page_asks_for_confirmation(client, log_in):
    log_in()
    page = html(client, "/simulator/reset")
    assert "I understand this removes everything I have simulated" in page and "does not touch any other account" in page


def test_reset_without_the_tick_does_nothing(app, client, log_in):
    log_in()
    finish(client, **ONE_FAILED)
    client.post("/simulator/reset", data={"csrf_token": token(client)})
    assert state(app) == ("Spring 2027", 20)
    assert "Tick the box to confirm the reset" in html(client, "/simulator/reset")


def test_reset_with_the_tick_restores_the_seeded_records(app, client, log_in):
    log_in()
    finish(client, **ONE_FAILED)
    client.post("/simulator/reset", data={"csrf_token": token(client), "confirm": "yes", "profile": "sample"})
    assert state(app) == ("Autumn 2027", 16)
    assert "Simulation reset: Two years in, halfway through the major." in html(client, "/planner")
    assert "Year 3, Semester 1" in html(client, "/simulator")
