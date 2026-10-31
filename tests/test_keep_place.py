import re

import pytest

from accounts.seed import DEMO_EMAIL, DEMO_PASSWORD

TOKEN = re.compile(r'name="csrf_token" value="([^"]+)"')
ACTION_FORM = re.compile(r'<form class="([^"]*)" method="post" action="([^"]*)"')


@pytest.fixture()
def demo(client):
    token = TOKEN.search(client.get("/login").get_data(as_text=True)).group(1)
    client.post("/login", data={"email": DEMO_EMAIL, "password": DEMO_PASSWORD, "csrf_token": token})
    return client


def page(client, url):
    return client.get(url, follow_redirects=True).get_data(as_text=True)


# --- the script that keeps your place ------------------------------------------------------------------

def test_the_script_is_served_from_the_app(client):
    res = client.get("/static/keep-scroll.js")
    assert res.status_code == 200
    assert "javascript" in res.headers["Content-Type"]
    body = res.get_data(as_text=True)
    assert "sessionStorage" in body and "enrol-form" in body and "scrollTo" in body


def test_pages_load_the_script_and_the_policy_allows_it(demo):
    html = page(demo, "/subjects")
    assert 'keep-scroll.js" defer' in html
    assert "script-src 'self'" in demo.get("/subjects").headers["Content-Security-Policy"]  # no inline script needed


def test_the_script_does_not_run_inline(demo):
    assert "<script>" not in page(demo, "/subjects")


# --- every action form is covered ------------------------------------------------------------------------------

@pytest.mark.parametrize("url", ["/subjects", "/planner", "/students/me", "/timetable"])
def test_every_enrolment_and_plan_form_uses_the_action_class(demo, url):
    forms = ACTION_FORM.findall(page(demo, url))
    actions = [(cls, action) for cls, action in forms if action.startswith(("/students/me/", "/planner/", "/timetable/"))]
    assert actions, "the page should have action forms"
    for cls, action in actions:
        assert "enrol-form" in cls.split(), action


def test_log_out_and_login_are_not_treated_as_actions(demo):
    html = page(demo, "/profile")
    assert 'class="inline" method="post" action="/logout"' in html


# --- cards can be reopened ---------------------------------------------------------------------------------------

def test_subject_cards_have_ids_so_open_ones_can_be_restored(demo):
    html = page(demo, "/subjects")
    assert 'id="card-41052"' in html and 'id="card-41026"' in html


def test_filtered_results_keep_the_card_ids(demo):
    html = demo.get("/subjects?q=algorithms", headers={"HX-Request": "true"}).get_data(as_text=True)
    assert "<html" not in html and 'id="card-41052"' in html


# --- messages stay in view ---------------------------------------------------------------------------------------

def test_a_message_is_shown_as_a_toast(demo):
    token = TOKEN.search(page(demo, "/subjects")).group(1)
    demo.post("/students/me/enrol", data={"subject_code": "41052", "session_label": "Spring 2027", "csrf_token": token})
    html = page(demo, "/subjects")
    assert '<div class="toasts">' in html
    assert 'class="toast flash-success"' in html
    assert "Enrolled in 41052 Advanced Algorithms for Spring 2027." in html


def test_an_error_message_is_a_toast_too(demo):
    token = TOKEN.search(page(demo, "/subjects")).group(1)
    demo.post("/students/me/enrol", data={"subject_code": "43030", "session_label": "Autumn 2027", "csrf_token": token})
    html = page(demo, "/subjects")
    assert 'class="toast flash-error"' in html and "Autumn 2027 is full" in html


def test_there_is_no_toast_container_when_there_is_nothing_to_say(demo):
    assert 'class="toasts"' not in page(demo, "/subjects")


def test_in_page_notices_are_not_toasts(demo):
    token = TOKEN.search(page(demo, "/planner")).group(1)
    demo.post("/planner/suggest", data={"csrf_token": token})
    html = page(demo, "/planner")
    assert '<p class="flash flash-success">Your plan covers every requirement' in html  # inline, stays on the page