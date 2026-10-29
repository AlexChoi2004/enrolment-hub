import re

import pytest

from accounts.seed import DEMO_EMAIL, DEMO_PASSWORD
from app import create_app


def sign_in(test_client, email=DEMO_EMAIL, password=DEMO_PASSWORD):
    page = test_client.get("/login").get_data(as_text=True)
    token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
    test_client.post("/login", data={"email": email, "password": password, "csrf_token": token})
    return test_client


@pytest.fixture()
def demo_client(tmp_path):
    return sign_in(create_app({"DATABASE": str(tmp_path / "t.db"), "TESTING": True, "SECRET_KEY": "k"}).test_client())


def card(html, code):
    """The HTML of one subject card."""
    start = html.index(f'<span class="code">{code}</span>')
    start = html.rindex("<details", 0, start)
    return html[start : html.index("</details>", start)]


def page(client, query=""):
    return client.get("/subjects" + query).get_data(as_text=True)


def test_completed_subject_is_greyed_and_marked_completed(demo_client):
    html = card(page(demo_client), "41039")
    assert "status-completed" in html
    assert "Completed" in html
    assert "Completed in Autumn 2025" in html


def test_enrolled_subject_is_marked_enrolled(demo_client):
    html = card(page(demo_client), "41026")
    assert "status-enrolled" in html
    assert 'st-enrolled">Enrolled' in html
    assert "In progress in Autumn 2027" in html


def test_available_subject_says_can_enrol(demo_client):
    html = card(page(demo_client), "41052")
    assert "status-available" in html
    assert "Can enrol" in html


def test_blocked_subject_says_why_it_cant_be_taken(demo_client):
    html = card(page(demo_client), "32931")
    assert "status-blocked" in html
    assert "Can&#39;t enrol" in html or "Can't enrol" in html
    assert "Needs 32144 Technology Research Preparation" in html


def test_prerequisite_list_shows_met_and_unmet(demo_client):
    met = card(page(demo_client), "41026")
    assert "completed</span>" in met
    unmet = card(page(demo_client), "32931")
    assert "in progress (not yet met)" in unmet


def test_general_electives_section_is_greyed_out_when_complete(demo_client):
    html = page(demo_client)
    section = html[html.index('class="group cat-general_elective'):]
    assert "group-complete" in section[:80]
    assert "4 of 4 chosen" in section
    assert "can&#39;t enrol in any more general electives" in section or "can't enrol in any more general electives" in section
    # unchosen electives are blocked, with the reason
    assert "General electives requirement already complete" in card(html, "SYN102")


def test_major_electives_section_is_not_greyed_out_yet(demo_client):
    html = page(demo_client)
    start = html.index('class="group cat-major_elective')
    assert "group-complete" not in html[start : start + 80]
    assert "1 of 3 chosen" in html


def test_status_filter_shows_only_matching_subjects(demo_client):
    completed = page(demo_client, "?status=completed")
    assert "16 subjects" in completed
    assert "status-available" not in completed
    available = page(demo_client, "?status=available")
    assert "status-completed" not in available and "status-blocked" not in available
    assert page(demo_client, "?status=enrolled").count("status-enrolled") == 4


def test_invalid_status_filter_returns_400(demo_client):
    assert demo_client.get("/subjects?status=maybe").status_code == 400


def test_detail_page_shows_prerequisite_state_and_status(demo_client):
    html = demo_client.get("/subjects/32931").get_data(as_text=True)
    assert "Needs 32144" in html or "not yet met" in html
    assert "in progress (not yet met)" in html


def test_new_student_sees_a_different_page_from_the_demo_student(tmp_path):
    client = create_app({"DATABASE": str(tmp_path / "n.db"), "TESTING": True, "SECRET_KEY": "k"}).test_client()
    page_ = client.get("/register").get_data(as_text=True)
    token = re.search(r'name="csrf_token" value="([^"]+)"', page_).group(1)
    client.post(
        "/register",
        data={"email": "new.student@student.uni.edu.au", "password": "Str0ng#Pass",
              "confirm_password": "Str0ng#Pass", "csrf_token": token},
    )
    html = page(client)
    assert "status-completed" not in html and "status-enrolled" not in html
    assert "group-complete" not in html
    assert "Can enrol" in card(html, "41039")  # Programming 1
    assert "Can't enrol" in card(html, "48024") or "Can&#39;t enrol" in card(html, "48024")
    assert "0 of 4 chosen" in html


def test_htmx_fragment_also_carries_statuses(demo_client):
    html = demo_client.get("/subjects?status=completed", headers={"HX-Request": "true"}).get_data(as_text=True)
    assert "<html" not in html
    assert "st-completed" in html