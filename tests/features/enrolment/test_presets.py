import re

import pytest

from features.accounts.seed import DEMO_PROFILES, DEMO_STUDENT_NUMBER
from features.advisor.service import assess
from features.degree_planner.service import get_plan
from features.enrolment import presets as presets_module
from features.enrolment.presets import DEFAULT_PRESET, PRESETS, preset_state
from features.enrolment.results import attempts_for
from features.enrolment.service import current_session_of, enrol, evaluate_subjects, next_session, session_sort_key, study_year
from shared import db
from features.simulator.service import SimulatorError, complete_semester, reset_demo_student, roll_back_semester
from features.subject_catalogue.service import load_credit_requirements, load_prerequisites
from features.transcript.service import transcript

KEYS = list(PRESETS)
TOKEN = re.compile(r'name="csrf_token" value="([^"]+)"')


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """One database per preset, built the way the app builds its own."""
    out = {}
    for key in KEYS:
        path = tmp_path_factory.mktemp(key) / "t.db"
        db.build_database(str(path), demo_profile=key)
        out[key] = db.connect(str(path))
    yield out
    for conn in out.values():
        conn.close()


def uid(conn):
    return conn.execute("SELECT id FROM users WHERE student_number = ?", (DEMO_STUDENT_NUMBER,)).fetchone()["id"]


def snap(conn):
    user = uid(conn)
    out = {}
    for table, cols in (("enrolments", "subject_code, status, session_label"), ("class_choices", "subject_code, component, class_id"),
                        ("planned_subjects", "subject_code, session_label"), ("elective_credits", "subject_code"), ("semester_log", "session_label"),
                        ("subject_attempts", "subject_code, session_label, attempt_number, outcome, mark, grade, source")):
        out[table] = sorted(tuple(r) for r in conn.execute(f"SELECT {cols} FROM {table} WHERE user_id = ?", (user,)))  # noqa: S608
    out["user"] = tuple(conn.execute("SELECT commencement_session, current_session, major_code, submajor_code, submajor_language, general_electives FROM users WHERE id = ?", (user,)).fetchone())
    return out


# --- the registry ------------------------------------------------------------------------------------------------------------------------

def test_the_presets_are_the_demo_profiles():
    assert KEYS == list(DEMO_PROFILES) == ["fresh", "sample", "late", "failed"] and DEFAULT_PRESET == "fresh"


@pytest.mark.parametrize("key", KEYS)
def test_every_preset_describes_itself(key):
    p = PRESETS[key]
    assert p["title"] and len(p["summary"]) > 30 and len(p["good_for"]) >= 3 and all(p["good_for"])
    assert preset_state(key) == (p["commencement"], p["current"], p["major"], p["submajor"])


# --- every preset is a valid student -----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("key", KEYS)
def test_the_student_row_matches_the_preset(built, key):
    conn = built[key]
    commencement, current, major, submajor = preset_state(key)
    row = conn.execute("SELECT commencement_session, current_session, major_code, submajor_code FROM users WHERE student_number = ?", (DEMO_STUDENT_NUMBER,)).fetchone()
    assert tuple(row) == (commencement, current, major, submajor)


@pytest.mark.parametrize("key", KEYS)
def test_the_finished_sessions_run_without_gaps_from_the_start_to_now(key):
    p = PRESETS[key]
    expected, label = [], p["commencement"]
    while label != p["current"]:
        expected.append(label)
        label = next_session(label)
    assert [s for s, _ in p["history"]] == expected


@pytest.mark.parametrize("key", KEYS)
def test_no_session_is_overloaded(built, key):
    conn = built[key]
    load = {}
    for r in conn.execute("SELECT a.session_label, s.credit_points FROM subject_attempts a JOIN subjects s ON s.code = a.subject_code WHERE a.user_id = ?", (uid(conn),)):
        load[r["session_label"]] = load.get(r["session_label"], 0) + r["credit_points"]
    for r in conn.execute("SELECT e.session_label, s.credit_points FROM enrolments e JOIN subjects s ON s.code = e.subject_code WHERE e.user_id = ? AND e.status = 'enrolled'", (uid(conn),)):
        load[r["session_label"]] = load.get(r["session_label"], 0) + r["credit_points"]
    assert all(cp <= 24 for cp in load.values()), load


@pytest.mark.parametrize("key", KEYS)
def test_every_subject_was_taken_in_a_session_that_offers_it(built, key):
    conn = built[key]
    rows = conn.execute("SELECT a.session_label, s.sessions_offered, a.subject_code FROM subject_attempts a JOIN subjects s ON s.code = a.subject_code WHERE a.user_id = ?", (uid(conn),)).fetchall()
    rows += conn.execute("SELECT e.session_label, s.sessions_offered, e.subject_code FROM enrolments e JOIN subjects s ON s.code = e.subject_code WHERE e.user_id = ? AND e.status = 'enrolled'", (uid(conn),)).fetchall()
    for r in rows:
        assert r["sessions_offered"] in (r["session_label"].split()[0], "Both"), tuple(r)


@pytest.mark.parametrize("key", KEYS)
def test_every_prerequisite_was_passed_in_an_earlier_session(built, key):
    conn = built[key]
    rules, credit = load_prerequisites(conn), load_credit_requirements(conn)
    user = uid(conn)
    passed = {r["subject_code"]: r["session_label"] for r in conn.execute("SELECT subject_code, session_label FROM subject_attempts WHERE user_id = ? AND outcome = 'passed'", (user,))}
    cps = {r["code"]: r["credit_points"] for r in conn.execute("SELECT code, credit_points FROM subjects")}
    members = {}
    for r in conn.execute("SELECT major_code, subject_code FROM major_subjects"):
        members.setdefault(r["major_code"], set()).add(r["subject_code"])
    taken = [(r["subject_code"], r["session_label"]) for r in conn.execute("SELECT subject_code, session_label FROM subject_attempts WHERE user_id = ?", (user,))]
    taken += [(r["subject_code"], r["session_label"]) for r in conn.execute("SELECT subject_code, session_label FROM enrolments WHERE user_id = ? AND status = 'enrolled'", (user,))]
    for code, session in taken:
        when = session_sort_key(session)
        for group in rules.get(code, []):
            assert any(alt in passed and (session_sort_key(passed[alt]) < when or (group["concurrent"] and session_sort_key(passed[alt]) <= when)) for alt in group["codes"]), (code, group["codes"])
        for req in credit.get(code, []):
            have = sum(cps[c] for c, s in passed.items() if session_sort_key(s) < when and (req["major_code"] is None or c in members.get(req["major_code"], ())))
            assert have >= req["min_cp"], (code, req["min_cp"], have)


@pytest.mark.parametrize("key", KEYS)
def test_attempts_and_enrolments_agree(built, key):
    conn = built[key]
    user = uid(conn)
    attempts = attempts_for(conn, user)
    passed = [a["subject_code"] for a in attempts if a["outcome"] == "passed"]
    assert len(passed) == len(set(passed))  # a subject is passed only once
    completed = [r[0] for r in conn.execute("SELECT subject_code FROM enrolments WHERE user_id = ? AND status = 'completed'", (user,))]
    assert sorted(completed) == sorted(passed)
    enrolled = [r[0] for r in conn.execute("SELECT subject_code FROM enrolments WHERE user_id = ? AND status = 'enrolled'", (user,))]
    assert not set(enrolled) & set(passed)
    for r in conn.execute("SELECT enrolled.session_label FROM enrolments enrolled WHERE enrolled.user_id = ? AND enrolled.status = 'enrolled'", (user,)):
        assert r[0] == current_session_of(conn, user)


@pytest.mark.parametrize("key", KEYS)
def test_planned_subjects_are_sensible(built, key):
    conn = built[key]
    user = uid(conn)
    for r in conn.execute("SELECT subject_code, session_label FROM planned_subjects WHERE user_id = ?", (user,)):
        assert session_sort_key(r["session_label"]) >= session_sort_key(current_session_of(conn, user))
        assert conn.execute("SELECT COUNT(*) FROM enrolments WHERE user_id = ? AND subject_code = ?", (user, r["subject_code"])).fetchone()[0] == 0


@pytest.mark.parametrize("key", KEYS)
def test_the_year_and_semester_follow_from_the_dates(built, key):
    conn = built[key]
    commencement, current = PRESETS[key]["commencement"], PRESETS[key]["current"]
    assert get_plan(conn, uid(conn))["period"]["year"] == study_year(commencement, current)


# --- what each preset is for ----------------------------------------------------------------------------------------------------------------

def test_fresh_has_nothing(built):
    conn = built["fresh"]
    assert attempts_for(conn, uid(conn)) == [] and get_plan(conn, uid(conn))["period"] == {"label": "Autumn 2027", "year": 1, "semester": 1}


def test_sample_is_halfway_through_the_major(built):
    conn = built["sample"]
    counts = get_plan(conn, uid(conn))["counts"]
    assert counts["completed"] == 16 and counts["enrolled"] == 4
    assert assess(conn, uid(conn), "major", "MAJ10053")["progress"]["major_percent"] == 62
    assert assess(conn, uid(conn), "major", "MAJ10053")["label"] == "Possible, but it costs time"


def test_late_is_nearly_through_the_major_and_swaps_need_care(built):
    conn = built["late"]
    plan = get_plan(conn, uid(conn))
    assert plan["period"] == {"label": "Spring 2027", "year": 3, "semester": 2} and plan["counts"]["completed"] == 20 and plan["counts"]["enrolled"] == 4
    swap = assess(conn, uid(conn), "major", "MAJ03445")
    assert swap["progress"]["major_percent"] == 88 and swap["label"] == "Think carefully" and swap["needs_ack"] is True
    assert swap["graduate_before"] != swap["graduate_after"]


def test_failed_has_a_failed_prerequisite_blocking_a_plan(built):
    conn = built["failed"]
    user = uid(conn)
    plan = get_plan(conn, user)
    assert plan["period"] == {"label": "Autumn 2027", "year": 2, "semester": 1}
    assert [r["code"] for r in plan["retakes"]] == ["48024"] and plan["counts"]["retake"] == 1 and plan["counts"]["blocked"] == 1
    blocked = [p for s in plan["sessions"] for p in s["planned"] if p.get("problem")]
    assert [p["code"] for p in blocked] == ["31251"] and "(failed: retake it first)" in blocked[0]["problem"]
    failed = [a for a in attempts_for(conn, user) if a["outcome"] == "failed"]
    assert [(a["subject_code"], a["session_label"], a["grade"]) for a in failed] == [("48024", "Spring 2026", "FL")]
    assert evaluate_subjects(conn, user)["subjects"]["31251"]["status"] == "blocked"


def test_the_failed_preset_can_be_played_through_to_a_pass(tmp_path):
    path = tmp_path / "f.db"
    db.build_database(str(path), demo_profile="failed")
    conn = db.connect(str(path))
    user = uid(conn)
    enrol(conn, user, "48024", "Autumn 2027")  # the retake fits: only 18 of 24 credit points are in use
    complete_semester(conn, user, {c: {"result": "passed", "mark": None} for c in ("31265", "37181", "41025", "48024")})
    attempts = [a for a in attempts_for(conn, user) if a["subject_code"] == "48024"]
    assert [(a["attempt_number"], a["outcome"]) for a in attempts] == [(1, "failed"), (2, "passed")]
    assert sum(1 for r in conn.execute("SELECT 1 FROM enrolments WHERE user_id = ? AND subject_code = '48024' AND status = 'completed'", (user,))) == 1
    assert evaluate_subjects(conn, user)["subjects"]["31251"]["status"] in ("available", "planned")  # no longer blocked
    roll_back_semester(conn, user)
    assert current_session_of(conn, user) == "Autumn 2027" and [a["outcome"] for a in attempts_for(conn, user) if a["subject_code"] == "48024"] == ["failed"]
    conn.close()


def test_a_pass_after_a_fail_in_a_preset_is_attempt_two(tmp_path, monkeypatch):
    custom = {**PRESETS["failed"], "history": [("Autumn 2026", [("41039", "failed")]), ("Spring 2026", [("41039", "passed")])], "current": "Autumn 2027", "enrolled": [], "plan": []}
    monkeypatch.setitem(PRESETS, "failed", custom)
    path = tmp_path / "c.db"
    db.build_database(str(path), demo_profile="failed")
    conn = db.connect(str(path))
    assert [(a["attempt_number"], a["outcome"]) for a in attempts_for(conn, uid(conn))] == [(1, "failed"), (2, "passed")]
    conn.close()


# --- resetting to a preset ----------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("target", KEYS)
def test_resetting_gives_exactly_the_same_as_a_fresh_build(conn, target, tmp_path):
    complete_semester(conn, 1, {})  # make a mess first: a finished semester, a rollback log entry
    reset_demo_student(conn, target)
    path = tmp_path / "ref.db"
    db.build_database(str(path), demo_profile=target)
    assert snap(conn) == snap(db.connect(str(path)))


@pytest.mark.parametrize("start", KEYS)
@pytest.mark.parametrize("target", KEYS)
def test_any_preset_can_follow_any_other(tmp_path, start, target):
    path = tmp_path / "x.db"
    db.build_database(str(path), demo_profile=start)
    conn = db.connect(str(path))
    reset_demo_student(conn, target)
    ref = tmp_path / "y.db"
    db.build_database(str(ref), demo_profile=target)
    assert snap(conn) == snap(db.connect(str(ref)))
    conn.close()


def test_an_unknown_starting_point_is_refused_and_nothing_changes(conn):
    before = snap(conn)
    for bad in ("nonsense", "", "FRESH", "sample; DROP TABLE users"):
        with pytest.raises(SimulatorError, match="Choose a starting point from the list"):
            reset_demo_student(conn, bad)
    assert snap(conn) == before


def test_other_students_are_untouched_by_a_reset(conn):
    from features.accounts.service import create_user

    other = create_user(conn, "other.student@student.uni.edu.au", "Str0ng#Pass", "Autumn 2027")["id"]
    complete_semester(conn, other, {})
    before = snap_user(conn, other)
    reset_demo_student(conn, "late")
    assert snap_user(conn, other) == before


def snap_user(conn, user):
    return (tuple(conn.execute("SELECT current_session, major_code FROM users WHERE id = ?", (user,)).fetchone()),
            conn.execute("SELECT COUNT(*) FROM semester_log WHERE user_id = ?", (user,)).fetchone()[0])


# --- the reset page -------------------------------------------------------------------------------------------------------------------------

def token(client, path="/profile"):
    return TOKEN.search(client.get(path).get_data(as_text=True)).group(1)


def html(client, url):
    return client.get(url, follow_redirects=True).get_data(as_text=True)


def test_the_reset_page_shows_a_card_for_every_preset(client, log_in):
    log_in()
    page = html(client, "/simulator/reset")
    assert page.count('class="preset"') == 4 and page.count('name="profile"') == 4 and 'value="fresh" checked' in page
    from markupsafe import escape

    for p in PRESETS.values():
        assert escape(p["title"]) in page and escape(p["summary"]) in page
        for item in p["good_for"]:
            assert escape(item) in page


@pytest.mark.parametrize("key", KEYS)
def test_choosing_a_preset_from_the_page_loads_it(app, client, log_in, key):
    log_in()
    res = client.post("/simulator/reset", data={"csrf_token": token(client), "confirm": "yes", "profile": key})
    assert res.status_code == 303 and res.headers["Location"].endswith("/planner")
    assert f"Simulation reset: {PRESETS[key]['title']}." in html(client, "/planner")
    conn = db.connect(app.config["DATABASE"])
    assert snap(conn)["user"][:4] == preset_state(key)  # commencement, current session, major, sub-major
    assert current_session_of(conn, 1) == PRESETS[key]["current"]
    conn.close()


def test_the_page_refuses_an_unknown_preset(app, client, log_in):
    log_in()
    client.post("/simulator/reset", data={"csrf_token": token(client), "confirm": "yes", "profile": "nonsense"})
    assert "Choose a starting point from the list." in html(client, "/simulator/reset")
    conn = db.connect(app.config["DATABASE"])
    assert len(attempts_for(conn, 1)) == 16  # unchanged
    conn.close()


def test_the_presets_are_known_to_the_ai_sources(conn):
    from ai_services.rag.retrieve import search

    assert "rule:presets" in [h["ref"] for h in search(conn, "how can I test a swap quickly with a preset")["hits"]]
    body = conn.execute("SELECT body FROM rag_chunks WHERE ref = 'rule:presets'").fetchone()[0]
    for text in ("62 percent", "88 percent", "Programming 2", "first-year student"):
        assert text in body
