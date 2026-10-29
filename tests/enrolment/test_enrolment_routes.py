import re

import pytest

from accounts.seed import DEMO_EMAIL, DEMO_PASSWORD
from app import create_app
from shared import db

AUTUMN = "Autumn 2027"
SPRING = "Spring 2027"
TOKEN = re.compile(r'name="csrf_token" value="([^"]+)"')


def sign_in(client, email=DEMO_EMAIL, password=DEMO_PASSWORD):
    token = TOKEN.search(client.get("/login").get_data(as_text=True)).group(1)
    client.post("/login", data={"email": email, "password": password, "csrf_token": token})
    return client


def token_for(client, path="/subjects"):
    return TOKEN.search(client.get(path).get_data(as_text=True)).group(1)


def enrolled_rows(app, user_id=1):
    conn = db.connect(app.config["DATABASE"])
    try:
        return {
            r["subject_code"]: (r["status"], r["session_label"])
            for r in conn.execute("SELECT * FROM enrolments WHERE user_id = ?", (user_id,))
        }
    finally:
        conn.close()


@pytest.fixture()
def demo(app, client):
    return sign_in(client)


def new_student(tmp_path):
    """A signed-in, freshly registered student on their own database."""
    client = create_app({"DATABASE": str(tmp_path / "n.db"), "TESTING": True, "SECRET_KEY": "k"}).test_client()
    token = TOKEN.search(client.get("/register").get_data(as_text=True)).group(1)
    client.post(
        "/register",
        data={"email": "new.student@student.uni.edu.au", "password": "Str0ng#Pass",
              "confirm_password": "Str0ng#Pass", "csrf_token": token},
    )
    return client


def post(client, url, **data):
    data.setdefault("csrf_token", token_for(client))
    return client.post(url, data=data)


def flashed(client, url="/subjects"):
    return client.get(url).get_data(as_text=True)


# --- access control ---------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "url", ["/students/me/enrol", "/students/me/withdraw/41026", "/students/me/move/41026"]
)
def test_anonymous_visitors_cannot_change_enrolments(app, client, url):
    res = client.post(url, data={"subject_code": "41052", "session_label": SPRING})
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]
    assert "41052" not in enrolled_rows(app)


@pytest.mark.parametrize(
    "url", ["/students/me/enrol", "/students/me/withdraw/41026", "/students/me/move/41026"]
)
def test_changes_must_be_posted(demo, url):
    assert demo.get(url).status_code == 405


@pytest.mark.parametrize(
    "url", ["/students/me/enrol", "/students/me/withdraw/41026", "/students/me/move/41026"]
)
def test_changes_need_a_csrf_token(app, demo, url):
    before = enrolled_rows(app)
    res = demo.post(url, data={"subject_code": "41052", "session_label": SPRING})
    assert res.status_code == 400
    assert enrolled_rows(app) == before


def test_a_forged_csrf_token_is_rejected(app, demo):
    res = demo.post("/students/me/enrol", data={"subject_code": "41052", "session_label": SPRING, "csrf_token": "forged"})
    assert res.status_code == 400
    assert "41052" not in enrolled_rows(app)


def test_the_form_cannot_name_another_student(app, demo):
    post(demo, "/students/me/enrol", subject_code="41052", session_label=SPRING, user_id="2", student_number="S0000002")
    assert enrolled_rows(app)["41052"] == ("enrolled", SPRING)  # went to the signed-in student


def test_malformed_subject_codes_return_400(demo):
    assert post(demo, "/students/me/enrol", subject_code="bad!code", session_label=SPRING).status_code == 400
    assert post(demo, "/students/me/enrol", session_label=SPRING).status_code == 400
    assert post(demo, "/students/me/withdraw/bad!code").status_code == 400


# --- enrol (Create) ---------------------------------------------------------------------------------------------

def test_enrolling_redirects_back_and_confirms(app, demo):
    res = post(demo, "/students/me/enrol", subject_code="41052", session_label=SPRING, next="/subjects?status=available")
    assert res.status_code == 303
    assert res.headers["Location"].endswith("/subjects?status=available")
    assert enrolled_rows(app)["41052"] == ("enrolled", SPRING)
    assert "Enrolled in 41052 Advanced Algorithms for Spring 2027." in flashed(demo)


def test_the_catalogue_shows_the_new_status_after_enrolling(demo):
    post(demo, "/students/me/enrol", subject_code="41052", session_label=SPRING)
    page = flashed(demo)
    start = page.index('<span class="code">41052</span>')
    assert "status-enrolled" in page[page.rindex("<details", 0, start):start]


def test_a_refused_enrolment_explains_why_and_changes_nothing(app, demo):
    before = enrolled_rows(app)
    post(demo, "/students/me/enrol", subject_code="32931", session_label=SPRING)
    assert enrolled_rows(app) == before
    assert "Needs 32144 Technology Research Preparation" in flashed(demo)


def test_a_full_session_shows_an_error_message(app, demo):
    post(demo, "/students/me/enrol", subject_code="43030", session_label=AUTUMN)
    assert "Autumn 2027 is full (24 of 24 credit points)" in flashed(demo)
    assert "43030" not in enrolled_rows(app)


def test_the_flash_message_is_shown_once(demo):
    post(demo, "/students/me/enrol", subject_code="41052", session_label=SPRING)
    assert "Enrolled in 41052" in flashed(demo)
    assert "Enrolled in 41052" not in flashed(demo)


@pytest.mark.parametrize("evil", ["//evil.example", "https://evil.example", "/\\evil.example"])
def test_enrolling_never_redirects_off_site(demo, evil):
    res = post(demo, "/students/me/enrol", subject_code="41052", session_label=SPRING, next=evil)
    assert res.status_code == 303
    assert res.headers["Location"].endswith("/subjects")
    assert "evil" not in res.headers["Location"]


# --- withdraw (Delete) -----------------------------------------------------------------------------------------

def test_withdrawing_a_seeded_enrolment(app, demo):
    res = post(demo, "/students/me/withdraw/41026", next="/students/me")
    assert res.status_code == 303
    assert "41026" not in enrolled_rows(app)
    assert "Withdrew from 41026 Advanced Software Development." in flashed(demo)


def test_withdrawing_a_completed_subject_is_refused(app, demo):
    post(demo, "/students/me/withdraw/41039")
    assert enrolled_rows(app)["41039"][0] == "completed"
    assert "completed and can&#39;t be withdrawn" in flashed(demo) or "completed and can't be withdrawn" in flashed(demo)


def test_withdrawing_something_you_are_not_in_is_refused(demo):
    post(demo, "/students/me/withdraw/41052")
    assert "not enrolled in 41052" in flashed(demo)


# --- move (Update) ----------------------------------------------------------------------------------------------

def test_moving_an_enrolment_between_sessions(app, demo):
    post(demo, "/students/me/enrol", subject_code="43030", session_label=SPRING)
    post(demo, "/students/me/withdraw/41040")  # make room in Autumn
    post(demo, "/students/me/move/43030", session_label=AUTUMN)
    assert enrolled_rows(app)["43030"] == ("enrolled", AUTUMN)
    assert "Moved 43030 Professional Practice in Computing to Autumn 2027." in flashed(demo)


def test_an_impossible_move_explains_why(app, demo):
    post(demo, "/students/me/move/41026", session_label=SPRING)
    assert enrolled_rows(app)["41026"] == ("enrolled", AUTUMN)
    assert "not offered in Spring 2027" in flashed(demo)


# --- what the pages offer ----------------------------------------------------------------------------------------

def card(html, code):
    start = html.index(f'<span class="code">{code}</span>')
    start = html.rindex("<details", 0, start)
    return html[start : html.index("</details>", start)]


def test_available_subjects_get_an_enrol_button(demo):
    html = card(flashed(demo), "41052")
    assert "Enrol for Spring 2027" in html
    assert 'action="/students/me/enrol"' in html
    assert 'name="csrf_token"' in html


def test_subjects_offered_in_both_sessions_get_a_session_choice(tmp_path):
    client = new_student(tmp_path)  # a new student has room in both sessions
    html = card(client.get("/subjects").get_data(as_text=True), "41039")
    assert '<select name="session_label">' in html
    assert 'value="Autumn 2027"' in html and 'value="Spring 2027"' in html


def test_enrolled_subjects_get_withdraw_but_completed_and_blocked_do_not(demo):
    page = flashed(demo)
    assert "Withdraw" in card(page, "41026")
    assert "Withdraw" not in card(page, "41039")  # completed
    assert "Enrol" not in card(page, "32931").replace("Enrolled", "")  # blocked
    assert "Withdraw" not in card(page, "32931")


def test_the_page_shows_how_full_each_session_is(demo):
    page = flashed(demo)
    assert "Autumn 2027: 24 of 24 credit points" in page
    assert "Spring 2027: 0 of 24 credit points" in page


def test_the_record_page_lists_withdraw_buttons_and_loads(demo):
    page = demo.get("/students/DEMO0001/record").get_data(as_text=True)
    assert page.count("Withdraw") == 4
    assert "Autumn 2027: 24 of 24 credit points" in page


def test_a_new_student_can_enrol_and_withdraw_through_the_pages(tmp_path):
    client = new_student(tmp_path)
    token = token_for(client)
    client.post("/students/me/enrol", data={"subject_code": "41039", "session_label": AUTUMN, "csrf_token": token})
    page = client.get("/students/me", follow_redirects=True).get_data(as_text=True)
    assert "41039" in page and "Programming 1" in page and "6 of 192 credit points counted" in page
    client.post("/students/me/withdraw/41039", data={"csrf_token": token, "next": "/students/me"})
    page = client.get("/students/me", follow_redirects=True).get_data(as_text=True)
    assert "0 of 192 credit points counted" in page