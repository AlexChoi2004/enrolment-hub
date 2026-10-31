import re

import pytest

from accounts.seed import DEMO_EMAIL, DEMO_PASSWORD
from app import create_app
from shared import db

TOKEN = re.compile(r'name="csrf_token" value="([^"]+)"')
LABELS = {"tutorial": "Tutorial", "tutorial2": "Tutorial 2", "workshop": "Workshop"}


def sign_in(client):
    token = TOKEN.search(client.get("/login").get_data(as_text=True)).group(1)
    client.post("/login", data={"email": DEMO_EMAIL, "password": DEMO_PASSWORD, "csrf_token": token})
    return client


def token_for(client, path="/timetable"):
    return TOKEN.search(client.get(path).get_data(as_text=True)).group(1)


def post(client, url, **data):
    data.setdefault("csrf_token", token_for(client))
    return client.post(url, data=data)


def page(client, query=""):
    return client.get("/timetable" + query).get_data(as_text=True)


def choices(app, user_id=1):
    conn = db.connect(app.config["DATABASE"])
    try:
        return {(r["subject_code"], r["component"]): r["class_id"] for r in conn.execute(
            "SELECT subject_code, component, class_id FROM class_choices WHERE user_id = ?", (user_id,))}
    finally:
        conn.close()


def set_classes(app, code, season, lecture, parts):
    conn = db.connect(app.config["DATABASE"])
    try:
        conn.execute("DELETE FROM class_choices WHERE subject_code = ?", (code,))
        conn.execute("DELETE FROM classes WHERE subject_code = ? AND season = ?", (code, season))
        conn.execute("INSERT INTO classes (subject_code, season, component, kind, name, day, start_hour, duration, room)"
                     " VALUES (?, ?, 'lecture', 'lecture', 'Lecture', ?, ?, ?, 'Room T1')", (code, season, *lecture))
        ids = {}
        for component, options in parts.items():
            kind = "workshop" if component == "workshop" else "tutorial"
            ids[component] = [conn.execute(
                "INSERT INTO classes (subject_code, season, component, kind, name, day, start_hour, duration, room)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Room T2')",
                (code, season, component, kind, f"{LABELS[component]} {'ABCDEFGHIJ'[i]}", day, start, duration)).lastrowid
                for i, (day, start, duration) in enumerate(options)]
        conn.commit()
        return ids
    finally:
        conn.close()


def friday(n=5):
    return [("Fri", 9 + i, 1) for i in range(n)]


@pytest.fixture()
def demo(app, client):
    return sign_in(client)


# --- access control ---------------------------------------------------------------------------------

def test_anonymous_visitors_are_sent_to_login(client):
    res = client.get("/timetable")
    assert res.status_code == 302 and "next=/timetable" in res.headers["Location"]


@pytest.mark.parametrize("url", ["/timetable/choose", "/timetable/drop/41026/tutorial"])
def test_anonymous_visitors_cannot_change_choices(app, client, url):
    res = client.post(url, data={"subject_code": "41026", "class_id": "1"})
    assert res.status_code == 302 and "/login" in res.headers["Location"]
    assert choices(app) == {}


@pytest.mark.parametrize("url", ["/timetable/choose", "/timetable/drop/41026/tutorial"])
def test_changes_must_be_posted_with_a_csrf_token(app, demo, url):
    ids = set_classes(app, "41026", "Autumn", ("Thu", 15, 2), {"tutorial": friday()})
    assert demo.get(url).status_code == 405
    assert demo.post(url, data={"subject_code": "41026", "class_id": str(ids["tutorial"][0])}).status_code == 400
    assert choices(app) == {}


def test_the_form_cannot_name_another_student(app, demo):
    ids = set_classes(app, "41026", "Autumn", ("Thu", 15, 2), {"tutorial": friday()})
    post(demo, "/timetable/choose", subject_code="41026", class_id=str(ids["tutorial"][0]), user_id="2")
    assert choices(app) == {("41026", "tutorial"): ids["tutorial"][0]}  # went to the signed-in student
    assert choices(app, user_id=2) == {}


def test_malformed_input_returns_400(demo):
    assert post(demo, "/timetable/choose", subject_code="bad!code", class_id="1").status_code == 400
    assert post(demo, "/timetable/choose", subject_code="41026", class_id="abc").status_code == 400
    assert post(demo, "/timetable/choose", subject_code="41026").status_code == 400
    assert post(demo, "/timetable/drop/bad!code/tutorial").status_code == 400
    assert post(demo, "/timetable/drop/41026/lecture").status_code == 400  # lectures cannot be dropped


def test_the_page_is_not_cacheable(demo):
    assert demo.get("/timetable").headers["Cache-Control"] == "no-store"


# --- the page ------------------------------------------------------------------------------------------

def test_the_page_shows_tabs_the_week_and_each_subject(demo):
    html = page(demo)
    assert ">Autumn 2027<" in html and ">Spring 2027<" in html
    assert 'class="tt-week"' in html and ">Mon<" in html and ">Fri<" in html
    for code in ["31272", "32144", "41026", "41040"]:
        assert f'<span class="code">{code}</span>' in html
    assert "invented for this prototype" in html
    assert "Lecture:" in html and "added automatically" in html


def test_every_subject_has_its_own_colour(demo):
    html = page(demo)
    classes = re.findall(r'<section class="card tt-subject tt-c(\d+)"', html)
    assert classes == ["0", "1", "2", "3"]
    lecture_colours = re.findall(r'class="tt-block tt-c(\d+) ', html)
    assert set(lecture_colours) == {"0", "1", "2", "3"}  # the four lectures, one colour each


def test_a_subjects_lecture_and_chosen_class_share_a_colour(app, demo):
    ids = set_classes(app, "41026", "Autumn", ("Thu", 15, 2), {"tutorial": friday()})
    post(demo, "/timetable/choose", subject_code="41026", class_id=str(ids["tutorial"][0]), session_label="Autumn 2027")
    blocks = re.findall(r'class="tt-block tt-c(\d+) [^"]*"\s+title="41026 ', page(demo))
    assert len(blocks) == 2 and len(set(blocks)) == 1


def test_each_choosable_component_lists_every_option(demo):
    html = page(demo)
    selects = re.findall(r'<select name="class_id"[^>]*>(.*?)</select>', html, re.S)
    assert selects and all(5 <= len(re.findall(r"<option", s)) <= 10 for s in selects)


def test_the_current_session_tab_is_marked(demo):
    assert re.search(r'session=Autumn[^"]*"[^>]*aria-current="page"', page(demo))
    assert re.search(r'session=Spring[^"]*"[^>]*aria-current="page"', page(demo, "?session=Spring 2027"))


def test_an_unknown_session_falls_back_to_the_current_one(demo):
    assert re.search(r'session=Autumn[^"]*"[^>]*aria-current="page"', page(demo, "?session=Winter 2099"))


def test_an_empty_session_says_so(demo):
    html = page(demo, "?session=Spring 2027")
    assert "not enrolled in anything for Spring 2027" in html and 'class="tt-week"' not in html


def test_spring_shows_subjects_enrolled_for_spring(demo):
    token = token_for(demo, "/subjects")
    demo.post("/students/me/enrol", data={"subject_code": "43030", "session_label": "Spring 2027", "csrf_token": token})
    html = page(demo, "?session=Spring 2027")
    assert '<span class="code">43030</span>' in html and "Choose " in html


def test_the_page_lists_what_is_still_to_choose(demo):
    assert "Still to choose:" in page(demo)


def test_each_form_uses_the_action_class_so_the_page_keeps_its_place(demo):
    forms = re.findall(r'<form class="([^"]*)" method="post" action="([^"]*)"', page(demo))
    actions = [c for c, a in forms if a.startswith("/timetable/")]
    assert actions and all("enrol-form" in c.split() for c in actions)


# --- choose, change, drop -----------------------------------------------------------------------------

def test_choosing_a_class_confirms_and_shows_it(app, demo):
    ids = set_classes(app, "41026", "Autumn", ("Thu", 15, 2), {"tutorial": friday()})
    res = post(demo, "/timetable/choose", subject_code="41026", class_id=str(ids["tutorial"][0]), session_label="Autumn 2027")
    assert res.status_code == 303 and "session=Autumn" in res.headers["Location"]
    assert choices(app) == {("41026", "tutorial"): ids["tutorial"][0]}
    html = page(demo)
    assert "Chose the class for 41026 Advanced Software Development: Tutorial A (Fri 9:00-10:00)." in html
    assert "Change tutorial" in html and ">Drop<" in html


def test_a_clash_is_allowed_with_a_warning_and_shown_in_red(app, demo):
    set_classes(app, "31272", "Autumn", ("Mon", 9, 2), {"tutorial": friday()})
    ids = set_classes(app, "41026", "Autumn", ("Thu", 15, 2), {"tutorial": [("Mon", 10, 1)] + [("Tue", 9 + i, 1) for i in range(4)]})
    post(demo, "/timetable/choose", subject_code="41026", class_id=str(ids["tutorial"][0]), session_label="Autumn 2027")
    assert choices(app) == {("41026", "tutorial"): ids["tutorial"][0]}  # saved
    html = page(demo)
    assert 'class="toast flash-warning"' in html
    assert "clashes with 31272 lecture (Mon 9:00-11:00)" in html
    assert html.count(" tt-clash") >= 2  # both overlapping blocks are red
    assert "Classes that clash this session" in html


def test_clashing_options_are_explained_but_not_disabled(app, demo):
    set_classes(app, "31272", "Autumn", ("Mon", 9, 2), {"tutorial": friday()})
    set_classes(app, "41026", "Autumn", ("Thu", 15, 2), {"tutorial": [("Mon", 10, 1)] + [("Tue", 9 + i, 1) for i in range(4)]})
    html = page(demo)
    assert "(clashes with 31272 lecture (Mon 9:00-11:00))" in html
    assert not re.search(r'<option value="\d+"[^>]*disabled', html)


def test_no_red_when_nothing_overlaps(demo):
    html = page(demo)
    assert " tt-clash" not in html
    assert "Classes that clash this session" not in html


def test_changing_and_dropping_through_the_pages(app, demo):
    ids = set_classes(app, "41026", "Autumn", ("Thu", 15, 2), {"tutorial": friday()})
    post(demo, "/timetable/choose", subject_code="41026", class_id=str(ids["tutorial"][0]), session_label="Autumn 2027")
    post(demo, "/timetable/choose", subject_code="41026", class_id=str(ids["tutorial"][1]), session_label="Autumn 2027")
    assert choices(app) == {("41026", "tutorial"): ids["tutorial"][1]}
    assert "Changed the class for 41026 Advanced Software Development" in page(demo)
    post(demo, "/timetable/drop/41026/tutorial", session_label="Autumn 2027")
    assert choices(app) == {}
    assert "Dropped the tutorial for 41026 Advanced Software Development." in page(demo)


def test_two_components_show_two_choosers(app, demo):
    ids = set_classes(app, "41026", "Autumn", ("Thu", 15, 2), {"tutorial": friday(), "workshop": [("Wed", 9 + 2 * i, 2) for i in range(5)]})
    html = page(demo)
    assert "Choose tutorial" in html and "Choose workshop" in html
    post(demo, "/timetable/choose", subject_code="41026", class_id=str(ids["workshop"][0]), session_label="Autumn 2027")
    assert choices(app) == {("41026", "workshop"): ids["workshop"][0]}
    assert "Workshop: <strong>Workshop A</strong>" in page(demo)


def test_dropping_something_not_chosen_is_refused(demo):
    post(demo, "/timetable/drop/41026/tutorial", session_label="Autumn 2027")
    assert "have not chosen that class for 41026" in page(demo)


def test_changes_return_to_the_timetable_for_that_session(app, demo):
    ids = set_classes(app, "41026", "Autumn", ("Thu", 15, 2), {"tutorial": friday()})
    res = post(demo, "/timetable/choose", subject_code="41026", class_id=str(ids["tutorial"][0]), session_label="Autumn 2027")
    assert res.status_code == 303 and "/timetable" in res.headers["Location"]


def test_a_new_student_sees_an_empty_timetable(tmp_path):
    client = create_app({"DATABASE": str(tmp_path / "n.db"), "TESTING": True, "SECRET_KEY": "k"}).test_client()
    token = TOKEN.search(client.get("/register").get_data(as_text=True)).group(1)
    client.post("/register", data={"email": "new.student@student.uni.edu.au", "password": "Str0ng#Pass",
                                   "confirm_password": "Str0ng#Pass", "csrf_token": token})
    assert "not enrolled in anything for Autumn 2027" in client.get("/timetable").get_data(as_text=True)


# --- navigation ------------------------------------------------------------------------------------------

def test_the_nav_lists_the_timetable_between_the_planner_and_record(demo):
    html = demo.get("/timetable").get_data(as_text=True)
    main = html[html.index('class="nav-main"'):html.index('class="nav-account"')]
    assert main.index(">Subjects<") < main.index(">Degree planner<") < main.index(">Timetable<") < main.index(">Record<")
    assert re.search(r'href="/timetable"[^>]*aria-current="page"', html)


def test_visitors_do_not_see_the_timetable_link(client):
    assert b'href="/timetable"' not in client.get("/login").data