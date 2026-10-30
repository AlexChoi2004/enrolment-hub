import re

import pytest

from accounts.seed import DEMO_EMAIL, DEMO_PASSWORD
from app import create_app
from shared import db

TOKEN = re.compile(r'name="csrf_token" value="([^"]+)"')


def sign_in(client, email=DEMO_EMAIL, password=DEMO_PASSWORD):
    token = TOKEN.search(client.get("/login").get_data(as_text=True)).group(1)
    client.post("/login", data={"email": email, "password": password, "csrf_token": token})
    return client


def token_for(client, path="/planner"):
    return TOKEN.search(client.get(path).get_data(as_text=True)).group(1)


def post(client, url, **data):
    data.setdefault("csrf_token", token_for(client))
    return client.post(url, data=data)


def page(client):
    return client.get("/planner").get_data(as_text=True)


def planned_rows(app, user_id=1):
    conn = db.connect(app.config["DATABASE"])
    try:
        return {r["subject_code"]: r["session_label"] for r in conn.execute(
            "SELECT subject_code, session_label FROM planned_subjects WHERE user_id = ?", (user_id,))}
    finally:
        conn.close()


@pytest.fixture()
def demo(app, client):
    return sign_in(client)


def new_student(tmp_path):
    client = create_app({"DATABASE": str(tmp_path / "n.db"), "TESTING": True, "SECRET_KEY": "k"}).test_client()
    token = TOKEN.search(client.get("/register").get_data(as_text=True)).group(1)
    client.post("/register", data={"email": "new.student@student.uni.edu.au", "password": "Str0ng#Pass",
                                   "confirm_password": "Str0ng#Pass", "csrf_token": token})
    return client


# --- access control ---------------------------------------------------------------------------------

def test_anonymous_visitors_are_sent_to_login(client):
    res = client.get("/planner")
    assert res.status_code == 302 and "next=/planner" in res.headers["Location"]


@pytest.mark.parametrize("url", ["/planner/add", "/planner/move/41052", "/planner/remove/41052", "/planner/suggest", "/planner/clear"])
def test_anonymous_visitors_cannot_change_a_plan(app, client, url):
    res = client.post(url, data={"subject_code": "41052", "session_label": "Spring 2028"})
    assert res.status_code == 302 and "/login" in res.headers["Location"]
    assert planned_rows(app) == {}


@pytest.mark.parametrize("url", ["/planner/add", "/planner/move/41052", "/planner/remove/41052", "/planner/suggest", "/planner/clear"])
def test_changes_must_be_posted_with_a_csrf_token(app, demo, url):
    assert demo.get(url).status_code == 405
    res = demo.post(url, data={"subject_code": "41052", "session_label": "Spring 2028"})
    assert res.status_code == 400
    assert planned_rows(app) == {}


def test_the_form_cannot_name_another_student(app, demo):
    post(demo, "/planner/add", subject_code="41052", session_label="Spring 2028", user_id="2")
    assert planned_rows(app) == {"41052": "Spring 2028"}  # went to the signed-in student (id 1)
    assert planned_rows(app, user_id=2) == {}


def test_malformed_subject_codes_return_400(demo):
    assert post(demo, "/planner/add", subject_code="bad!code", session_label="Spring 2028").status_code == 400
    assert post(demo, "/planner/remove/bad!code").status_code == 400
    assert post(demo, "/planner/move/bad!code", session_label="Spring 2028").status_code == 400


def test_the_page_is_not_cacheable(demo):
    assert demo.get("/planner").headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("evil", ["//evil.example", "https://evil.example"])
def test_changes_always_return_to_the_planner(demo, evil):
    res = post(demo, "/planner/add", subject_code="41052", session_label="Spring 2028", next=evil)
    assert res.status_code == 303 and res.headers["Location"].endswith("/planner")


# --- create, update, delete -----------------------------------------------------------------------------

def test_adding_a_subject_confirms_it(app, demo):
    res = post(demo, "/planner/add", subject_code="41052", session_label="Spring 2028")
    assert res.status_code == 303
    assert planned_rows(app) == {"41052": "Spring 2028"}
    assert "Added 41052 Advanced Algorithms to your plan for Spring 2028." in page(demo)


def test_a_refused_add_explains_why(app, demo):
    post(demo, "/planner/add", subject_code="SYN102", session_label="Autumn 2028")
    assert planned_rows(app) == {}
    assert "General electives requirement would be exceeded" in page(demo)


def test_moving_and_removing_through_the_pages(app, demo):
    post(demo, "/planner/add", subject_code="31260", session_label="Spring 2028")
    post(demo, "/planner/move/31260", session_label="Autumn 2028")
    assert planned_rows(app) == {"31260": "Autumn 2028"}
    assert "Moved 31260 Fundamentals of Interaction Design to Autumn 2028." in page(demo)
    post(demo, "/planner/remove/31260")
    assert planned_rows(app) == {}
    assert "Removed 31260 Fundamentals of Interaction Design from your plan." in page(demo)


def test_removing_something_a_planned_subject_needs_is_refused(tmp_path):
    client = new_student(tmp_path)
    post(client, "/planner/add", subject_code="41039", session_label="Autumn 2027")
    post(client, "/planner/add", subject_code="48024", session_label="Spring 2027")
    post(client, "/planner/remove/41039")
    html = page(client)
    assert "Can&#39;t remove 41039 Programming 1" in html or "Can't remove 41039 Programming 1" in html
    assert "48024 Programming 2 is planned for Spring 2027" in html


def test_suggest_and_clear_through_the_pages(app, demo):
    post(demo, "/planner/suggest")
    assert len(planned_rows(app)) == 11
    html = page(demo)
    assert "Added 11 subjects to your plan." in html
    assert "Your plan covers every requirement of the degree." in html
    post(demo, "/planner/suggest")
    assert "Nothing to add" in page(demo)
    post(demo, "/planner/clear")
    assert planned_rows(app) == {}
    assert "Cleared your plan (11 planned subjects)." in page(demo)


# --- what the page shows ------------------------------------------------------------------------------------

def test_the_page_shows_sessions_loads_and_enrolled_subjects(demo):
    html = page(demo)
    assert "Plan by session" in html and "Still to plan" in html
    assert "24 of 24 credit points" in html
    assert html.count('class="badge st-enrolled">Enrolled') == 4
    assert "96 cp completed" in html and "72 cp still to plan" in html


def test_outstanding_subjects_get_an_add_form(demo):
    html = page(demo)
    assert html.count('action="/planner/add"') >= 9
    assert 'aria-label="Plan 32931 for"' in html


def test_elective_choices_are_listed_when_still_needed(demo):
    html = page(demo)
    assert "Major electives: choose 2 more" in html
    assert "General electives: choose" not in html  # the demo student has finished those


def test_planned_subjects_can_be_moved_and_removed(demo):
    post(demo, "/planner/add", subject_code="31260", session_label="Spring 2028")
    html = page(demo)
    assert 'class="badge st-planned">Planned' in html
    assert 'action="/planner/move/31260"' in html and 'action="/planner/remove/31260"' in html


def test_a_plan_that_has_gone_stale_is_highlighted(demo):
    post(demo, "/planner/add", subject_code="32931", session_label="Spring 2027")
    token = token_for(demo)
    demo.post("/students/me/withdraw/32144", data={"csrf_token": token, "next": "/planner"})
    html = page(demo)
    assert "plan-problem" in html and "Problems with your plan" in html
    assert "Needs 32144" in html


def test_a_new_student_starts_with_an_empty_plan_and_a_suggest_button(tmp_path):
    client = new_student(tmp_path)
    html = page(client)
    assert "Suggest a plan" in html and "Clear plan" not in html
    assert html.count("Nothing planned.") == 10
    assert "192 cp still to plan" in html
    post(client, "/planner/suggest")
    html = page(client)
    assert "Added 31 subjects to your plan." in html
    assert "Clear plan" in html and "0 cp still to plan" in html


def test_each_student_only_sees_their_own_plan(tmp_path):
    client = new_student(tmp_path)
    post(client, "/planner/suggest")
    assert "John Doe" not in page(client)
    assert 'class="badge st-enrolled">Enrolled' not in page(client)


# --- navigation -----------------------------------------------------------------------------------------------

def test_the_nav_lists_the_planner_between_subjects_and_record(demo):
    html = demo.get("/planner").get_data(as_text=True)
    main = html[html.index('class="nav-main"'):html.index('class="nav-account"')]
    assert main.index(">Subjects<") < main.index(">Degree planner<") < main.index(">Record<")
    assert re.search(r'href="/planner"[^>]*aria-current="page"', html)


def test_visitors_do_not_see_the_planner_link(client):
    assert b'href="/planner"' not in client.get("/login").data