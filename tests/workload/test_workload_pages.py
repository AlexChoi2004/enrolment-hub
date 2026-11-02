import re

TOKEN = re.compile(r'name="csrf_token" value="([^"]+)"')


def html(client, url):
    return client.get(url, follow_redirects=True).get_data(as_text=True)


def card(page, code):
    start = page.rindex("<details", 0, page.index(f'<span class="code">{code}</span>'))
    return page[start: page.index("</details>", start)]


# --- the subject card ---------------------------------------------------------------------------------------------------

def test_a_subject_shows_its_assessment_load_as_an_app_estimate(client, log_in):
    log_in()
    page = card(html(client, "/subjects"), "41040")  # Introduction to AI
    assert "Assessment load 3 of 5" in page and "App estimate, not a UTS rating" in page


def test_the_assessment_load_comes_with_its_reasons(client, log_in):
    log_in()
    assert "the exam is 30% of the marks" in card(html(client, "/subjects"), "41040")


def test_a_subject_with_no_breakdown_has_no_assessment_load_badge(client, log_in):
    log_in()
    page = card(html(client, "/subjects"), "41759")  # Capstone
    assert "Assessment load" not in page and "No assessment breakdown has been published yet" in page


def test_the_assessment_table_has_a_due_column_marked_illustrative(client, log_in):
    log_in()
    page = card(html(client, "/subjects"), "41039")
    assert "<th>Due</th>" in page and "Exam period*" in page and re.search(r"Week \d+\*", page)
    assert "*Due weeks are illustrative (invented for this prototype)" in page


# --- the planner -----------------------------------------------------------------------------------------------------------

def test_the_planner_shows_a_workload_verdict_for_a_session(client, log_in):
    log_in()
    page = html(client, "/planner")
    assert "Workload: Heavy" in page and "Crunch week 8:" in page
    assert "average assessment load" in page and "(app estimate)" in page


def test_the_planner_says_deadlines_are_illustrative(client, log_in):
    log_in()
    assert "Deadlines by week (illustrative)" in html(client, "/planner")


def test_a_session_with_nothing_in_it_has_no_verdict(client, log_in):
    log_in()
    page = html(client, "/planner")
    assert page.count('class="workload ') == 1  # only Autumn 2027, where John is enrolled


def test_a_suggested_move_comes_with_a_working_button(app, client, register):
    from shared import db
    from degree_planner.service import add_to_plan, get_plan

    register()
    token = TOKEN.search(client.get("/planner").get_data(as_text=True)).group(1)
    client.post("/major/MAJ03519/choose", data={"csrf_token": token})
    client.post("/submajor/SMJ10156/choose", data={"csrf_token": token})
    client.post("/planner/suggest", data={"csrf_token": token})
    conn = db.connect(app.config["DATABASE"])
    try:
        plan = get_plan(conn, 2)
    finally:
        conn.close()
    page = html(client, "/planner")
    assert "Workload:" in page
    assert page.count("Suggestion: move") == sum(len(s["suggestions"]) for s in plan["sessions"])


# --- the timetable ---------------------------------------------------------------------------------------------------------

def test_the_timetable_shows_the_same_verdict_for_the_session(client, log_in):
    log_in()
    page = html(client, "/timetable")
    assert "Workload: Heavy" in page and "Crunch week 11:" in page and "(illustrative)" in page


def test_an_empty_timetable_session_has_no_workload_box(client, log_in):
    log_in()
    assert "Workload:" not in html(client, "/timetable?session=Spring 2027")


# --- it is a detail of the opened card only: never a headline, a filter or a ranking -------------------------------------

def test_the_assessment_load_is_not_on_the_collapsed_card_line(client, log_in):
    log_in()
    page = html(client, "/subjects")
    summaries = re.findall(r"<summary>.*?</summary>", page, re.S)
    assert summaries and not any("Assessment load" in s or "Difficulty" in s for s in summaries)


def test_the_filters_cannot_sort_or_filter_by_assessment_load(client, log_in):
    log_in()
    page = html(client, "/subjects")
    start = page.index('<form class="filters"')
    form = page[start: page.index("</form>", start)]
    assert "load" not in form.lower() and "difficulty" not in form.lower()
    assert client.get("/subjects?load=5").status_code == 200  # an unknown parameter is simply ignored


def test_the_word_difficulty_is_not_shown_to_students_anywhere(client, log_in):
    log_in()
    for url in ("/subjects", "/planner", "/timetable", "/subjects/31251"):
        assert "difficulty" not in html(client, url).lower()
