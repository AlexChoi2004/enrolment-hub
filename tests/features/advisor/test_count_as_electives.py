import re

import pytest

from features.accounts.service import create_user
from features.advisor.service import ElectiveChoiceError, assess, validate_electives
from features.degree_planner.service import get_plan
from features.enrolment.results import record_result
from features.enrolment.service import evaluate_subjects
from features.majors.service import choose_major
from shared import db
from features.simulator.service import reset_demo_student
from features.submajors.service import choose_electives, choose_submajor
from features.subject_catalogue import service as catalogue

AUTUMN = "Autumn 2027"
SUB_CORE = ["48080", "81529", "81546", "81547"]  # John's completed Innovation and Entrepreneurship subjects
TOKEN = re.compile(r'name="csrf_token" value="([^"]+)"')


def rows(conn, user=1):
    return sorted(r[0] for r in conn.execute("SELECT subject_code FROM elective_credits WHERE user_id = ?", (user,)))


def categories(conn, user=1):
    return {c["category"]: c for c in catalogue.degree_categories(conn, user)}


@pytest.fixture()
def electives_student(conn):
    """A student with a major, six subjects done, on the general electives path with nothing counted as electives yet."""
    user = create_user(conn, "new.student@student.uni.edu.au", "Str0ng#Pass", AUTUMN)["id"]
    choose_major(conn, user, "MAJ03519")
    for code in ("41039", "33130", "31265", "37181", "31268", "41092", "48024", "41025", "31251", "41052"):
        record_result(conn, user, code, "Autumn 2026", "passed")  # 41025 and 41052 only count in the ESD major
    choose_electives(conn, user)
    return user


# --- when the prompt appears ----------------------------------------------------------------------------------------------------

def test_moving_a_sub_major_to_electives_offers_to_count_its_subjects(conn):
    offer = assess(conn, 1, "electives")["electives_offer"]
    assert offer["space_cp"] == 24 and offer["max_cp"] == 24
    assert [e["code"] for e in offer["eligible"]] == SUB_CORE
    assert {e["status"] for e in offer["eligible"]} == {"completed"}


def test_no_offer_for_a_student_on_a_sub_major_because_there_is_no_electives_block(conn):
    assert assess(conn, 1, "major", "MAJ10053")["electives_offer"] is None  # John is on a sub-major
    assert assess(conn, 1, "submajor", "SMJ10157")["electives_offer"] is None


def test_no_offer_when_nothing_would_stop_counting(electives_student, conn):
    assert assess(conn, electives_student, "major", "MAJ03519")["electives_offer"] is None  # the same major


def test_no_offer_for_a_first_choice(conn):
    fresh = create_user(conn, "fresh.student@student.uni.edu.au", "Str0ng#Pass", AUTUMN)["id"]
    assert assess(conn, fresh, "electives")["electives_offer"] is None


def test_a_major_swap_on_the_electives_path_offers_the_lost_major_subjects(electives_student, conn):
    offer = assess(conn, electives_student, "major", "MAJ10053")["electives_offer"]
    assert offer["space_cp"] == 24 and "41025" in [e["code"] for e in offer["eligible"]]


def test_the_offer_only_covers_the_space_that_is_free(electives_student, conn):
    for code in ("SYN101", "SYN103"):
        record_result(conn, electives_student, code, "Autumn 2026", "passed")  # 12 of the 24 cp are used
    assert assess(conn, electives_student, "major", "MAJ10053")["electives_offer"]["space_cp"] == 12


def test_planned_electives_also_use_up_the_space(electives_student, conn):
    from features.degree_planner.service import add_to_plan

    add_to_plan(conn, electives_student, "SYN101", "Spring 2027")
    assert assess(conn, electives_student, "major", "MAJ10053")["electives_offer"]["space_cp"] == 18


def test_a_full_electives_block_means_no_offer(electives_student, conn):
    for code in ("SYN101", "SYN103", "SYN106", "SYN109"):
        record_result(conn, electives_student, code, "Autumn 2026", "passed")
    assert assess(conn, electives_student, "major", "MAJ10053")["electives_offer"] is None


# --- the effect on the advice ---------------------------------------------------------------------------------------------------

def test_counting_every_subject_as_electives_makes_the_swap_free(conn):
    plain = assess(conn, 1, "electives")
    counted = assess(conn, 1, "electives", elective_codes=SUB_CORE)
    assert plain["tier"] == "costs_time" and plain["lost_cp"] == 24
    assert counted["tier"] == "good" and counted["lost_cp"] == 0 and counted["extra_sessions"] == 0 and counted["needs_ack"] is False
    assert counted["counted_as_electives"] == SUB_CORE and counted["graduate_before"] == counted["graduate_after"]


def test_counting_some_of_them_reduces_what_is_lost(conn):
    two = assess(conn, 1, "electives", elective_codes=SUB_CORE[:2])
    assert two["lost_cp"] == 12 and two["tier"] == "costs_time"


def test_the_offer_is_the_same_whether_or_not_choices_are_applied(conn):
    assert assess(conn, 1, "electives")["electives_offer"] == assess(conn, 1, "electives", elective_codes=SUB_CORE)["electives_offer"]


def test_assessing_with_choices_never_saves_them(conn):
    assess(conn, 1, "electives", elective_codes=SUB_CORE)
    assert rows(conn) == [] and tuple(conn.execute("SELECT submajor_code, general_electives FROM users WHERE id = 1").fetchone()) == ("SMJ10156", 0)


# --- checking the choices --------------------------------------------------------------------------------------------------------

def test_no_choices_is_always_fine(conn):
    assert validate_electives(conn, 1, "electives", None, None, []) == []
    assert validate_electives(conn, 1, "major", "MAJ10053", None, []) == []


def test_duplicates_are_removed_and_valid_choices_pass(conn):
    assert validate_electives(conn, 1, "electives", None, None, ["48080", "48080", "81529"]) == ["48080", "81529"]


@pytest.mark.parametrize("codes", [["41039"], ["00000"], ["48080", "41026"], ["'; DROP TABLE subjects;--"]])
def test_a_subject_that_would_not_stop_counting_cannot_be_chosen(conn, codes):
    with pytest.raises(ElectiveChoiceError, match="can't be counted as general electives"):
        validate_electives(conn, 1, "electives", None, None, codes)


def test_a_subject_that_is_only_planned_cannot_be_chosen(electives_student, conn):
    from features.degree_planner.service import add_to_plan

    add_to_plan(conn, electives_student, "31269", "Spring 2027")  # planned, not done, so it cannot be counted
    with pytest.raises(ElectiveChoiceError, match="can't be counted"):
        validate_electives(conn, electives_student, "major", "MAJ10053", None, ["31269"])


def test_more_than_the_free_space_is_refused(electives_student, conn):
    for code in ("SYN101", "SYN103", "SYN106"):
        record_result(conn, electives_student, code, "Autumn 2026", "passed")  # 18 used, 6 free
    with pytest.raises(ElectiveChoiceError, match="Only 6 credit points of general electives are free; you chose 12"):
        validate_electives(conn, electives_student, "major", "MAJ10053", None, ["41025", "41052"])


def test_choosing_when_there_is_no_room_is_refused(conn):
    with pytest.raises(ElectiveChoiceError, match="no room for general electives"):
        validate_electives(conn, 1, "major", "MAJ10053", None, ["41025"])  # John is on a sub-major


# --- making the swap with them ---------------------------------------------------------------------------------------------------

def test_the_chosen_subjects_count_as_general_electives_after_the_swap(conn):
    result = choose_electives(conn, 1, count_as_electives=SUB_CORE)
    assert result["counted_as_electives"] == 4 and result["no_longer_counted"] == 0
    assert rows(conn) == sorted(SUB_CORE)
    cats = categories(conn)
    assert "sub_core" not in cats and cats["general_elective"]["required_credit_points"] == 24
    progress = evaluate_subjects(conn, 1)["categories"]["general_elective"]
    assert progress["counted_cp"] == 24 and progress["completed"] == 4


def test_counted_subjects_keep_their_completed_status_and_fill_the_block(conn):
    choose_electives(conn, 1, count_as_electives=SUB_CORE)
    subjects = evaluate_subjects(conn, 1)["subjects"]
    assert all(subjects[c]["status"] == "completed" for c in SUB_CORE)
    assert subjects["SYN102"]["reasons"] == ["General electives requirement already complete"]  # the block is full


def test_the_credit_points_are_not_counted_twice(conn):
    choose_electives(conn, 1, count_as_electives=SUB_CORE)
    plan = get_plan(conn, 1)
    assert plan["completed_cp"] + plan["enrolled_cp"] + plan["planned_cp"] + plan["remaining_cp"] == 192
    assert plan["extra_cp"] == 0


def test_without_choices_they_stay_on_the_record_but_do_not_count(conn):
    result = choose_electives(conn, 1)
    assert result["counted_as_electives"] == 0 and result["no_longer_counted"] == 4 and rows(conn) == []
    assert get_plan(conn, 1)["extra_cp"] == 24


def test_a_stray_choice_is_ignored_when_not_on_the_electives_path(conn):
    from features.majors.service import choose_major as swap

    swap(conn, 1, "MAJ10053", count_as_electives=["41025"])  # John is on a sub-major: nothing can be counted
    assert rows(conn) == [] and "41025" not in {s["code"] for s in catalogue.degree_subjects(conn, 1) if s["in_degree"]}


def test_a_major_swap_on_the_electives_path_counts_the_chosen_subjects(electives_student, conn):
    result = choose_major(conn, electives_student, "MAJ10053", count_as_electives=["41025", "41052"])
    assert result["counted_as_electives"] == 2 and rows(conn, electives_student) == ["41025", "41052"]
    in_degree = {s["code"]: s["category"] for s in catalogue.degree_subjects(conn, electives_student) if s["in_degree"]}
    assert in_degree["41025"] == "general_elective" and in_degree["41052"] == "general_elective"
    assert in_degree["48024"] == "core"  # a core subject still counts as core


def test_leaving_the_electives_path_clears_the_choices(conn):
    choose_electives(conn, 1, count_as_electives=SUB_CORE)
    choose_submajor(conn, 1, "SMJ10157")
    assert rows(conn) == []
    assert all(s["category"] != "general_elective" for s in catalogue.degree_subjects(conn, 1))


def test_a_reset_removes_the_choices(conn):
    choose_electives(conn, 1, count_as_electives=SUB_CORE)
    reset_demo_student(conn, "sample")
    assert rows(conn) == []


def test_other_students_are_untouched(conn, electives_student):
    choose_electives(conn, 1, count_as_electives=SUB_CORE)
    assert rows(conn, electives_student) == []


# --- the pages ------------------------------------------------------------------------------------------------------------------------

def token(client, path="/subjects"):
    return TOKEN.search(client.get(path).get_data(as_text=True)).group(1)


def html(client, url):
    return client.get(url, follow_redirects=True).get_data(as_text=True)


def stored_rows(app, user=1):
    conn = db.connect(app.config["DATABASE"])
    try:
        return rows(conn, user)
    finally:
        conn.close()


def test_the_electives_page_offers_the_subjects_with_checkboxes(client, log_in):
    log_in()
    page = html(client, "/submajor/electives")
    assert "Count these as general electives?" in page and "<strong>24</strong> credit points of that block are still free" in page
    assert page.count('name="count_as_electives"') == 4 and 'value="48080"' in page and "(6 cp, completed)" in page


def test_the_major_swap_page_has_no_offer_for_a_sub_major_student(client, log_in):
    log_in()
    assert "Count these as general electives?" not in html(client, "/major/MAJ10053")


def test_ticking_all_of_them_lets_the_swap_through_without_the_cost_tick(app, client, log_in):
    log_in()
    data = {"csrf_token": token(client), "count_as_electives": SUB_CORE}  # no acknowledge needed: nothing is lost
    res = client.post("/submajor/electives/choose", data=data)
    assert res.status_code == 303 and stored_rows(app) == sorted(SUB_CORE)
    page = html(client, "/subjects")
    assert "Counted 4 subject(s) as general electives." in page and "no longer count" not in page
    assert "General electives" in page and "4 of 4 chosen" in page


def test_ticking_some_still_needs_the_cost_tick(app, client, log_in):
    log_in()
    client.post("/submajor/electives/choose", data={"csrf_token": token(client), "count_as_electives": SUB_CORE[:2]})
    assert stored_rows(app) == []  # refused: 12 cp would still be lost
    client.post("/submajor/electives/choose", data={"csrf_token": token(client), "count_as_electives": SUB_CORE[:2], "acknowledge": "1"})
    assert stored_rows(app) == sorted(SUB_CORE[:2])
    assert "Counted 2 subject(s) as general electives." in html(client, "/subjects")


def test_a_forged_subject_is_refused_and_nothing_changes(app, client, log_in):
    log_in()
    client.post("/submajor/electives/choose", data={"csrf_token": token(client), "count_as_electives": ["41039"], "acknowledge": "1"})
    assert stored_rows(app) == []
    conn = db.connect(app.config["DATABASE"])
    assert conn.execute("SELECT general_electives FROM users WHERE id = 1").fetchone()[0] == 0
    conn.close()
    again = client.post("/submajor/electives/choose", data={"csrf_token": token(client), "count_as_electives": ["41039"], "acknowledge": "1"}, follow_redirects=True)
    assert "be counted as general electives: 41039." in again.get_data(as_text=True)


def test_the_swap_advice_tool_mentions_the_offer(conn):
    from ai_services.tools.registry import call_tool

    offer = call_tool(conn, 1, "get_swap_advice", {"kind": "electives"})["data"]["electives_offer"]
    assert offer["space_cp"] == 24 and len(offer["eligible"]) == 4
