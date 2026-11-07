"""One rule for "when would I finish?", shared by the dashboard, the swap advice and the major comparison."""
import pytest

from features.advisor.service import SESSION_CP, assess, room_in_current_session, session_after, sessions_after_current
from features.dashboard.service import build_dashboard
from features.enrolment.presets import PRESETS
from features.enrolment.service import current_session_of
from shared import db

KEYS = list(PRESETS)


@pytest.fixture(scope="module")
def students(tmp_path_factory):
    out = {}
    for key in KEYS:
        path = tmp_path_factory.mktemp(key) / "t.db"
        db.build_database(str(path), demo_profile=key)
        out[key] = db.connect(str(path))
    yield out
    for conn in out.values():
        conn.close()


@pytest.mark.parametrize("counted,room,expected", [
    (0, 24, 7),      # nothing done, a whole session free: 8 sessions in all, 7 after this one
    (0, 0, 8),       # the same student with the current session already full
    (96, 0, 4), (120, 0, 3), (168, 0, 1),
    (170, 0, 1),     # 22 credit points left is still one more session
    (192, 0, 0), (200, 0, 0),
    (186, 6, 0),     # the 6 left fit in the room in this session
    (150, 6, 2),     # 42 left: 6 here, 36 more is two sessions
])
def test_sessions_still_needed_after_the_current_one(counted, room, expected):
    assert sessions_after_current(counted, room) == expected


def test_a_session_holds_24_credit_points():
    assert SESSION_CP == 24


@pytest.mark.parametrize("key,room", [("fresh", 24), ("sample", 0), ("late", 0), ("failed", 6)])
def test_the_room_left_is_24_minus_what_the_student_is_enrolled_in(students, key, room):
    conn = students[key]
    assert room_in_current_session(conn, 1, current_session_of(conn, 1)) == room


def test_a_first_year_is_projected_eight_sessions_from_autumn_2027(students):
    assert build_dashboard(students["fresh"], 1)["graduation"]["session"] == "Spring 2030"
    assert session_after("Autumn 2027", 7) == "Spring 2030"


@pytest.mark.parametrize("key", KEYS)
def test_the_dashboard_and_the_swap_advice_say_the_same_thing(students, key):
    conn = students[key]
    advice = assess(conn, 1, "major", "MAJ03519")
    assert advice["graduate_before"] == build_dashboard(conn, 1)["graduation"]["session"]


@pytest.mark.parametrize("key", KEYS)
def test_a_swap_never_brings_graduation_forward(students, key):
    conn = students[key]
    for code in ("MAJ10053", "MAJ02080", "MAJ02900", "MAJ03519", "MAJ02092", "MAJ01156", "MAJ03445", "MAJ02901"):
        advice = assess(conn, 1, "major", code)
        assert advice["extra_sessions"] >= 0 and advice["lost_cp"] >= 0
        assert advice["graduate_after"] == session_after(current_session_of(conn, 1), advice["extra_sessions"] + _sessions_before(conn, advice))


def _sessions_before(conn, advice):
    """The sessions the advice's own 'before' date implies, counted from the student's current session."""
    current = current_session_of(conn, 1)
    steps = 0
    while session_after(current, steps) != advice["graduate_before"]:
        steps += 1
        assert steps < 40
    return steps
