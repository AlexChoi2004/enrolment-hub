import pytest

from accounts.service import create_user
from enrolment.service import evaluate_subjects


def demo(conn):
    return evaluate_subjects(conn, 1)


def status(result, code):
    return result["subjects"][code]["status"]


# --- the four statuses for the demo student ---------------------------------

def test_completed_subjects_are_marked_completed(conn):
    result = demo(conn)
    assert status(result, "41039") == "completed"
    assert result["subjects"]["41039"]["note"] == "Completed in Autumn 2025"


def test_subjects_in_progress_are_marked_enrolled(conn):
    result = demo(conn)
    assert status(result, "41026") == "enrolled"
    assert result["subjects"]["41026"]["note"] == "In progress in Autumn 2027"


def test_subjects_with_met_prerequisites_are_available(conn):
    result = demo(conn)
    assert status(result, "41052") == "available"  # Advanced Algorithms: needs 31251, completed
    assert status(result, "32113") == "available"  # Advanced Database: needs 31271, completed
    assert result["subjects"]["41052"]["note"] == ""


def test_subjects_with_no_prerequisites_are_available_if_not_taken(conn):
    assert status(demo(conn), "41759") == "available"  # Capstone has no supplied rule


def test_a_prerequisite_that_is_only_in_progress_does_not_unlock_a_subject(conn):
    result = demo(conn)
    assert status(result, "32931") == "blocked"  # Honours Project A needs 32144, which is enrolled
    assert result["subjects"]["32931"]["reasons"] == ["Needs 32144 Technology Research Preparation"]


def test_every_missing_prerequisite_is_named(conn):
    # Pretend the student has nothing completed for Advanced Software Development's chain.
    conn.execute("DELETE FROM enrolments WHERE subject_code IN ('41025', '41026')")
    result = demo(conn)
    assert status(result, "41026") == "blocked"
    assert "41025 Introduction to Software Development" in result["subjects"]["41026"]["note"]


# --- elective requirements ----------------------------------------------------

def test_all_four_general_electives_completed_blocks_the_rest(conn):
    result = demo(conn)
    general = [code for code in result["subjects"] if code.startswith("SYN")]
    states = {code: status(result, code) for code in general}
    assert sum(1 for s in states.values() if s == "completed") == 4
    assert sum(1 for s in states.values() if s == "blocked") == 8
    assert "available" not in states.values()
    blocked = next(code for code, s in states.items() if s == "blocked")
    assert result["subjects"][blocked]["reasons"] == ["General electives requirement already complete"]


def test_major_electives_stay_open_until_three_are_chosen(conn):
    result = demo(conn)
    progress = result["categories"]["major_elective"]
    assert (progress["completed"], progress["enrolled"], progress["counted_cp"]) == (0, 1, 6)
    assert status(result, "31777") == "available"


def test_major_electives_close_when_three_are_chosen(conn):
    conn.execute(
        "INSERT INTO enrolments (user_id, subject_code, status, session_label)"
        " VALUES (1, '41052', 'enrolled', 'Autumn 2027'), (1, '31777', 'enrolled', 'Autumn 2027')"
    )
    result = demo(conn)
    assert status(result, "41889") == "blocked"
    assert result["subjects"]["41889"]["reasons"] == ["Major electives requirement already complete"]
    assert status(result, "41052") == "enrolled"  # chosen ones keep their own status


def test_a_non_elective_subject_is_never_blocked_by_an_elective_limit(conn):
    assert status(demo(conn), "41759") == "available"


# --- category progress --------------------------------------------------------

def test_category_progress_counts_completed_and_in_progress(conn):
    categories = demo(conn)["categories"]
    assert (categories["core"]["completed"], categories["core"]["enrolled"], categories["core"]["pool"]) == (9, 1, 16)
    assert (categories["major_core"]["completed"], categories["major_core"]["enrolled"]) == (3, 1)
    assert categories["general_elective"]["counted_cp"] == 24
    assert categories["general_elective"]["required_cp"] == 24


def test_counted_credit_points_match_the_students_record(conn):
    categories = demo(conn)["categories"]
    assert sum(c["counted_cp"] for c in categories.values()) == 120  # 96 completed + 24 in progress


# --- other students ---------------------------------------------------------------

def test_a_new_student_has_nothing_completed_and_can_only_take_subjects_without_prerequisites(conn):
    user = create_user(conn, "new.student@student.uni.edu.au", "Str0ng#Pass", "Autumn 2027")
    result = evaluate_subjects(conn, user["id"])
    states = {code: info["status"] for code, info in result["subjects"].items()}
    assert "completed" not in states.values() and "enrolled" not in states.values()
    assert states["41039"] == "available"  # Programming 1: no prerequisite
    assert states["48024"] == "blocked"  # Programming 2 needs Programming 1
    assert states["41026"] == "blocked"
    assert states["SYN101"] == "available"  # general electives are open
    assert all(p["counted_cp"] == 0 for p in result["categories"].values())


def test_statuses_only_use_the_requested_students_records(conn):
    other = create_user(conn, "other.student@student.uni.edu.au", "Str0ng#Pass", "Autumn 2027")
    conn.execute(
        "INSERT INTO enrolments (user_id, subject_code, status, session_label)"
        " VALUES (?, '41039', 'completed', 'Autumn 2027')",
        (other["id"],),
    )
    assert status(evaluate_subjects(conn, other["id"]), "48024") == "available"
    assert status(evaluate_subjects(conn, other["id"]), "33130") == "available"  # demo's history is not theirs
    assert status(evaluate_subjects(conn, other["id"]), "41025") == "available"


@pytest.mark.parametrize("code", ["41039", "41026", "41052", "32931"])
def test_every_subject_gets_exactly_one_status(conn, code):
    assert status(demo(conn), code) in {"completed", "enrolled", "available", "blocked"}