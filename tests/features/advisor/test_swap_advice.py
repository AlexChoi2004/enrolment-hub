import re

import pytest

from features.accounts.service import create_user
from features.advisor.service import KINDS, TIERS, assess, session_after
from features.degree_planner.service import add_to_plan
from features.enrolment.service import current_session_of, enrol
from features.enrolment.results import record_result
from features.majors.service import choose_major
from shared import db
from features.submajors.service import choose_submajor

AUTUMN = "Autumn 2027"
TOKEN = re.compile(r'name="csrf_token" value="([^"]+)"')


@pytest.fixture()
def student(conn):
    user = create_user(conn, "new.student@student.uni.edu.au", "Str0ng#Pass", AUTUMN)["id"]
    choose_major(conn, user, "MAJ03519")
    choose_submajor(conn, user, "SMJ10156")
    return user


def passed(conn, user, *codes, session="Autumn 2026"):
    for code in codes:
        record_result(conn, user, code, session, "passed")


# --- the sessions ----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("start,steps,end", [("Autumn 2027", 0, "Autumn 2027"), ("Autumn 2027", 3, "Spring 2028"), ("Spring 2027", 2, "Spring 2028")])
def test_session_after_counts_forward(start, steps, end):
    assert session_after(start, steps) == end


# --- the demo student (two years in) ------------------------------------------------------------------------------------------

def test_the_facts_for_the_demo_student_swapping_to_another_major(conn):
    a = assess(conn, 1, "major", "MAJ10053")  # Artificial Intelligence and Data Analytics
    assert a["progress"] == {"counted_cp": 120, "degree_cp": 192, "percent": 62, "major_cp": 30, "major_percent": 62}
    assert (a["lost_cp"], a["carried_cp"], a["carry_percent"]) == (24, 96, 80)
    assert (a["extra_cp"], a["extra_subjects"], a["extra_sessions"]) == (24, 4, 1)
    assert (a["graduate_before"], a["graduate_after"]) == ("Spring 2028", "Autumn 2029")
    assert a["tier"] == "costs_time" and a["label"] == "Possible, but it costs time" and a["needs_ack"] is True


def test_losing_a_lot_is_think_carefully(conn):
    a = assess(conn, 1, "major", "MAJ03445")  # Networking and Cybersecurity
    assert a["tier"] == "think" and a["extra_sessions"] == 2 and a["lost_cp"] == 30
    assert any("extra subjects and 2 extra session" in r for r in a["reasons"])


def test_the_lost_subjects_are_listed_with_their_credit_points_and_status(conn):
    lost = assess(conn, 1, "major", "MAJ10053")["lost"]
    assert {"code": "41025", "credit_points": 6, "status": "completed"} in lost
    assert {"code": "41026", "credit_points": 6, "status": "enrolled"} in lost
    assert sum(item["credit_points"] for item in lost) == 24


def test_swapping_to_the_same_major_loses_nothing(conn):
    a = assess(conn, 1, "major", "MAJ03519")
    assert a["tier"] == "good" and a["lost_cp"] == 0 and a["extra_sessions"] == 0 and a["needs_ack"] is False
    assert a["graduate_before"] == a["graduate_after"] and a["ack_text"] == ""


def test_the_sub_major_and_electives_are_assessed_too(conn):
    sub = assess(conn, 1, "submajor", "SMJ10157")
    assert sub["target"] == "Information Security" and sub["lost_cp"] == 24 and sub["tier"] == "costs_time"
    electives = assess(conn, 1, "electives")
    assert electives["target"] == "General electives" and electives["lost_cp"] == 24


def test_a_language_target_is_named_with_its_language(conn):
    assert assess(conn, 1, "submajor", "SMJ09035", "CBK90495")["target"] == "Language Other Than English (LOTE) (Japanese)"


def test_an_unknown_target_is_none_and_a_bad_kind_is_refused(conn):
    assert assess(conn, 1, "major", "MAJ00000") is None and assess(conn, 1, "submajor", "SMJ00000") is None
    with pytest.raises(ValueError):
        assess(conn, 1, "nonsense")
    assert set(KINDS) == {"major", "submajor", "electives"}


def test_the_advice_always_carries_the_tuition_note_and_the_rules(conn):
    a = assess(conn, 1, "major", "MAJ10053")
    assert "extra tuition (HECS or otherwise)" in a["tuition_note"] and "no dollar amount" in a["tuition_note"]
    assert len(a["rules"]) == 3 and "Good to switch" in a["rules"][0]
    assert "extra tuition" in a["ack_text"] and "4 extra subject(s)" in a["ack_text"] and "1 session(s)" in a["ack_text"]


def test_assessing_never_changes_anything(conn):
    before = (
        [tuple(r) for r in conn.execute("SELECT * FROM users WHERE id = 1")],
        [tuple(r) for r in conn.execute("SELECT * FROM enrolments WHERE user_id = 1 ORDER BY subject_code")],
    )
    for kind, code in [("major", "MAJ10053"), ("submajor", "SMJ10157"), ("electives", None)]:
        assess(conn, 1, kind, code)
    after = (
        [tuple(r) for r in conn.execute("SELECT * FROM users WHERE id = 1")],
        [tuple(r) for r in conn.execute("SELECT * FROM enrolments WHERE user_id = 1 ORDER BY subject_code")],
    )
    assert before == after


def test_the_tiers_are_the_three_named_verdicts():
    assert set(TIERS) == {"good", "costs_time", "think"}


# --- other students ---------------------------------------------------------------------------------------------------------------

def test_a_student_with_nothing_done_loses_nothing_by_choosing_a_first_major(conn):
    fresh = create_user(conn, "fresh.student@student.uni.edu.au", "Str0ng#Pass", AUTUMN)["id"]
    a = assess(conn, fresh, "major", "MAJ10053")
    assert a["tier"] == "good" and a["lost_cp"] == 0 and a["carry_percent"] == 100 and a["progress"]["percent"] == 0


def test_a_student_with_nothing_done_loses_nothing_by_swapping_either_way(conn, student):
    assert assess(conn, student, "major", "MAJ10053")["tier"] == "good"
    assert assess(conn, student, "electives")["tier"] == "good"


def test_a_high_overlap_swap_with_one_subject_lost_is_good_to_switch(conn, student):
    passed(conn, student, "41039", "33130", "31265", "37181", "31268", "41092")  # core subjects count in every major
    choose_major(conn, student, "MAJ10053")
    passed(conn, student, "31250")  # Introduction to Data Analytics: a core subject of this major
    a = assess(conn, student, "major", "MAJ03519")  # Enterprise Software Development: only that one subject is lost
    assert a["lost_cp"] == 6 and a["tier"] == "good" and a["needs_ack"] is False
    assert a["carry_percent"] >= 85


def test_a_late_swap_with_almost_no_overlap_is_think_carefully(conn, student):
    choose_major(conn, student, "MAJ03445")  # Networking and Cybersecurity
    passed(conn, student, "31277", "31275", "48730", "43037", "42891", "41759", "32011", "41900")  # most of the 48 cp major
    a = assess(conn, student, "major", "MAJ01156")  # Mathematical Analysis: nothing in common
    assert a["progress"]["major_percent"] >= 75 and a["carry_percent"] < 25
    assert a["tier"] == "think" and any("through your current major and only" in r for r in a["reasons"])


def test_the_projected_graduation_follows_the_students_own_session(conn, student):
    from features.simulator.service import complete_semester

    complete_semester(conn, student, {})  # on to Spring 2027
    a = assess(conn, student, "major", "MAJ10053")
    # 192 cp is 8 sessions of 24 including the current one, so 7 more after Spring 2027 (the room left in the current session counts)
    assert current_session_of(conn, student) == "Spring 2027" and a["graduate_before"] == session_after("Spring 2027", 7) == "Autumn 2031"


def test_the_advice_reflects_a_failed_subject_that_no_longer_counts(conn, student):
    choose_major(conn, student, "MAJ10053")
    enrol(conn, student, "31250", AUTUMN)
    record_result(conn, student, "31250", AUTUMN, "failed")
    assert assess(conn, student, "major", "MAJ03519")["lost_cp"] == 0  # a fail never counted


# --- the pages ---------------------------------------------------------------------------------------------------------------------------

def page(client, url):
    return client.get(url, follow_redirects=True).get_data(as_text=True)


def token(client, path="/subjects"):
    return TOKEN.search(client.get(path).get_data(as_text=True)).group(1)


def test_the_major_swap_page_shows_the_advice_for_the_demo_student(client, log_in):
    log_in()
    p = page(client, "/major/MAJ10053")
    assert "Swap advice: Possible, but it costs time" in p
    assert "62%</strong> through your degree (120 of 192 credit points)" in p and "62%</strong> through your major" in p
    assert "Projected graduation: <strong>Spring 2028</strong> now, <strong>Autumn 2029</strong> after this swap" in p
    assert "extra tuition (HECS or otherwise)" in p and "How this verdict is worked out" in p
    assert "not decided by an AI" in p and "You make the final decision" in p


def test_the_swap_page_has_the_confirmation_tick_when_it_is_not_a_good_swap(client, log_in):
    log_in()
    p = page(client, "/major/MAJ03445")
    assert 'name="acknowledge"' in p and "required" in p and "I understand this adds about 5 extra subject(s)" in p


def test_there_is_no_advice_and_no_tick_for_your_current_major(client, log_in):
    log_in()
    p = page(client, "/major/MAJ03519")
    assert "Swap advice" not in p and 'name="acknowledge"' not in p


def test_choosing_a_first_major_shows_no_swap_advice_and_needs_no_tick(client, register):
    register()  # nothing chosen yet, so there is nothing to swap from
    p = page(client, "/major/MAJ10053")
    assert "Swap advice" not in p and 'name="acknowledge"' not in p and "Confirm this major" in p


def test_choosing_a_first_sub_major_or_electives_shows_no_swap_advice(client, register):
    register()
    for url in ("/submajor/SMJ10157", "/submajor/electives"):
        p = page(client, url)
        assert "Swap advice" not in p and 'name="acknowledge"' not in p


def test_a_student_with_a_major_but_nothing_done_gets_a_short_note_not_zeros(client, register):
    register()
    client.post("/major/MAJ03519/choose", data={"csrf_token": token(client)})
    p = page(client, "/major/MAJ10053")
    assert "Swap advice: Good to switch" in p and "have not done anything that counts towards your degree yet" in p
    assert "through your degree" not in p and 'name="acknowledge"' not in p


def test_the_assessment_says_whether_it_is_a_first_choice(conn, student):
    fresh = create_user(conn, "first.student@student.uni.edu.au", "Str0ng#Pass", AUTUMN)["id"]
    assert assess(conn, fresh, "major", "MAJ10053")["first_choice"] is True
    assert assess(conn, fresh, "submajor", "SMJ10157")["first_choice"] is True and assess(conn, fresh, "electives")["first_choice"] is True
    assert assess(conn, student, "major", "MAJ10053")["first_choice"] is False
    assert assess(conn, 1, "electives")["first_choice"] is False


def test_the_server_still_needs_no_tick_for_a_first_choice(app, client, register):
    from shared import db as dbm

    register()
    client.post("/major/MAJ10053/choose", data={"csrf_token": token(client)})
    conn = dbm.connect(app.config["DATABASE"])
    assert conn.execute("SELECT major_code FROM users WHERE id = 2").fetchone()[0] == "MAJ10053"
    conn.close()


def test_the_server_refuses_a_swap_without_the_tick(app, client, log_in):
    log_in()
    res = client.post("/major/MAJ10053/choose", data={"csrf_token": token(client)})
    assert res.status_code == 303 and "/major/MAJ10053" in res.headers["Location"]
    assert "Please tick the box to confirm you understand what this swap costs." in page(client, "/major/MAJ10053")
    conn = db.connect(app.config["DATABASE"])
    assert conn.execute("SELECT major_code FROM users WHERE id = 1").fetchone()[0] == "MAJ03519"  # unchanged
    conn.close()


def test_a_wrong_value_for_the_tick_is_not_accepted(app, client, log_in):
    log_in()
    client.post("/major/MAJ10053/choose", data={"csrf_token": token(client), "acknowledge": "yes"})
    conn = db.connect(app.config["DATABASE"])
    assert conn.execute("SELECT major_code FROM users WHERE id = 1").fetchone()[0] == "MAJ03519"
    conn.close()


def test_the_swap_goes_ahead_with_the_tick(app, client, log_in):
    log_in()
    client.post("/major/MAJ10053/choose", data={"csrf_token": token(client), "acknowledge": "1"})
    conn = db.connect(app.config["DATABASE"])
    assert conn.execute("SELECT major_code FROM users WHERE id = 1").fetchone()[0] == "MAJ10053"
    conn.close()


def test_the_sub_major_swap_needs_the_tick_too(app, client, log_in):
    log_in()
    assert "Swap advice" in page(client, "/submajor/SMJ10157") and 'name="acknowledge"' in page(client, "/submajor/SMJ10157")
    client.post("/submajor/SMJ10157/choose", data={"csrf_token": token(client)})
    conn = db.connect(app.config["DATABASE"])
    assert conn.execute("SELECT submajor_code FROM users WHERE id = 1").fetchone()[0] == "SMJ10156"
    client.post("/submajor/SMJ10157/choose", data={"csrf_token": token(client), "acknowledge": "1"})
    assert conn.execute("SELECT submajor_code FROM users WHERE id = 1").fetchone()[0] == "SMJ10157"
    conn.close()


def test_the_electives_swap_needs_the_tick_too(app, client, log_in):
    log_in()
    assert "Swap advice" in page(client, "/submajor/electives") and 'name="acknowledge"' in page(client, "/submajor/electives")
    client.post("/submajor/electives/choose", data={"csrf_token": token(client)})
    conn = db.connect(app.config["DATABASE"])
    assert conn.execute("SELECT general_electives FROM users WHERE id = 1").fetchone()[0] == 0
    client.post("/submajor/electives/choose", data={"csrf_token": token(client), "acknowledge": "1"})
    assert conn.execute("SELECT general_electives FROM users WHERE id = 1").fetchone()[0] == 1
    conn.close()


def test_a_language_pick_is_assessed_with_the_chosen_language(client, log_in):
    log_in()
    assert "Swap advice" not in page(client, "/submajor/SMJ09035")  # nothing to assess until a language is chosen
    assert "Swap advice" in page(client, "/submajor/SMJ09035?language=CBK90495")


def test_the_pages_do_not_charge_a_dollar_amount(client, log_in):
    log_in()
    assert "$" not in page(client, "/major/MAJ10053").split("Swap advice")[1].split("</section>")[0]
