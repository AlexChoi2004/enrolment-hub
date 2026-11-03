import re

import pytest

from enrolment.results import attempts_for
from enrolment.service import current_session_of, get_record
from shared import db
from simulator.service import SimulatorError, complete_semester, current_state, reset_demo_student
from submajors.service import choose_submajor
from subject_catalogue import service as catalogue
from transcript.service import transcript

TOKEN = re.compile(r'name="csrf_token" value="([^"]+)"')


@pytest.fixture()
def fresh_conn(tmp_path):
    path = tmp_path / "fresh.db"
    db.build_database(str(path), demo_profile="fresh")
    conn = db.connect(str(path))
    yield conn
    conn.close()


# --- a fresh first-year student ------------------------------------------------------------------------------------------------

def test_the_fresh_demo_student_is_in_year_one_semester_one(fresh_conn):
    state = current_state(fresh_conn, 1)
    assert (state["label"], state["year"], state["semester"]) == ("Autumn 2027", 1, 1)
    assert state["subjects"] == []


def test_the_fresh_demo_student_has_no_history_at_all(fresh_conn):
    for table in ("enrolments", "subject_attempts", "planned_subjects", "class_choices"):
        assert fresh_conn.execute(f"SELECT COUNT(*) FROM {table} WHERE user_id = 1").fetchone()[0] == 0  # noqa: S608
    assert get_record(fresh_conn, 1)["completed_cp"] == 0 and transcript(fresh_conn, 1)["groups"] == []


def test_the_fresh_demo_student_has_a_major_but_no_sub_major_yet(fresh_conn):
    row = fresh_conn.execute("SELECT major_code, submajor_code, general_electives FROM users WHERE id = 1").fetchone()
    assert tuple(row) == ("MAJ03519", None, 0)
    assert catalogue.user_submajor(fresh_conn, 1) is None


def test_the_fresh_student_can_choose_a_sub_major_like_anyone(fresh_conn):
    choose_submajor(fresh_conn, 1, "SMJ10156")
    assert catalogue.user_submajor(fresh_conn, 1)["code"] == "SMJ10156"


def test_the_fresh_demo_student_can_still_use_the_simulator(fresh_conn):
    done = complete_semester(fresh_conn, 1, {})
    assert done["to"] == "Spring 2027" and current_session_of(fresh_conn, 1) == "Spring 2027"


def test_the_demo_login_is_the_same_whichever_profile(fresh_conn, conn):
    assert fresh_conn.execute("SELECT email, student_number FROM users WHERE id = 1").fetchone()[:] == \
        conn.execute("SELECT email, student_number FROM users WHERE id = 1").fetchone()[:]


def test_the_real_apps_default_is_the_fresh_profile(tmp_path, monkeypatch):
    from app import create_app

    monkeypatch.delenv("DEMO_PROFILE", raising=False)
    monkeypatch.delenv("ALLOW_REGISTRATION", raising=False)
    app = create_app({"DATABASE": str(tmp_path / "real.db"), "TESTING": True, "SECRET_KEY": "k"})
    assert app.config["DEMO_PROFILE"] == "fresh" and app.config["ALLOW_REGISTRATION"] is False
    c = db.connect(str(tmp_path / "real.db"))
    assert c.execute("SELECT COUNT(*) FROM enrolments").fetchone()[0] == 0
    c.close()


def test_the_profile_can_be_chosen_in_the_environment(tmp_path, monkeypatch):
    from app import create_app

    monkeypatch.setenv("DEMO_PROFILE", "sample")
    create_app({"DATABASE": str(tmp_path / "sample.db"), "TESTING": True, "SECRET_KEY": "k"})
    c = db.connect(str(tmp_path / "sample.db"))
    assert c.execute("SELECT COUNT(*) FROM enrolments WHERE status = 'completed'").fetchone()[0] == 16
    c.close()


# --- resetting to either ---------------------------------------------------------------------------------------------------------

def test_a_reset_to_fresh_removes_everything_and_restarts_the_year(conn):
    complete_semester(conn, 1, {})
    reset_demo_student(conn, "fresh")
    state = current_state(conn, 1)
    assert (state["label"], state["year"], state["semester"]) == ("Autumn 2027", 1, 1)
    assert attempts_for(conn, 1) == [] and conn.execute("SELECT COUNT(*) FROM enrolments WHERE user_id = 1").fetchone()[0] == 0
    assert conn.execute("SELECT commencement_session, submajor_code FROM users WHERE id = 1").fetchone()[:] == ("Autumn 2027", None)


def test_a_reset_to_the_sample_history_restores_year_three(conn):
    reset_demo_student(conn, "fresh")
    reset_demo_student(conn, "sample")
    state = current_state(conn, 1)
    assert (state["year"], state["semester"], len(state["subjects"])) == (3, 1, 4)
    assert len(attempts_for(conn, 1)) == 16 and catalogue.user_submajor(conn, 1)["code"] == "SMJ10156"


def test_switching_back_and_forth_is_reliable_after_several_semesters(conn):
    for _ in range(3):
        complete_semester(conn, 1, {})
        reset_demo_student(conn, "fresh")
        complete_semester(conn, 1, {})
        reset_demo_student(conn, "sample")
    assert len(attempts_for(conn, 1)) == 16 and current_session_of(conn, 1) == "Autumn 2027"


def test_an_unknown_profile_is_refused_and_nothing_changes(conn):
    before = attempts_for(conn, 1)
    with pytest.raises(SimulatorError, match="Choose how to start again"):
        reset_demo_student(conn, "nonsense")
    assert attempts_for(conn, 1) == before


def test_the_reset_page_offers_both_starts(client, log_in):
    log_in()
    page = client.get("/simulator/reset").get_data(as_text=True)
    assert 'value="fresh" checked' in page and 'value="sample"' in page
    assert "Start as a first-year student" in page and "Load the sample two-year history" in page


def test_the_reset_page_defaults_to_a_first_year_student(app, client, log_in):
    log_in()
    token = TOKEN.search(client.get("/simulator/reset").get_data(as_text=True)).group(1)
    client.post("/simulator/reset", data={"csrf_token": token, "confirm": "yes"})
    conn = db.connect(app.config["DATABASE"])
    assert conn.execute("SELECT COUNT(*) FROM subject_attempts WHERE user_id = 1").fetchone()[0] == 0
    conn.close()


def test_an_unknown_profile_on_the_page_is_refused(app, client, log_in):
    log_in()
    token = TOKEN.search(client.get("/simulator/reset").get_data(as_text=True)).group(1)
    client.post("/simulator/reset", data={"csrf_token": token, "confirm": "yes", "profile": "nonsense"})
    conn = db.connect(app.config["DATABASE"])
    assert conn.execute("SELECT COUNT(*) FROM subject_attempts WHERE user_id = 1").fetchone()[0] == 16  # unchanged
    conn.close()
