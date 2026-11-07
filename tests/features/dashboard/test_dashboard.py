import json
import re

import pytest

from features.advisor.service import assess
from features.dashboard.service import MAX_SESSIONS, MAX_STEPS, build_dashboard
from features.degree_planner.service import get_plan
from features.enrolment.presets import PRESETS
from shared import db

TOKEN = re.compile(r'name="csrf_token" value="([^"]+)"')
KEYS = list(PRESETS)
SHAPE = {"student", "period", "degree", "counts", "choices", "categories", "graduation", "sessions", "next_steps"}


@pytest.fixture(scope="module")
def data(tmp_path_factory):
    """The dashboard for each starting point, built from a database made the way the app makes its own."""
    out = {}
    for key in KEYS:
        path = tmp_path_factory.mktemp(key) / "t.db"
        db.build_database(str(path), demo_profile=key)
        conn = db.connect(str(path))
        out[key] = (build_dashboard(conn, 1), conn)
    yield out
    for _, conn in out.values():
        conn.close()


def token(client, path="/profile"):
    return TOKEN.search(client.get(path).get_data(as_text=True)).group(1)


def html(client, url):
    return client.get(url, follow_redirects=True).get_data(as_text=True)


# --- the data -----------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("key", KEYS)
def test_the_dashboard_has_the_agreed_shape_and_is_plain_json(data, key):
    d, _ = data[key]
    assert set(d) == SHAPE and json.loads(json.dumps(d)) == d


@pytest.mark.parametrize("key", KEYS)
def test_the_numbers_come_from_the_planner(data, key):
    d, conn = data[key]
    plan = get_plan(conn, 1)
    assert d["degree"] == {"total_cp": 192, "completed_cp": plan["completed_cp"], "enrolled_cp": plan["enrolled_cp"],
                           "planned_cp": plan["planned_cp"], "remaining_cp": plan["remaining_cp"]}
    assert d["period"] == plan["period"] and d["counts"]["completed"] == plan["counts"]["completed"]


@pytest.mark.parametrize("key", KEYS)
def test_the_requirements_add_up_to_the_whole_degree_and_never_overfill(data, key):
    d, _ = data[key]
    assert sum(c["required_cp"] for c in d["categories"]) == 192
    for c in d["categories"]:
        assert c["completed_cp"] + c["enrolled_cp"] + c["planned_cp"] <= c["required_cp"] and min(c["completed_cp"], c["enrolled_cp"], c["planned_cp"]) >= 0


@pytest.mark.parametrize("key", ["sample", "late", "failed"])
def test_credit_points_in_the_requirements_match_the_degree_totals(data, key):
    d, _ = data[key]
    assert sum(c["completed_cp"] for c in d["categories"]) == d["degree"]["completed_cp"]
    assert sum(c["enrolled_cp"] for c in d["categories"]) == d["degree"]["enrolled_cp"]


def test_a_first_year_sees_the_major_and_pathway_as_not_chosen_yet(data):
    d, _ = data["fresh"]
    assert d["choices"] == {"major": {"name": None}, "pathway": {"kind": None, "name": None}}
    pending = [c for c in d["categories"] if c["pending"]]
    assert [(c["key"], c["required_cp"]) for c in pending] == [("major_pending", 48), ("submajor_pending", 24)]
    assert not any(c["pending"] for c in data["sample"][0]["categories"])


def test_the_chosen_major_and_sub_major_are_named(data):
    d, _ = data["sample"]
    assert d["choices"] == {"major": {"name": "Enterprise Software Development"}, "pathway": {"kind": "submajor", "name": "Innovation and Entrepreneurship"}}


def test_the_student_is_named(data):
    assert data["sample"][0]["student"] == {"display_name": "John Doe"}


# --- graduation ---------------------------------------------------------------------------------------------------------------------------------

def test_a_first_year_is_projected_eight_sessions_not_nine(data):
    g = data["fresh"][0]["graduation"]
    assert g == {"session": "Spring 2030", "sessions_left": 7, "remaining_cp": 192, "finished": False}


@pytest.mark.parametrize("key", ["sample", "late", "failed"])
def test_the_projection_agrees_with_the_swap_advice(data, key):
    d, conn = data[key]
    assert d["graduation"]["session"] == assess(conn, 1, "major", "MAJ03519")["graduate_before"]


def test_the_sample_student_finishes_in_spring_2028(data):
    assert data["sample"][0]["graduation"] == {"session": "Spring 2028", "sessions_left": 3, "remaining_cp": 72, "finished": False}


# --- sessions and next steps ----------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("key", KEYS)
def test_sessions_start_with_the_current_one_and_are_limited(data, key):
    d, _ = data[key]
    assert d["sessions"][0]["current"] is True and d["sessions"][0]["label"] == d["period"]["label"] and len(d["sessions"]) <= MAX_SESSIONS
    assert all(s["workload"] in (None, "light", "balanced", "heavy", "too_heavy") for s in d["sessions"])


def test_a_heavy_session_is_flagged_by_the_planners_own_verdict(data):
    s = data["sample"][0]["sessions"][0]
    assert (s["workload"], s["workload_label"], s["load_cp"]) == ("heavy", "Heavy", 24)
    assert data["late"][0]["sessions"][0]["workload"] == "too_heavy"


@pytest.mark.parametrize("key", KEYS)
def test_next_steps_are_few_and_point_at_real_pages(data, key):
    d, _ = data[key]
    assert 0 < len(d["next_steps"]) <= MAX_STEPS
    assert all(s["href"] in ("/major", "/submajor", "/planner", "/subjects") and s["text"] and s["severity"] in ("info", "warning") for s in d["next_steps"])


def test_a_first_year_is_told_to_choose_a_major_then_a_pathway_then_enrol(data):
    steps = data["fresh"][0]["next_steps"]
    assert [s["kind"] for s in steps] == ["setup", "setup", "enrol"] and steps[0]["href"] == "/major" and steps[1]["href"] == "/submajor"


def test_a_failed_prerequisite_shows_the_retake_and_the_blocked_subject(data):
    steps = data["failed"][0]["next_steps"]
    kinds = [s["kind"] for s in steps]
    assert kinds[:2] == ["retake", "blocked"] and "48024 Programming 2 was failed" in steps[0]["text"]
    assert "(failed: retake it first)" in steps[1]["text"] and data["failed"][0]["counts"]["retake"] == 1


# --- the page and the data endpoint ------------------------------------------------------------------------------------------------------------

def test_the_dashboard_needs_a_login(client):
    assert client.get("/dashboard").status_code == 302 and client.get("/api/dashboard").status_code == 302


def test_the_endpoint_returns_the_students_own_data_and_is_never_cached(client, log_in):
    log_in()
    res = client.get("/api/dashboard")
    assert res.status_code == 200 and res.headers["Content-Type"] == "application/json" and res.headers["Cache-Control"] == "no-store"
    assert set(res.get_json()) == SHAPE and res.get_json()["student"]["display_name"] == "John Doe"


def test_the_endpoint_only_answers_get(client, log_in):
    log_in()
    for method in (client.post, client.put, client.delete, client.patch):
        assert method("/api/dashboard", data={"csrf_token": token(client)}).status_code == 405


def test_the_endpoint_does_not_change_any_data(app, client, log_in):
    log_in()
    conn = db.connect(app.config["DATABASE"])
    before = [sorted(tuple(r) for r in conn.execute(f"SELECT * FROM {t}")) for t in ("users", "enrolments", "planned_subjects", "subject_attempts")]  # noqa: S608
    client.get("/api/dashboard")
    client.get("/dashboard")
    assert before == [sorted(tuple(r) for r in conn.execute(f"SELECT * FROM {t}")) for t in ("users", "enrolments", "planned_subjects", "subject_attempts")]  # noqa: S608
    conn.close()


def test_one_student_never_sees_anothers_data(client, register):
    register()
    res = client.get("/api/dashboard")
    body = res.get_data(as_text=True)
    assert "John" not in body and res.get_json()["student"]["display_name"] == "Jane Smith" and res.get_json()["degree"]["completed_cp"] == 0


def test_the_page_has_a_plain_version_for_when_javascript_is_off(client, log_in):
    log_in()
    page = html(client, "/dashboard")
    assert '<div id="dashboard-root" data-endpoint="/api/dashboard">' in page
    assert "96 of 192 credit points completed, 24 in progress, 0 planned." in page and "Projected graduation: <strong>Spring 2028</strong>" in page
    assert "Next steps" in page


def test_the_page_loads_the_built_script_as_a_module_with_no_inline_code(client, log_in):
    log_in()
    page = html(client, "/dashboard")
    assert '<script type="module" src="/static/dist/dashboard.js"></script>' in page
    assert '<link rel="stylesheet" href="/static/dist/dashboard.css">' in page
    assert all("src=" in s for s in re.findall(r"<script[^>]*>", page))


def test_the_built_files_are_in_the_repository(client):
    for name, marker in (("dashboard.js", b"dashboard-root"), ("dashboard.css", b".dash-")):
        res = client.get(f"/static/dist/{name}")
        assert res.status_code == 200 and marker in res.data and len(res.data) > 1000


# --- landing on the dashboard ----------------------------------------------------------------------------------------------------------------------------

def test_the_dashboard_is_the_first_link_and_marked_when_open(client, log_in):
    log_in()
    nav = html(client, "/dashboard").split('<nav class="nav-main" aria-label="Main">', 1)[1].split("</nav>", 1)[0]
    assert re.findall(r">([^<]+)</a>", nav)[:2] == ["Dashboard", "Subjects"] and 'href="/dashboard" aria-current="page"' in nav


def test_visitors_do_not_see_the_dashboard_link(client):
    assert ">Dashboard<" not in html(client, "/login")


def test_the_help_page_explains_the_dashboard(client):
    page = html(client, "/help")
    assert "<dt>Dashboard</dt>" in page and "The first page after you log in" in page and "You land on the <strong>Dashboard</strong>" in page
