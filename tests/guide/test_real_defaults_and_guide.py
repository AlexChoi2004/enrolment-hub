import re

import pytest

from app import create_app
from shared import db

TOKEN = re.compile(r'name="csrf_token" value="([^"]+)"')


@pytest.fixture()
def real(tmp_path, monkeypatch):
    """The app exactly as it runs for real: public sign-up off and a first-year demo student."""
    monkeypatch.delenv("DEMO_PROFILE", raising=False)
    monkeypatch.delenv("ALLOW_REGISTRATION", raising=False)
    app = create_app({"DATABASE": str(tmp_path / "real.db"), "TESTING": True, "SECRET_KEY": "k"})
    return app, app.test_client()


def token(client, path):
    return TOKEN.search(client.get(path).get_data(as_text=True)).group(1)


def sign_in(client):
    client.post("/login", data={"email": "john.doe@student.uni.edu.au", "password": "Johndoe#1", "csrf_token": token(client, "/login")})


def html(client, url):
    return client.get(url, follow_redirects=True).get_data(as_text=True)


# --- public sign-up is off ----------------------------------------------------------------------------------------------------------

def test_the_register_page_does_not_exist_by_default(real):
    _, client = real
    assert client.get("/register").status_code == 404
    assert client.post("/register", data={"email": "x@student.uni.edu.au", "password": "Str0ng#Pass", "confirm_password": "Str0ng#Pass"}).status_code == 404


def test_no_account_can_be_created_by_default(real):
    app, client = real
    client.post("/register", data={"email": "x@student.uni.edu.au", "password": "Str0ng#Pass", "confirm_password": "Str0ng#Pass"})
    conn = db.connect(app.config["DATABASE"])
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1  # only the simulated demo student
    conn.close()


def test_no_page_offers_to_create_an_account(real):
    _, client = real
    for url in ("/", "/login"):
        assert "Create account" not in html(client, url) and "Create an account" not in html(client, url)


def test_the_login_page_explains_there_is_no_sign_up_and_links_to_the_guide(real):
    _, client = real
    page = html(client, "/login")
    assert "no public sign-up" in page and "how to try the demo" in page


def test_the_demo_login_still_works(real):
    _, client = real
    sign_in(client)
    assert "John Doe" in html(client, "/profile")


def test_registration_can_be_switched_back_on_for_development(tmp_path, monkeypatch):
    monkeypatch.setenv("ALLOW_REGISTRATION", "1")
    client = create_app({"DATABASE": str(tmp_path / "dev.db"), "TESTING": True, "SECRET_KEY": "k"}).test_client()
    assert client.get("/register").status_code == 200 and "Create an account" in html(client, "/login")


# --- the first-year demo student, as seen in the app --------------------------------------------------------------------------------

def test_the_demo_student_starts_in_year_one(real):
    _, client = real
    sign_in(client)
    assert "Year 1, Semester 1" in html(client, "/planner") and "Year 1" in html(client, "/students/me")


def test_a_first_year_students_results_page_is_empty(real):
    _, client = real
    sign_in(client)
    assert "No results yet" in html(client, "/transcript")


def test_the_subjects_page_prompts_for_a_major_and_then_a_sub_major_or_electives(real):
    _, client = real
    sign_in(client)
    page = html(client, "/subjects")
    assert "You haven't chosen a major yet" in page and "chosen a sub-major or general electives yet" in page
    assert "Major core" not in page and "Choose major" in page


def test_a_first_year_can_choose_a_major_from_the_page(real):
    _, client = real
    sign_in(client)
    client.post("/major/MAJ03519/choose", data={"csrf_token": token(client, "/subjects")})
    page = html(client, "/subjects")
    assert "Enterprise Software Development major" in page and "You haven't chosen a major yet" not in page
    assert "chosen a sub-major or general electives yet" in page  # the sub-major is still to choose


def test_the_planner_asks_a_first_year_to_choose_a_major(real):
    _, client = real
    sign_in(client)
    assert "haven't chosen a major" in html(client, "/planner")


def test_the_guide_tells_a_first_year_to_choose_a_major_first(real):
    _, client = real
    page = html(client, "/help")
    assert "no major and no" in page and "sub-major chosen yet" in page


# --- the help page ----------------------------------------------------------------------------------------------------------------------

def test_the_help_page_is_public(real):
    _, client = real
    page = client.get("/help")
    assert page.status_code == 200 and "Try these scenarios" in page.get_data(as_text=True)


def test_the_help_page_says_it_is_simulated_and_gives_the_demo_login(real):
    _, client = real
    page = html(client, "/help")
    assert "Nothing here is a genuine UTS academic record" in page and "simulated" in page
    assert "john.doe@student.uni.edu.au" in page and "Johndoe#1" in page and "no public sign-up" in page


@pytest.mark.parametrize("title", [
    "Try this: fail a prerequisite subject", "Try this: retake and pass", "Try this: skip a semester without making up results",
    "Try this: change major or sub-major", "Try this: explore a student two years in",
])
def test_every_scenario_is_on_the_help_page(real, title):
    _, client = real
    assert title in html(client, "/help")


def test_the_help_page_covers_the_questions_people_ask(real):
    _, client = real
    page = html(client, "/help")
    for text in ("Is this a real UTS system?", "Why can't I create an account?", "How do marks become grades?",
                 "What does \"No result yet\" do?", "Are credit points ever counted twice?", "How do I start again?"):
        assert text in page


def test_the_nav_links_to_help_for_everyone(real):
    _, client = real
    assert ">Help<" in html(client, "/login")
    sign_in(client)
    assert ">Help<" in html(client, "/subjects")


# --- the guide's first scenario really behaves as written ----------------------------------------------------------------------------

def test_the_fail_a_prerequisite_scenario_does_what_the_guide_says(real):
    _, client = real
    sign_in(client)
    for code in ("41039", "33130", "31265", "37181"):
        client.post("/students/me/enrol", data={"subject_code": code, "session_label": "Autumn 2027", "csrf_token": token(client, "/subjects")})
    client.post("/planner/add", data={"subject_code": "48024", "session_label": "Spring 2027", "csrf_token": token(client, "/planner")})
    t = token(client, "/simulator/results")
    review = client.post("/simulator/review", data={
        "csrf_token": t, "mode": "complete", "result_41039": "failed", "result_33130": "passed", "result_31265": "passed", "result_37181": "passed"})
    assert review.status_code == 200 and "Confirm and save" in review.get_data(as_text=True)
    client.post("/simulator/finish", data={
        "csrf_token": t, "result_41039": "failed", "result_33130": "passed", "result_31265": "passed", "result_37181": "passed"})
    planner = html(client, "/planner")
    assert "Year 1, Semester 2" in planner and "Spring 2027" in planner
    results = html(client, "/transcript")
    assert "Programming 1" in results and 'st-retake">Failed' in results and results.count('st-completed">Passed') == 3
    assert "Add retake to plan" in planner and "Failed subjects" in planner
    assert "Needs 41039 Programming 1 (failed: retake it first)" in planner
    assert "Failed: retake needed" in html(client, "/subjects")
    refused = client.post("/students/me/enrol", data={"subject_code": "48024", "session_label": "Spring 2027", "csrf_token": token(client, "/subjects")}, follow_redirects=True)
    assert "failed: retake it first" in refused.get_data(as_text=True)


def test_the_retake_and_pass_scenario_does_what_the_guide_says(real):
    _, client = real
    sign_in(client)
    client.post("/students/me/enrol", data={"subject_code": "41039", "session_label": "Autumn 2027", "csrf_token": token(client, "/subjects")})
    client.post("/planner/add", data={"subject_code": "48024", "session_label": "Spring 2027", "csrf_token": token(client, "/planner")})
    client.post("/simulator/finish", data={"csrf_token": token(client, "/simulator/results"), "result_41039": "failed"})
    client.post("/students/me/enrol", data={"subject_code": "41039", "session_label": "Spring 2027", "csrf_token": token(client, "/subjects")})
    client.post("/simulator/finish", data={"csrf_token": token(client, "/simulator/results"), "result_41039": "passed"})
    results = html(client, "/transcript")
    assert results.count("Programming 1") >= 2 and 'st-retake">Failed' in results and 'st-completed">Passed' in results
    assert "6 credit points passed" in results  # counted once
    planner = html(client, "/planner")
    assert "Needs rescheduling" in planner and "48024" in planner and "Spring 2027, which has passed" in planner


def test_the_skip_scenario_does_what_the_guide_says(app, real):
    _, client = real
    sign_in(client)
    client.post("/students/me/enrol", data={"subject_code": "41039", "session_label": "Autumn 2027", "csrf_token": token(client, "/subjects")})
    client.post("/simulator/finish", data={"csrf_token": token(client, "/simulator/results"), "result_41039": "none"})
    assert "No results yet" in html(client, "/transcript")  # nothing was invented
    assert "Year 1, Semester 2" in html(client, "/planner")
