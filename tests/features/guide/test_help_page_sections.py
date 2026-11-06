import re

import pytest
from markupsafe import escape

from features.enrolment.presets import PRESETS
from shared import db

TOKEN = re.compile(r'name="csrf_token" value="([^"]+)"')
SECTIONS = ["start", "presets", "tests", "ai", "showcase", "tabs", "faq"]


def token(client, path="/profile"):
    return TOKEN.search(client.get(path).get_data(as_text=True)).group(1)


def html(client, url):
    return client.get(url, follow_redirects=True).get_data(as_text=True)


def reset_to(client, key):
    client.post("/simulator/reset", data={"csrf_token": token(client), "confirm": "yes", "profile": key})


def post(client, url, **data):
    return client.post(url, data={"csrf_token": token(client), **data})


# --- the page's structure ----------------------------------------------------------------------------------------------------------------

def test_the_help_page_has_every_section_in_order(client):
    page = html(client, "/help")
    positions = [page.index(f'id="{s}"') for s in SECTIONS]
    assert positions == sorted(positions)


def test_every_contents_link_goes_to_a_section_on_the_page(client):
    page = html(client, "/help")
    toc = page.split('<nav class="toc"', 1)[1].split("</nav>", 1)[0]
    targets = re.findall(r'href="#([a-z]+)"', toc)
    assert targets == SECTIONS and all(f'id="{t}"' in page for t in targets)


def test_the_starting_points_table_is_built_from_the_presets(client):
    page = html(client, "/help")
    for key, p in PRESETS.items():
        assert f'id="preset-{key}"' in page and escape(p["title"]) in page and escape(p["summary"]) in page
        assert all(escape(item) in page for item in p["good_for"])


def test_every_walkthrough_names_a_real_starting_point_and_says_so_in_its_label(client):
    page = html(client, "/help")
    found = re.findall(r'<details class="walkthrough" data-preset="(\w+)">\s*<summary>(.*?)<span class="tag">Start from: ([^<]+)</span>', page, re.S)
    assert len(found) >= 11
    for key, title, label in found:
        assert key in PRESETS and title.strip()
        assert label == "any" or label == PRESETS[key]["title"], (key, label)


def test_every_walkthrough_with_steps_has_a_numbered_list(client):
    page = html(client, "/help")
    blocks = page.split('<details class="walkthrough"')[1:]
    assert all("<ol>" in b.split("</details>", 1)[0] for b in blocks)


def test_the_page_no_longer_mentions_things_that_were_removed_or_renamed(client):
    page = html(client, "/help")
    for stale in ("Skip to next semester", ">Simulator<", "Load the sample two-year history", "Start as a first-year student", "Reset the simulation</strong>, choose"):
        assert stale not in page


def test_the_page_points_to_the_simulation_bar_and_the_starting_points(client):
    page = html(client, "/help")
    assert "Press <strong>Reset</strong> in the bar under the header" in page and "Where did the Simulator tab go?" in page


# --- every walkthrough really does what it says --------------------------------------------------------------------------------------------

def test_walkthrough_a_failed_prerequisite_then_a_retake(app, client, log_in):
    log_in()
    reset_to(client, "failed")
    planner = html(client, "/planner")
    assert "Failed subjects" in planner and "Add retake to plan" in planner
    assert "Needs 48024 Programming 2 (failed: retake it first)" in planner
    assert post(client, "/students/me/enrol", subject_code="48024", session_label="Autumn 2027").status_code in (302, 303)  # there is room: 18 of 24 cp
    codes = ("31265", "37181", "41025", "48024")
    assert post(client, "/simulator/finish", **{f"result_{c}": "passed" for c in codes}).status_code == 303
    results = html(client, "/transcript").split("<main", 1)[1]
    assert results.count("Programming 2") >= 2 and "Spring 2026" in results and "Autumn 2027" in results
    assert "Failed" in results and "Passed" in results
    after = html(client, "/planner")
    assert "Needs 48024 Programming 2 (failed" not in after
    conn = db.connect(app.config["DATABASE"])
    assert conn.execute("SELECT COUNT(*) FROM enrolments WHERE user_id = 1 AND subject_code = '48024' AND status = 'completed'").fetchone()[0] == 1  # counted once
    conn.close()
    assert post(client, "/simulator/rollback").status_code == 303
    assert "Failed subjects" in html(client, "/planner")  # undone: Programming 2 is a failed subject again


def test_walkthrough_a_swap_that_costs_time(app, client, log_in):
    log_in()
    reset_to(client, "sample")
    page = html(client, "/major/MAJ10053")
    assert "Possible, but it costs time" in page and "<strong>Spring 2028</strong> now, <strong>Autumn 2029</strong> after this swap" in page
    assert 'name="acknowledge"' in page
    post(client, "/major/MAJ10053/choose")  # without the tick
    conn = db.connect(app.config["DATABASE"])
    assert conn.execute("SELECT major_code FROM users WHERE id = 1").fetchone()[0] == "MAJ03519"  # refused, nothing deleted
    assert conn.execute("SELECT COUNT(*) FROM subject_attempts WHERE user_id = 1").fetchone()[0] == 16
    conn.close()


def test_walkthrough_a_risky_swap_needs_your_confirmation(app, client, log_in):
    log_in()
    reset_to(client, "late")
    page = html(client, "/major/MAJ03445")
    assert "Swap advice: Think carefully" in page and "88%</strong> through your major" in page and 'name="acknowledge"' in page
    post(client, "/major/MAJ03445/choose")
    conn = db.connect(app.config["DATABASE"])
    assert conn.execute("SELECT major_code FROM users WHERE id = 1").fetchone()[0] == "MAJ03519"
    post(client, "/major/MAJ03445/choose", acknowledge="1")
    assert conn.execute("SELECT major_code FROM users WHERE id = 1").fetchone()[0] == "MAJ03445"
    conn.close()


def test_walkthrough_keep_a_sub_majors_subjects_as_general_electives(app, client, log_in):
    log_in()
    reset_to(client, "sample")
    page = html(client, "/submajor/electives")
    assert "Count these as general electives?" in page and page.count('name="count_as_electives"') == 4
    two = ["48080", "81529"]
    post(client, "/submajor/electives/choose", count_as_electives=two)  # only two: the cost tick is still needed
    conn = db.connect(app.config["DATABASE"])
    assert conn.execute("SELECT general_electives FROM users WHERE id = 1").fetchone()[0] == 0
    post(client, "/submajor/electives/choose", count_as_electives=["48080", "81529", "81546", "81547"])  # all four: no tick needed
    assert conn.execute("SELECT general_electives FROM users WHERE id = 1").fetchone()[0] == 1
    conn.close()
    subjects = html(client, "/subjects")
    assert "Counted 4 subject(s) as general electives." in subjects and "4 of 4 chosen" in subjects


def test_walkthrough_a_heavy_semester(client, log_in):
    log_in()
    reset_to(client, "sample")
    planner = html(client, "/planner")
    assert "Autumn 2027" in planner and "Heavy" in planner


def test_walkthrough_set_up_a_degree_from_scratch(app, client, log_in):
    log_in()
    reset_to(client, "fresh")
    assert "Choose major" in html(client, "/subjects") and "Choose sub-major or electives" in html(client, "/subjects")
    post(client, "/major/MAJ03519/choose")
    post(client, "/submajor/SMJ10156/choose")
    for code in ("41039", "33130", "31265", "37181"):
        post(client, "/students/me/enrol", subject_code=code, session_label="Autumn 2027")
    assert "Programming 1" in html(client, "/timetable")
    assert post(client, "/planner/suggest").status_code == 303
    conn = db.connect(app.config["DATABASE"])
    assert conn.execute("SELECT COUNT(*) FROM planned_subjects WHERE user_id = 1").fetchone()[0] > 0
    assert conn.execute("SELECT COUNT(*) FROM enrolments WHERE user_id = 1 AND status = 'enrolled'").fetchone()[0] == 4
    conn.close()


def test_walkthrough_undo_a_semester(app, client, log_in):
    log_in()
    reset_to(client, "sample")
    post(client, "/simulator/finish", **{f"result_{c}": "passed" for c in ("31272", "32144", "41026", "41040")})
    assert "Simulation: <strong>Spring 2027</strong>" in html(client, "/planner")
    post(client, "/simulator/rollback")
    page = html(client, "/planner")
    assert "Simulation: <strong>Autumn 2027</strong>" in page and "is-disabled" in page


def test_walkthrough_ai_questions_have_somewhere_to_be_asked(client, log_in):
    log_in()
    reset_to(client, "late")
    post(client, "/ai/mode")
    assert 'class="ask-panel"' in html(client, "/planner") and "Explain this swap" in html(client, "/major/MAJ03445")


def test_walkthrough_plan_by_dragging_and_see_the_planner_say_no(app, client, log_in):
    log_in()
    reset_to(client, "failed")
    assert 'href="/planner/board"' in html(client, "/planner") and "Board view" in html(client, "/planner")
    board = client.get("/api/planner/board").get_json()
    assert "48024" in [c["code"] for c in board["to_place"] if c["retake"]]
    spring = next(c for c in board["columns"] if c["label"] == "Spring 2027")
    assert any(c["code"] == "31251" and c["problem"] for c in spring["cards"])
    ok = client.post("/api/planner/move", json={"code": "48024", "to": "Spring 2027"}, headers={"X-CSRF-Token": token(client)})
    assert ok.status_code == 200 and ok.get_json()["ok"] is True
    no = client.post("/api/planner/move", json={"code": "48024", "to": "Autumn 2029"}, headers={"X-CSRF-Token": token(client)})
    assert no.status_code == 422 and "needs 48024 Programming 2 first" in no.get_json()["error"]
    classic = html(client, "/planner")
    assert "Spring 2027" in classic and "48024" in classic  # the classic planner shows the same plan
