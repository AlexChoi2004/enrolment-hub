import re

import pytest

from features.accounts.seed import DEMO_EMAIL, DEMO_PASSWORD
from features.accounts.service import create_user
from features.degree_planner.service import add_to_plan, get_plan
from features.majors.service import choose_major
from features.submajors.service import choose_submajor

TOKEN = re.compile(r'name="csrf_token" value="([^"]+)"')


@pytest.fixture()
def student(conn):
    user = create_user(conn, "new.student@student.uni.edu.au", "Str0ng#Pass", "Autumn 2027")["id"]
    choose_major(conn, user, "MAJ03519")  # new accounts choose a major; these tests use Enterprise Software Development
    choose_submajor(conn, user, "SMJ10157")  # Information Security: core 41181 plus 18 cp of options
    return user


def sections(conn, user_id):
    return {s["label"]: s for s in get_plan(conn, user_id)["elective_sections"]}


# --- the data: both elective requirements are always listed -------------------------------------------

def test_the_demo_student_has_one_elective_section_because_the_sub_major_core_is_not_a_choice(conn):
    assert [s["label"] for s in get_plan(conn, 1)["elective_sections"]] == ["Major electives"]


def test_a_completed_sub_major_core_does_not_appear_as_an_elective_section(conn):
    assert "Sub-major core" not in sections(conn, 1)
    assert get_plan(conn, 1)["outstanding"]  # required subjects are listed separately


def test_an_unfinished_section_lists_what_is_still_needed(conn):
    major = sections(conn, 1)["Major electives"]  # one enrolled so far
    assert major["complete"] is False
    assert (major["choose"], major["chosen"], major["need"]) == (3, 1, 2)
    assert "41052" in {c["code"] for c in major["candidates"]}


def test_a_new_student_has_two_unfinished_sections(conn, student):
    result = sections(conn, student)
    assert (result["Major electives"]["chosen"], result["Major electives"]["need"]) == (0, 3)
    assert (result["Sub-major options"]["chosen"], result["Sub-major options"]["need"]) == (0, 3)  # 18 cp of 6 cp subjects
    assert not result["Major electives"]["complete"] and not result["Sub-major options"]["complete"]


def test_planning_the_last_elective_completes_the_section(conn):
    add_to_plan(conn, 1, "41052", "Spring 2028")
    add_to_plan(conn, 1, "32113", "Spring 2028")
    major = sections(conn, 1)["Major electives"]
    assert major["complete"] is True and major["chosen"] == 3
    assert any(s["label"] == "Major electives" for s in get_plan(conn, 1)["elective_sections"])  # still listed


def test_the_older_needs_list_only_holds_unfinished_sections(conn):
    add_to_plan(conn, 1, "41052", "Spring 2028")
    add_to_plan(conn, 1, "32113", "Spring 2028")
    assert get_plan(conn, 1)["elective_needs"] == []  # both finished


# --- the page ------------------------------------------------------------------------------------------------

def sign_in(client):
    token = TOKEN.search(client.get("/login").get_data(as_text=True)).group(1)
    client.post("/login", data={"email": DEMO_EMAIL, "password": DEMO_PASSWORD, "csrf_token": token})
    return client


def planner_page(client):
    return client.get("/planner").get_data(as_text=True)


def test_a_finished_section_shows_a_message_instead_of_disappearing(client):
    sign_in(client)
    for code in ("41052", "32113"):
        token = TOKEN.search(planner_page(client)).group(1)
        client.post("/planner/add", data={"subject_code": code, "session_label": "Spring 2028", "csrf_token": token})
    html = planner_page(client)
    assert 'class="card plan-complete"' in html
    assert "already completed or chosen all 3 major electives (3 of 3)" in html


def test_an_unfinished_section_is_still_an_expandable_list(client):
    html = planner_page(sign_in(client))
    assert "Major electives: choose 2 more (1 of 3 chosen)" in html
    assert 'id="electives-major-electives"' in html


def test_the_message_appears_once_the_last_elective_is_chosen(client):
    sign_in(client)
    token = TOKEN.search(planner_page(client)).group(1)
    for code in ["41052", "32113"]:
        client.post("/planner/add", data={"subject_code": code, "session_label": "Spring 2028", "csrf_token": token})
    html = planner_page(client)
    assert "already completed or chosen all 3 major electives (3 of 3)" in html
    assert "Major electives: choose" not in html  # the section is still there, but now as a message
    assert "Major electives" in html


def test_a_new_student_sees_both_lists_and_no_completion_messages(tmp_path):
    from app import create_app

    client = create_app({"DATABASE": str(tmp_path / "n.db"), "TESTING": True, "SECRET_KEY": "k"}).test_client()
    token = TOKEN.search(client.get("/register").get_data(as_text=True)).group(1)
    client.post("/register", data={"email": "new.student@student.uni.edu.au", "password": "Str0ng#Pass",
                                   "confirm_password": "Str0ng#Pass", "csrf_token": token})
    token = TOKEN.search(client.get("/planner").get_data(as_text=True)).group(1)
    client.post("/major/MAJ03519/choose", data={"csrf_token": token})  # new accounts choose a major first
    client.post("/submajor/SMJ10157/choose", data={"csrf_token": token})  # and a sub-major
    html = client.get("/planner").get_data(as_text=True)
    assert "Major electives: choose 3 more (0 of 3 chosen)" in html
    assert "Sub-major options: choose 3 more (0 of 3 chosen)" in html
    assert "already completed or chosen all" not in html