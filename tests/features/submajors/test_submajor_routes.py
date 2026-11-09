import re

import pytest

from shared import db

TOKEN = re.compile(r'name="csrf_token" value="([^"]+)"')
INFOSEC, INNOVATION, LOTE, HUMANITARIAN = "SMJ10157", "SMJ10156", "SMJ09035", "SMJ10196"
JAPANESE = "CBK90495"


def token(client, path="/subjects"):
    return TOKEN.search(client.get(path).get_data(as_text=True)).group(1)


def choose(client, code, path="/subjects", **extra):
    return client.post(f"/submajor/{code}/choose", data={"csrf_token": token(client, path), **extra})


def html(client, url):
    return client.get(url, follow_redirects=True).get_data(as_text=True)


def stored(app, user_id):
    conn = db.connect(app.config["DATABASE"])
    try:
        row = conn.execute("SELECT submajor_code, submajor_language FROM users WHERE id = ?", (user_id,)).fetchone()
        return row["submajor_code"], row["submajor_language"]
    finally:
        conn.close()


# --- access control ----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("url", ["/submajor", "/submajor/SMJ10157"])
def test_anonymous_visitors_are_sent_to_login(client, url):
    res = client.get(url)
    assert res.status_code == 302 and "/login" in res.headers["Location"]


def test_anonymous_visitors_cannot_choose(app, client):
    res = client.post("/submajor/SMJ10157/choose", data={})
    assert res.status_code == 302 and "/login" in res.headers["Location"]
    assert stored(app, 1) == (INNOVATION, None)


def test_choosing_needs_post_and_a_csrf_token(app, client, register):
    register()
    assert client.get("/submajor/SMJ10157/choose").status_code == 405
    assert client.post("/submajor/SMJ10157/choose", data={}).status_code == 400
    assert client.post("/submajor/SMJ10157/choose", data={"csrf_token": "forged"}).status_code == 400
    assert stored(app, 2) == (None, None)


def test_malformed_and_unknown_codes(client, register):
    register()
    assert client.get("/submajor/bad!code").status_code == 400
    assert client.get("/submajor/SMJ00000").status_code == 404
    assert client.get("/submajor/SMJ09035?language=nope").status_code == 400
    assert client.post("/submajor/bad!code/choose", data={"csrf_token": token(client)}).status_code == 400
    assert client.post("/submajor/SMJ09035/choose", data={"csrf_token": token(client), "language": "bad!"}).status_code == 400


def test_the_form_cannot_name_another_student(app, client, register):
    register()
    choose(client, INFOSEC, user_id="1", submajor_code="SMJ10190")
    assert stored(app, 2) == (INFOSEC, None) and stored(app, 1) == (INNOVATION, None)


def test_the_pages_are_not_cacheable(client, register):
    register()
    assert client.get("/submajor").headers["Cache-Control"] == "no-store"
    assert client.get("/submajor/SMJ10157").headers["Cache-Control"] == "no-store"


# --- browsing ------------------------------------------------------------------------------------------------------------

def test_the_list_shows_every_sub_major_with_a_summary(client, register):
    register()
    page = html(client, "/submajor")
    assert "Choose your sub-major" in page
    for name in ["Applied and Industrial Optimisation", "Humanitarian Engineering", "Information Security",
                 "Innovation and Entrepreneurship", "iOS Industry", "Mathematical Analysis Extension",
                 "Statistical Analysis", "Language Other Than English (LOTE)"]:
        assert name in page
    assert "6 cp core, plus 18 cp of options" in page and "All subjects are core" in page
    assert "Choose one of 6 language programs" in page


def test_a_sub_major_shows_core_and_options_separately(client, register):
    register()
    page = html(client, "/submajor/SMJ10157")
    assert "Core subjects" in page and "all 1 required" in page and "41181" in page
    assert "choose 18 cp from 6 subjects" in page and "Privacy Preserving" in page and "Confirm this sub-major" in page


def test_a_stream_is_shown_as_a_stream_with_its_note(client, register):
    register()
    page = html(client, "/submajor/SMJ10196")
    assert "Stream CBK92069 Transdisciplinary Electives" in page and "eight subjects" in page and "have not been loaded" not in page
    assert "TD: Sustainability in an interconnected world" in page and "TD: Change-making for social impact" in page
    assert "In-country Contemporary Society Study" in page


def test_the_option_groups_of_mathematical_analysis_extension_are_listed_separately(client, register):
    register()
    page = html(client, "/submajor/SMJ10167")
    assert "Options group 1" in page and "choose 6 cp from 2 subjects" in page
    assert "Options group 2" in page and "choose 18 cp from 6 subjects" in page
    assert "two groups of options" in page  # the Handbook's two option groups are explained


def test_the_language_sub_major_lists_programs_and_waits_for_a_choice(client, register):
    register()
    page = html(client, "/submajor/SMJ09035")
    for language in ("Chinese", "French", "German", "Italian", "Japanese", "Spanish"):
        assert language in page
    assert "Pick a language above, then confirm." in page and "Confirm this sub-major" not in page
    assert "You can't combine languages." in page


def test_picking_a_language_shows_only_that_program_and_the_confirm_button(client, register):
    register()
    page = html(client, f"/submajor/SMJ09035?language={JAPANESE}")
    assert "Japanese Language and Culture 1" in page and "8 cp" in page
    assert "Chinese Language and Culture 1" not in page
    assert "Confirm this sub-major" in page and f'name="language" value="{JAPANESE}"' in page


def test_overlaps_with_the_major_are_flagged(client, register):
    register()
    token_ = token(client)
    client.post("/major/MAJ03445/choose", data={"csrf_token": token_})
    page = html(client, "/submajor/SMJ10157")
    assert "also in your major" in page and "A subject counts once, in your major" in page


# --- choosing and swapping -----------------------------------------------------------------------------------------------

def test_confirming_a_sub_major_saves_it_and_goes_to_the_subjects_page(app, client, register):
    register()
    res = choose(client, INFOSEC)
    assert res.status_code == 303 and res.headers["Location"].endswith("/subjects")
    assert stored(app, 2) == (INFOSEC, None)
    assert "Confirmed Information Security as your sub-major." in html(client, "/subjects")


def test_the_subjects_page_shows_the_sub_major_sections_after_choosing(client, register):
    register()
    choose(client, INFOSEC)
    page = html(client, "/subjects")
    assert "Sub-major core" in page and "Sub-major options" in page
    assert "Choose 18 cp from 6 subjects" in page and "0 of 18 cp chosen" in page
    assert "Information Security sub-major" in page and "Swap sub-major" in page
    assert "chosen a sub-major or general electives yet" not in page


def test_the_choose_a_language_flow_confirms_one_program(app, client, register):
    register()
    res = choose(client, LOTE, language=JAPANESE)
    assert res.status_code == 303 and stored(app, 2) == (LOTE, JAPANESE)
    page = html(client, "/subjects")
    assert "Confirmed Language Other Than English (LOTE) (Japanese) as your sub-major." in page
    assert "Sub-major language: Japanese" in page and "Choose 24 cp from 10 subjects" in page


def test_choosing_the_language_sub_major_without_a_language_is_refused(app, client, register):
    register()
    res = choose(client, LOTE)
    assert res.status_code == 303 and stored(app, 2) == (None, None)
    assert "Choose one language program for this sub-major." in html(client, "/submajor/SMJ09035")


def test_swapping_changes_the_sections_and_warns_about_subjects_that_stop_counting(app, client, log_in):
    log_in()  # the demo student has completed all four Innovation and Entrepreneurship subjects
    page = html(client, "/submajor/SMJ10157")
    assert "These subjects you have done would stop counting towards your degree" in page
    assert "48080 Introduction to Innovation (completed)" in page and "Swap to this sub-major" in page
    res = choose(client, INFOSEC, acknowledge="1")
    assert res.status_code == 303 and stored(app, 1) == (INFOSEC, None)
    after = html(client, "/subjects")
    assert "Swapped to Information Security as your sub-major." in after
    assert "4 subject(s) you have done no longer count towards your degree." in after


def test_a_swap_is_not_blocked_for_the_demo_student(app, client, log_in):
    log_in()
    assert "You can't swap" not in html(client, "/submajor/SMJ10157")


def test_the_current_sub_major_is_marked(client, register):
    register()
    choose(client, INFOSEC)
    assert "This is your sub-major." in html(client, "/submajor/SMJ10157")
    assert "Your sub-major" in html(client, "/submajor")


# --- the rest of the site -------------------------------------------------------------------------------------------------

def test_a_new_student_is_prompted_to_choose_a_sub_major(client, register):
    register()
    page = html(client, "/subjects")
    assert "You haven&#39;t chosen a sub-major or general electives yet" in page or "You haven't chosen a sub-major or general electives yet" in page
    assert 'href="/submajor"' in page and "Choose sub-major or electives" in page
    assert "Sub-major core" not in page


def test_the_prompt_is_hidden_while_filtering(client, register):
    register()
    assert 'class="group cat-submajor_prompt"' not in html(client, "/subjects?q=programming")


def test_the_profile_and_record_show_the_sub_major(client, register):
    register()
    choose(client, INFOSEC)
    profile = html(client, "/profile")
    assert "Information Security (SMJ10157)" in profile and "Swap sub-major" in profile
    assert "Information Security sub-major" in html(client, "/students/me")


def test_the_profile_offers_the_chooser_when_there_is_none(client, register):
    register()
    assert "Choose your sub-major" in html(client, "/profile")
    assert "sub-major not chosen yet" in html(client, "/students/me")


def test_the_planner_prompts_for_a_sub_major_and_counts_its_credit_points(client, register):
    register()
    page = html(client, "/planner")
    assert "You haven't chosen a sub-major or general electives, so those 24 credit points aren't in this plan yet." in page
    assert "192 cp still to plan" in page


def test_a_subject_lists_the_sub_majors_that_use_it(client, log_in):
    log_in()
    page = html(client, "/subjects/41181")  # Information Security and Management (also core in a major)
    assert "Sub-majors" in page and "Information Security: core" in page


def test_the_demo_students_completed_sub_major_is_shown(client, log_in):
    log_in()
    page = html(client, "/subjects")
    assert "Innovation and Entrepreneurship sub-major" in page and "All 4 required" in page


def test_the_timetable_works_for_a_language_subject(app, client, register):
    register()
    choose(client, LOTE, language=JAPANESE)
    conn = db.connect(app.config["DATABASE"])
    try:  # the offerings are illustrative, so pick a Japanese subject that is offered in Autumn
        code = conn.execute(
            "SELECT s.code FROM subjects s JOIN submajor_group_subjects gs ON gs.subject_code = s.code"
            " JOIN submajor_groups g ON g.id = gs.group_id WHERE g.language_program = ? AND s.sessions_offered IN ('Autumn', 'Both')"
            " ORDER BY s.code LIMIT 1", (JAPANESE,)).fetchone()[0]
    finally:
        conn.close()
    client.post("/students/me/enrol", data={"subject_code": code, "session_label": "Autumn 2027", "csrf_token": token(client)})
    assert f'<span class="code">{code}</span>' in html(client, "/timetable")
