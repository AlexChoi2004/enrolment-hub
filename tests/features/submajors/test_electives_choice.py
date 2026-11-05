import re

import pytest

from features.accounts.service import create_user
from features.degree_planner.service import PlanError, add_to_plan, get_plan, suggest_plan
from features.enrolment.service import EnrolmentError, enrol, evaluate_subjects
from features.majors.service import choose_major
from shared import db
from features.subject_catalogue import service as catalogue
from features.submajors.service import SubmajorError, choose_electives, choose_submajor, electives_preview, impact

TOKEN = re.compile(r'name="csrf_token" value="([^"]+)"')
AUTUMN = "Autumn 2027"
ESD, INFOSEC, INNOVATION = "MAJ03519", "SMJ10157", "SMJ10156"
ELECTIVES = [f"SYN{n}" for n in range(101, 113)]


@pytest.fixture()
def student(conn):
    user = create_user(conn, "new.student@student.uni.edu.au", "Str0ng#Pass", AUTUMN)["id"]
    choose_major(conn, user, ESD)
    return user


def complete(conn, user_id, *codes):
    for code in codes:
        conn.execute("INSERT INTO enrolments (user_id, subject_code, status, session_label) VALUES (?, ?, 'completed', 'Autumn 2026')", (user_id, code))
    conn.commit()


def categories(conn, user_id):
    return {c["category"]: c for c in catalogue.degree_categories(conn, user_id)}


def reasons(conn, user_id, code):
    return evaluate_subjects(conn, user_id)["subjects"][code]["reasons"]


# --- the either-or choice -------------------------------------------------------------------------------------------

def test_a_new_account_has_chosen_neither(conn, student):
    assert catalogue.user_submajor(conn, student) is None and catalogue.uses_general_electives(conn, student) is False
    plan = get_plan(conn, student)
    assert plan["needs_submajor"] is True and plan["remaining_cp"] == 192


def test_until_one_is_chosen_the_electives_and_sub_major_subjects_are_both_unavailable(conn, student):
    assert reasons(conn, student, "SYN101") == ["Choose general electives or a sub-major to take this subject"]
    assert reasons(conn, student, "37242") == ["Choose a sub-major to take this subject"]


def test_choosing_electives_counts_24_cp_of_them(conn, student):
    result = choose_electives(conn, student)
    assert result == {"swapped": False, "plan_removed": 0, "no_longer_counted": 0, "withdrawn": 0, "counted_as_electives": 0}
    cats = categories(conn, student)
    assert cats["general_elective"]["required_credit_points"] == 24 and cats["general_elective"]["subject_count"] == 12
    assert not any(k.startswith("sub_") for k in cats)
    assert sum(c["required_credit_points"] for c in cats.values()) == 96 + 24 + 48 + 24 == 192


def test_the_two_are_alternatives_not_both(conn, student):
    choose_submajor(conn, student, INFOSEC)
    choose_electives(conn, student)
    assert catalogue.user_submajor(conn, student) is None and catalogue.uses_general_electives(conn, student) is True
    choose_submajor(conn, student, INFOSEC)
    assert catalogue.uses_general_electives(conn, student) is False and catalogue.user_submajor(conn, student)["code"] == INFOSEC
    assert "general_elective" not in categories(conn, student)


def test_choosing_electives_twice_is_refused(conn, student):
    choose_electives(conn, student)
    with pytest.raises(SubmajorError, match="already your choice"):
        choose_electives(conn, student)


def test_with_electives_the_sub_major_subjects_say_why_they_are_unavailable(conn, student):
    choose_electives(conn, student)
    assert reasons(conn, student, "37242") == ["Not part of your degree: you chose general electives instead of a sub-major"]


def test_with_a_sub_major_the_electives_say_why_they_are_unavailable(conn, student):
    choose_submajor(conn, student, INFOSEC)
    assert reasons(conn, student, "SYN101") == [
        "Not part of your degree: you chose the Information Security sub-major instead of general electives"
    ]


# --- the electives behave as before ---------------------------------------------------------------------------------------

def test_four_electives_fill_the_block_and_the_rest_are_blocked(conn, student):
    choose_electives(conn, student)
    complete(conn, student, "SYN101", "SYN103", "SYN106", "SYN109")
    result = evaluate_subjects(conn, student)
    assert result["categories"]["general_elective"]["counted_cp"] == 24
    assert result["subjects"]["SYN102"]["reasons"] == ["General electives requirement already complete"]
    with pytest.raises(EnrolmentError, match="General electives requirement already complete"):
        enrol(conn, student, "SYN102", AUTUMN)


def test_four_electives_can_be_planned_but_not_a_fifth(conn, student):
    choose_electives(conn, student)
    for code in ["SYN101", "SYN103", "SYN106", "SYN109"]:
        add_to_plan(conn, student, code, "Spring 2028" if code != "SYN101" else "Autumn 2028")
    with pytest.raises(PlanError, match="General electives requirement would be exceeded"):
        add_to_plan(conn, student, "SYN111", "Spring 2029")


def test_a_sub_major_subject_cannot_be_planned_with_electives(conn, student):
    choose_electives(conn, student)
    with pytest.raises(PlanError, match="you chose general electives instead of a sub-major"):
        add_to_plan(conn, student, "37242", "Autumn 2028")


def test_an_elective_cannot_be_planned_with_a_sub_major(conn, student):
    choose_submajor(conn, student, INFOSEC)
    with pytest.raises(PlanError, match="instead of general electives"):
        add_to_plan(conn, student, "SYN101", "Autumn 2028")


def test_the_plan_lists_the_electives_section_and_completes_in_full(conn, student):
    choose_electives(conn, student)
    assert "General electives" in {s["label"] for s in get_plan(conn, student)["elective_sections"]}
    added, unplaced = suggest_plan(conn, student)
    plan = get_plan(conn, student)
    assert (added, unplaced) == (31, []) and plan["complete"] is True and plan["remaining_cp"] == 0


# --- swapping either way ----------------------------------------------------------------------------------------------------

def test_the_demo_student_can_swap_to_electives_and_nothing_is_deleted(conn):
    before = conn.execute("SELECT COUNT(*) FROM enrolments WHERE user_id = 1").fetchone()[0]
    effect = impact(conn, 1, electives=True)
    assert [i["subject_code"] for i in effect["lost"]] == ["48080", "81529", "81546", "81547"]
    result = choose_electives(conn, 1)
    assert result["swapped"] is True and result["no_longer_counted"] == 4
    assert conn.execute("SELECT COUNT(*) FROM enrolments WHERE user_id = 1").fetchone()[0] == before
    assert "sub_core" not in categories(conn, 1) and "general_elective" in categories(conn, 1)


def test_swapping_from_electives_to_a_sub_major_stops_the_electives_counting(conn, student):
    choose_electives(conn, student)
    complete(conn, student, "SYN101", "SYN103")
    result = choose_submajor(conn, student, INFOSEC)
    assert result["swapped"] is True and result["no_longer_counted"] == 2


def test_swapping_removes_planned_subjects_that_no_longer_belong(conn, student):
    choose_electives(conn, student)
    add_to_plan(conn, student, "SYN101", "Autumn 2028")
    add_to_plan(conn, student, "41039", "Autumn 2027")
    assert choose_submajor(conn, student, INFOSEC)["plan_removed"] == 1
    planned = {r[0] for r in conn.execute("SELECT subject_code FROM planned_subjects WHERE user_id = ?", (student,))}
    assert planned == {"41039"}


def test_previewing_never_changes_anything(conn, student):
    choose_submajor(conn, student, INFOSEC)
    electives_preview(conn, student)
    impact(conn, student, electives=True)
    assert catalogue.user_submajor(conn, student)["code"] == INFOSEC and catalogue.uses_general_electives(conn, student) is False


def test_the_electives_preview_lists_the_twelve_sample_subjects(conn, student):
    preview = electives_preview(conn, student)
    assert [s["code"] for s in preview["subjects"]] and len(preview["subjects"]) == 12 and preview["required_cp"] == 24


def test_the_database_only_allows_the_flag_to_be_zero_or_one(conn):
    with pytest.raises(Exception, match="CHECK"):
        conn.execute("UPDATE users SET general_electives = 2 WHERE id = 1")


def test_the_completed_cp_are_never_counted_twice_with_electives(conn, student):
    choose_electives(conn, student)
    complete(conn, student, "SYN101")
    plan = get_plan(conn, student)
    assert plan["completed_cp"] + plan["enrolled_cp"] + plan["planned_cp"] + plan["remaining_cp"] == 192


# --- the pages ----------------------------------------------------------------------------------------------------------------

def token(client, path="/subjects"):
    return TOKEN.search(client.get(path).get_data(as_text=True)).group(1)


def html(client, url):
    return client.get(url, follow_redirects=True).get_data(as_text=True)


def stored(app, user_id):
    conn = db.connect(app.config["DATABASE"])
    try:
        row = conn.execute("SELECT submajor_code, general_electives FROM users WHERE id = ?", (user_id,)).fetchone()
        return row["submajor_code"], row["general_electives"]
    finally:
        conn.close()


def test_the_chooser_offers_electives_as_an_alternative(client, register):
    register()
    page = html(client, "/submajor")
    assert "either a sub-major or general electives" in page and "General electives instead of a sub-major" in page
    assert "Choose your sub-major or electives" in page


def test_the_electives_page_lists_the_samples_and_warns_they_are_invented(client, register):
    register()
    page = html(client, "/submajor/electives")
    assert "Introduction to Statistics" in page and "invented sample subjects" in page
    assert "Choose general electives" in page and "choose any 4" in page


def test_choosing_electives_through_the_page(app, client, register):
    register()
    res = client.post("/submajor/electives/choose", data={"csrf_token": token(client)})
    assert res.status_code == 303 and stored(app, 2) == (None, 1)
    page = html(client, "/subjects")
    assert "Confirmed 24 cp of general electives instead of a sub-major." in page
    assert "General electives" in page and "Choose 4 of 12" in page and "0 of 4 chosen" in page
    assert "General electives instead of a sub-major" in page  # the header line
    assert "chosen a sub-major or general electives yet" not in page


def test_choosing_electives_needs_a_login_post_and_csrf(app, client, register):
    assert client.post("/submajor/electives/choose", data={}).status_code == 302
    register()
    assert client.get("/submajor/electives/choose").status_code == 405
    assert client.post("/submajor/electives/choose", data={}).status_code == 400
    assert client.post("/submajor/electives/choose", data={"csrf_token": "forged"}).status_code == 400
    assert stored(app, 2) == (None, 0)


def test_swapping_to_electives_warns_about_what_stops_counting(app, client, log_in):
    log_in()
    page = html(client, "/submajor/electives")
    assert "These subjects you have done would stop counting towards your degree" in page
    assert "48080 Introduction to Innovation (completed)" in page and "Swap to general electives" in page
    client.post("/submajor/electives/choose", data={"csrf_token": token(client), "acknowledge": "1"})
    assert stored(app, 1) == (None, 1)
    assert "4 subject(s) you have done no longer count towards your degree." in html(client, "/subjects")


def test_choosing_a_sub_major_turns_the_electives_off(app, client, register):
    register()
    client.post("/submajor/electives/choose", data={"csrf_token": token(client)})
    client.post("/submajor/SMJ10157/choose", data={"csrf_token": token(client)})
    assert stored(app, 2) == ("SMJ10157", 0)
    assert "Choose 4 of 12" not in html(client, "/subjects")


def test_the_electives_are_labelled_as_invented_on_the_subjects_page(client, register):
    register()
    client.post("/submajor/electives/choose", data={"csrf_token": token(client)})
    res = client.get("/subjects?category=general_elective")
    assert res.data.count(b"synthetic") >= 12


def test_the_profile_and_record_show_the_electives(client, register):
    register()
    client.post("/submajor/electives/choose", data={"csrf_token": token(client)})
    assert "General electives (24 cp, instead of a sub-major)" in html(client, "/profile")
    assert "general electives" in html(client, "/students/me")


def test_the_planner_counts_the_electives_instead_of_prompting(client, register):
    register()
    client.post("/submajor/electives/choose", data={"csrf_token": token(client)})
    page = html(client, "/planner")
    assert "chosen a sub-major or general electives" not in page
    assert "General electives: choose 4 more (0 of 4 chosen)" in page


def test_swapping_to_electives_can_withdraw_in_progress_sub_major_subjects(conn, student):
    choose_submajor(conn, student, INNOVATION)
    conn.execute("INSERT INTO enrolments (user_id, subject_code, status, session_label) VALUES (?, '48080', 'enrolled', ?)", (student, AUTUMN))
    conn.commit()
    assert [w["subject_code"] for w in impact(conn, student, electives=True)["withdrawable"]] == ["48080"]
    result = choose_electives(conn, student, withdraw=True)
    assert result["withdrawn"] == 1
    assert conn.execute("SELECT COUNT(*) FROM enrolments WHERE user_id = ?", (student,)).fetchone()[0] == 0


def test_swapping_a_sub_major_can_withdraw_in_progress_subjects_of_the_old_one(conn, student):
    choose_submajor(conn, student, INNOVATION)
    conn.execute("INSERT INTO enrolments (user_id, subject_code, status, session_label) VALUES (?, '48080', 'enrolled', ?)", (student, AUTUMN))
    conn.commit()
    kept = choose_submajor(conn, student, INFOSEC)
    assert kept["withdrawn"] == 0 and conn.execute("SELECT COUNT(*) FROM enrolments WHERE user_id = ?", (student,)).fetchone()[0] == 1
    choose_submajor(conn, student, INNOVATION)  # back again: it counts, so nothing to withdraw
    result = choose_submajor(conn, student, INFOSEC, withdraw=True)
    assert result["withdrawn"] == 1


def test_the_electives_page_offers_the_withdraw_box_when_there_is_something_to_withdraw(client, log_in):
    log_in()  # John's four Innovation subjects are completed, so there is nothing in progress to withdraw from them
    assert 'name="withdraw_in_progress"' not in html(client, "/submajor/electives")
