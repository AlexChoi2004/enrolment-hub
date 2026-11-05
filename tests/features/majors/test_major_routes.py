import re

import pytest

from shared import db

TOKEN = re.compile(r'name="csrf_token" value="([^"]+)"')
QUANTUM, AI, ESD, BISM = "MAJ02901", "MAJ10053", "MAJ03519", "MAJ02080"


def token(client, path="/subjects"):
    return TOKEN.search(client.get(path).get_data(as_text=True)).group(1)


def choose(client, code, path="/subjects", **extra):
    return client.post(f"/major/{code}/choose", data={"csrf_token": token(client, path), **extra})


def html(client, url):
    return client.get(url, follow_redirects=True).get_data(as_text=True)


def stored_major(app, user_id):
    conn = db.connect(app.config["DATABASE"])
    try:
        return conn.execute("SELECT major_code FROM users WHERE id = ?", (user_id,)).fetchone()["major_code"]
    finally:
        conn.close()


def card(page, code):
    start = page.index(f'<span class="code">{code}</span>')
    start = page.rindex("<details", 0, start)
    return page[start: page.index("</details>", start)]


# --- access control ----------------------------------------------------------------------------------

@pytest.mark.parametrize("url", ["/major", "/major/MAJ02901"])
def test_anonymous_visitors_are_sent_to_login(client, url):
    res = client.get(url)
    assert res.status_code == 302 and "/login" in res.headers["Location"]


def test_anonymous_visitors_cannot_choose_a_major(app, client):
    res = client.post("/major/MAJ02901/choose", data={})
    assert res.status_code == 302 and "/login" in res.headers["Location"]
    assert stored_major(app, 1) == ESD


def test_choosing_needs_post_and_a_csrf_token(app, client, register):
    register()
    assert client.get("/major/MAJ02901/choose").status_code == 405
    assert client.post("/major/MAJ02901/choose", data={}).status_code == 400
    assert client.post("/major/MAJ02901/choose", data={"csrf_token": "forged"}).status_code == 400
    assert stored_major(app, 2) is None


def test_malformed_and_unknown_major_codes(client, register):
    register()
    assert client.get("/major/bad!code").status_code == 400
    assert client.get("/major/MAJ00000").status_code == 404
    assert client.post("/major/bad!code/choose", data={"csrf_token": token(client)}).status_code == 400


def test_the_form_cannot_name_another_student(app, client, register):
    register()
    choose(client, QUANTUM, user_id="1", major_code=BISM)
    assert stored_major(app, 2) == QUANTUM  # the signed-in student
    assert stored_major(app, 1) == ESD  # the demo student is untouched


def test_the_pages_are_not_cacheable(client, register):
    register()
    assert client.get("/major").headers["Cache-Control"] == "no-store"
    assert client.get("/major/MAJ02901").headers["Cache-Control"] == "no-store"


# --- the chooser pages: summaries first, subjects only for the one you open --------------------------------------

def test_the_list_shows_every_major_with_a_summary_but_no_subjects(client, register):
    register()
    page = html(client, "/major")
    assert "Choose your major" in page
    for name in ["Enterprise Software Development", "Artificial Intelligence and Data Analytics", "Business Information Systems Management",
                 "Cybersecurity and Privacy", "Interaction Design", "Mathematical Analysis", "Networking and Cybersecurity", "Quantum Computing"]:
        assert name in page
    assert "3 core subjects, plus choose 5 of 9 options" in page
    assert "All 8 subjects are core" in page
    assert "Machine Learning" not in page and "Linear Algebra" not in page  # no subject lists on this page


def test_opening_a_major_lists_its_core_and_options(client, register):
    register()
    page = html(client, "/major/MAJ10053")
    assert "Core subjects" in page and "all 3 required" in page
    assert "Introduction to Data Analytics" in page and "Capstone" in page
    assert "Options" in page and "choose 5 of 9" in page and "Machine Learning" in page
    assert "Linear Algebra" not in page  # a different major's subject


def test_a_major_without_options_says_so(client, register):
    register()
    page = html(client, "/major/MAJ02080")
    assert "no options: every subject is core" in page and "all 8 required" in page


def test_a_new_student_sees_a_confirm_button(client, register):
    register()
    page = html(client, "/major/MAJ02901")
    assert "Confirm this major" in page and 'action="/major/MAJ02901/choose"' in page
    assert "Swap to this major" not in page


# --- confirming ----------------------------------------------------------------------------------------------------

def test_confirming_a_major_saves_it_and_goes_to_the_subjects_page(app, client, register):
    register()
    res = choose(client, QUANTUM)
    assert res.status_code == 303 and res.headers["Location"].endswith("/subjects")
    assert stored_major(app, 2) == QUANTUM
    assert "Confirmed Quantum Computing as your major." in html(client, "/subjects")


def test_after_confirming_the_subjects_page_shows_that_majors_sections(client, register):
    register()
    choose(client, QUANTUM)
    page = html(client, "/subjects")
    assert "Quantum Computing major" in page and "Swap major" in page
    assert "Major core" in page and "Methods in Quantum Computing" in page
    assert "All 5 required" in page and "Choose 3 of 9" in page and "0 of 3 chosen" in page
    assert "Advanced Software Development" not in page  # an Enterprise Software Development subject
    assert "Choose major" not in page


def test_after_confirming_the_profile_and_record_show_the_major(client, register):
    register()
    choose(client, QUANTUM)
    assert "Quantum Computing (MAJ02901)" in html(client, "/profile") and "Swap major" in html(client, "/profile")
    assert "Quantum Computing major" in html(client, "/students/me")


def test_the_current_major_is_marked_and_other_majors_offer_a_swap(client, register):
    register()
    choose(client, QUANTUM)
    assert "This is your major." in html(client, "/major/MAJ02901")
    other = html(client, "/major/MAJ10053")
    assert "Swap to this major" in other and "Confirm this major" not in other
    assert "Swapping keeps what you have done" in other
    assert "Swap major" in html(client, "/major") and "Your major" in html(client, "/major")


def test_swapping_changes_the_subjects_page(app, client, register):
    register()
    choose(client, QUANTUM)
    res = choose(client, AI)
    assert res.status_code == 303 and stored_major(app, 2) == AI
    page = html(client, "/subjects")
    assert "Swapped to Artificial Intelligence and Data Analytics as your major." in page
    assert "Machine Learning" in page and "Methods in Quantum Computing" not in page


def test_choosing_the_same_major_again_explains(client, register):
    register()
    choose(client, QUANTUM)
    choose(client, QUANTUM)
    assert "is already your major" in html(client, "/major/MAJ02901")


def test_swapping_removes_planned_subjects_and_says_so(client, register):
    register()
    choose(client, ESD)
    client.post("/planner/add", data={"subject_code": "31260", "session_label": "Spring 2028", "csrf_token": token(client, "/planner")})
    choose(client, QUANTUM, path="/planner")
    assert "Removed 1 planned subject(s) that are not in this major." in html(client, "/subjects")
    assert "31260" not in html(client, "/planner")


# --- the demo student ---------------------------------------------------------------------------------------------------

def test_the_demo_student_keeps_enterprise_software_development(client, log_in):
    log_in()
    page = html(client, "/subjects")
    assert "Enterprise Software Development major" in page
    assert "All 5 required" in page and "Choose 3 of 9" in page


def test_the_demo_student_can_swap_and_is_told_what_stops_counting(app, client, log_in):
    log_in()
    page = html(client, "/major/MAJ10053")
    assert "These subjects you have done would stop counting towards your degree" in page
    assert "41025 Introduction to Software Development (completed)" in page
    assert "Swap to this major" in page and "You can't swap" not in page
    choose(client, AI, acknowledge="1")
    assert stored_major(app, 1) == AI
    after = html(client, "/subjects")
    assert "Swapped to Artificial Intelligence and Data Analytics as your major." in after
    assert "subject(s) you have done no longer count towards your degree." in after


def test_the_demo_students_own_major_page_says_so(client, log_in):
    log_in()
    assert "This is your major." in html(client, "/major/MAJ03519")


# --- a student with no major yet -------------------------------------------------------------------------------------------

def test_with_no_major_the_subjects_page_offers_choose_major_where_the_major_would_be(client, register):
    register()
    page = html(client, "/subjects")
    assert "You haven't chosen a major yet" in page and 'href="/major"' in page and "Choose major" in page
    honours = page.index('<h2 class="group-title">Honours core')
    major_prompt = page.index('class="group cat-major_prompt"')
    sub_prompt = page.index('class="group cat-submajor_prompt"')
    assert honours < major_prompt < sub_prompt  # the sub-major prompt comes after the major's
    assert "Major core" not in page and "Major electives" not in page


def test_with_no_major_no_major_subjects_are_listed(client, register):
    register()
    page = html(client, "/subjects")
    assert "Programming 1" in page and "Technology Research Preparation" in page  # core and honours core
    for hidden in ["Advanced Software Development", "Machine Learning", "Linear Algebra", "Capstone"]:
        assert hidden not in page


def test_with_no_major_the_category_filter_only_offers_shared_sections(client, register):
    register()
    page = html(client, "/subjects")
    assert 'value="core"' in page and 'value="honours_core"' in page and 'value="major_core"' not in page
    assert client.get("/subjects?category=major_core").status_code == 400


def test_the_prompt_is_hidden_while_filtering(client, register):
    register()
    assert "You haven't chosen a major yet" in html(client, "/subjects")  # the header line always says so
    assert "major-prompt" not in html(client, "/subjects?q=programming")


def test_a_subject_from_another_major_still_opens_with_the_reason(client, register):
    register()
    page = html(client, "/subjects/41025")
    assert "Not in your degree" in page and "Choose a major to take this subject" in page
    assert "Enterprise Software Development: core" in page


def test_with_no_major_enrolling_in_a_major_subject_is_refused(app, client, register):
    register()
    client.post("/students/me/enrol", data={"subject_code": "41025", "session_label": "Autumn 2027", "csrf_token": token(client)})
    assert "Choose a major to take this subject" in html(client, "/subjects")


def test_with_no_major_the_profile_and_planner_offer_the_chooser(client, register):
    register()
    profile = html(client, "/profile")
    assert "Not chosen yet" in profile and "Choose your major" in profile
    planner = html(client, "/planner")
    assert "You haven't chosen a major" in planner and "48 credit points" in planner
    assert "major not chosen yet" in html(client, "/students/me")


def test_a_major_subject_shows_which_majors_use_it(client, register):
    register()
    choose(client, QUANTUM)
    page = card(html(client, "/subjects"), "31250")
    assert "Artificial Intelligence and Data Analytics: core" in page and "Quantum Computing: option" in page


def test_the_planner_after_choosing_shows_the_majors_electives(client, register):
    register()
    choose(client, AI)
    page = html(client, "/planner")
    assert "Major electives: choose 5 more (0 of 5 chosen)" in page and "You haven't chosen a major" not in page


def test_the_timetable_works_for_a_new_majors_subjects(client, register):
    register()
    choose(client, AI)
    client.post("/students/me/enrol", data={"subject_code": "31250", "session_label": "Autumn 2027", "csrf_token": token(client)})
    page = html(client, "/timetable")
    assert '<span class="code">31250</span>' in page and "Introduction to Data Analytics" in page


def test_added_subjects_show_prerequisites_like_the_original_ones(client, register):
    register()
    choose(client, "MAJ02900")
    page = card(html(client, "/subjects"), "41180")  # Data Analytics in Cybersecurity <- Cybersecurity
    assert "has prerequisites" in page and "prerequisites not verified" not in page
    assert "48730 Cybersecurity" in page and "&#10007; not completed" in page


def test_a_subject_with_no_rule_says_no_prerequisites(client, register):
    register()
    choose(client, AI)
    page = card(html(client, "/subjects"), "31250")  # Introduction to Data Analytics: nothing listed
    assert "no prerequisites" in page and "No prerequisites listed in the supplied data." in page


def test_alternatives_are_shown_as_one_of(client, register):
    register()
    choose(client, "MAJ02092")
    page = card(html(client, "/subjects"), "31264")  # Computer Graphics <- 31080 OR 31263
    assert "One of:" in page and "31080 Interactive Media" in page and "31263 Introduction to Computer Game Development" in page


def test_a_credit_condition_is_shown_separately_with_progress(client, register):
    register()
    choose(client, "MAJ03445")
    page = card(html(client, "/subjects"), "32009")
    assert "31277 Routing and Switching Essentials" in page
    assert "At least 30 credit points completed in Networking and Cybersecurity" in page and "0 completed so far" in page


def test_a_corequisite_says_it_can_be_taken_together(client, register):
    register()
    choose(client, "MAJ01156")
    assert "can also be taken at the same time" in card(html(client, "/subjects"), "37161")


def test_an_unenforceable_lead_is_shown_as_not_enforced(client, register):
    register()
    choose(client, AI)
    page = card(html(client, "/subjects"), "31243")
    assert "Note:" in page and "41004" in page and "not enforced" in page
    assert 'st-available">Can enrol' in page  # it is not blocked by the lead it cannot enforce


def test_the_handbook_wording_is_shown_when_the_app_cannot_enforce_all_of_it(client, log_in):
    log_in()
    page = card(html(client, "/subjects"), "41040")
    assert "41039 Programming 1" in page  # the enforced prerequisite
    assert "UTS Handbook requisite: (48023 OR 41039)" in page and "Only the subjects in this app are enforced" in page


def test_a_subject_only_lists_what_it_unlocks_inside_your_degree(client, register):
    register()
    page = card(html(client, "/subjects"), "33130")  # Mathematics 1 leads to Linear Algebra in another major
    assert "Linear Algebra" not in page
    choose(client, "MAJ01156")
    assert "Linear Algebra" in card(html(client, "/subjects"), "33130")


def test_the_swap_page_offers_to_withdraw_from_in_progress_subjects(client, log_in):
    log_in()
    page = html(client, "/major/MAJ10053")
    assert 'name="withdraw_in_progress"' in page and "41026 Advanced Software Development (enrolled)" in page
    assert "Also withdraw me from the 1 in-progress subject(s)" in page


def enrolment_status(app, code, user_id=1):
    conn = db.connect(app.config["DATABASE"])
    try:
        row = conn.execute("SELECT status FROM enrolments WHERE user_id = ? AND subject_code = ?", (user_id, code)).fetchone()
        return row["status"] if row else None
    finally:
        conn.close()


def test_swapping_with_the_box_ticked_withdraws_them(app, client, log_in):
    log_in()
    choose(client, AI, withdraw_in_progress="1", acknowledge="1")
    assert enrolment_status(app, "41026") is None  # Advanced Software Development is withdrawn
    assert enrolment_status(app, "41025") == "completed"  # history stays
    assert "Withdrew you from 1 in-progress subject(s) that are not in this major." in html(client, "/subjects")


def test_swapping_without_the_box_leaves_them_enrolled(app, client, log_in):
    log_in()
    choose(client, AI)
    assert enrolment_status(app, "41026") == "enrolled"
    assert "Withdrew you from" not in html(client, "/subjects")
