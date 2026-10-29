import sqlite3

import pytest

from accounts.seed import DEMO_STUDENT_NUMBER
from enrolment.seed import CURRENT_SESSION
from enrolment.service import session_sort_key


@pytest.fixture()
def history(conn):
    user = conn.execute("SELECT id FROM users WHERE student_number = ?", (DEMO_STUDENT_NUMBER,)).fetchone()
    rows = conn.execute(
        "SELECT e.subject_code, e.status, e.session_label, s.credit_points, s.sessions_offered"
        " FROM enrolments e JOIN subjects s ON s.code = e.subject_code WHERE e.user_id = ?",
        (user["id"],),
    ).fetchall()
    return [dict(r) for r in rows]


def prerequisites(conn):
    out = {}
    for row in conn.execute("SELECT subject_code, prereq_code FROM prerequisites"):
        out.setdefault(row["subject_code"], []).append(row["prereq_code"])
    return out


def test_demo_student_is_on_the_course_with_a_fixed_identity(conn):
    user = conn.execute("SELECT * FROM users WHERE student_number = ?", (DEMO_STUDENT_NUMBER,)).fetchone()
    assert user["email"] == "john.doe@student.uni.edu.au"
    assert user["display_name"] == "John Doe"
    assert user["course_code"] == "C09119"
    assert user["commencement_session"] == "Autumn 2025"


def test_demo_student_is_about_two_years_in(history):
    completed = [h for h in history if h["status"] == "completed"]
    enrolled = [h for h in history if h["status"] == "enrolled"]
    assert len(completed) == 16
    assert sum(h["credit_points"] for h in completed) == 96  # two years of a 192 cp degree
    assert len(enrolled) == 4
    assert sum(h["credit_points"] for h in enrolled) == 24
    assert {h["session_label"] for h in enrolled} == {CURRENT_SESSION}


def test_credit_points_are_not_double_counted(conn, history):
    codes = [h["subject_code"] for h in history]
    assert len(codes) == len(set(codes))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO enrolments (user_id, subject_code, status, session_label)"
            " VALUES (1, ?, 'enrolled', 'Autumn 2027')",
            (codes[0],),
        )


def test_every_prerequisite_was_completed_in_an_earlier_session(conn, history):
    prereqs = prerequisites(conn)
    done = {h["subject_code"]: h for h in history if h["status"] == "completed"}
    for h in history:
        for needed in prereqs.get(h["subject_code"], []):
            assert needed in done, f"{h['subject_code']} needs {needed}, which is not completed"
            assert session_sort_key(done[needed]["session_label"]) < session_sort_key(h["session_label"])


def test_subjects_were_taken_in_sessions_they_are_offered(history):
    for h in history:
        season = h["session_label"].split()[0]
        assert h["sessions_offered"] in (season, "Both"), h


def test_history_leaves_some_subjects_available_and_some_blocked(conn, history):
    status = {h["subject_code"]: h["status"] for h in history}
    prereqs = prerequisites(conn)
    # Available: not yet taken, and every prerequisite is completed.
    assert "41052" not in status and status["31251"] == "completed"  # Advanced Algorithms is open
    assert "32113" not in status and status["31271"] == "completed"  # Advanced Database is open
    # Blocked: its prerequisite is only in progress, not completed.
    assert "32931" not in status
    assert status[prereqs["32931"][0]] == "enrolled"  # Honours Project A waits on Technology Research Prep


def test_session_sort_key_orders_autumn_before_spring_and_by_year():
    labels = ["Autumn 2027", "Spring 2025", "Autumn 2025", "Spring 2026", "Autumn 2026"]
    assert sorted(labels, key=session_sort_key) == [
        "Autumn 2025", "Spring 2025", "Autumn 2026", "Spring 2026", "Autumn 2027",
    ]


def test_rebuilding_the_database_gives_identical_demo_history(tmp_path):
    from shared import db

    def snapshot(name):
        path = tmp_path / name
        db.build_database(str(path))
        conn = db.connect(str(path))
        rows = conn.execute(
            "SELECT subject_code, status, session_label FROM enrolments ORDER BY subject_code"
        ).fetchall()
        conn.close()
        return [tuple(r) for r in rows]

    assert snapshot("a.db") == snapshot("b.db")