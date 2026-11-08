import re

import pytest

from features.advisor.ranking import SORTS, fit_key, row_of, session_index, sort_rows
from features.advisor.service import assess
from features.enrolment.presets import PRESETS
from features.majors.fit import rank_majors
from features.subject_catalogue.service import list_majors
from shared import db

KEYS = list(PRESETS)
TOKEN = re.compile(r'name="csrf_token" value="([^"]+)"')


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


def row(name, tier="good", lost=0, extra=0, graduate="Autumn 2028"):
    return {"name": name, "tier": tier, "lost_cp": lost, "extra_sessions": extra, "graduate": graduate}


# --- ordering ------------------------------------------------------------------------------------------------------------------------------------

def test_sessions_are_in_calendar_order():
    labels = ["Spring 2029", "Autumn 2029", "Autumn 2028", "Spring 2028", "Autumn 2030"]
    assert sorted(labels, key=session_index) == ["Autumn 2028", "Spring 2028", "Autumn 2029", "Spring 2029", "Autumn 2030"]


def test_best_fit_orders_by_verdict_then_credit_points_lost_then_extra_sessions_then_name():
    rows = [row("D", "think", 40, 2), row("B", "good", 6, 0), row("C", "costs_time", 24, 1), row("A", "good", 6, 0), row("E", "good", 0, 0), row("F", "costs_time", 24, 0)]
    assert [r["name"] for r in sort_rows(rows, "fit")] == ["E", "A", "B", "F", "C", "D"]


def test_a_worse_verdict_never_beats_a_better_one_whatever_the_numbers():
    assert fit_key(row("x", "think", 0, 0)) > fit_key(row("y", "good", 99, 9)) and fit_key(row("x", "costs_time", 0, 0)) > fit_key(row("y", "good", 99, 9))


def test_the_other_orders():
    rows = [row("B", lost=12, graduate="Spring 2029"), row("A", lost=6, graduate="Autumn 2030"), row("C", lost=6, graduate="Autumn 2029")]
    assert [r["name"] for r in sort_rows(rows, "lost")] == ["A", "C", "B"]
    assert [r["name"] for r in sort_rows(rows, "graduation")] == ["C", "B", "A"]
    assert [r["name"] for r in sort_rows(rows, "name")] == ["A", "B", "C"]


def test_the_available_orders():
    assert list(SORTS) == ["fit", "lost", "graduation", "name"]


# --- the data: the advisor's own numbers ----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("key", KEYS)
def test_every_major_is_listed_once_and_the_students_own_is_kept_apart(students, key):
    conn = students[key]
    result = rank_majors(conn, 1)
    codes = [r["code"] for r in result["rows"]] + ([result["current"]["code"]] if result["current"] else [])
    assert sorted(codes) == sorted(m["code"] for m in list_majors(conn)) and len(codes) == len(set(codes)) == 8
    assert (result["current"] is None) == result["first_choice"] and not any(r["is_current"] for r in result["rows"])


@pytest.mark.parametrize("key", KEYS)
def test_each_row_is_exactly_the_swap_advice_for_that_major(students, key):
    conn = students[key]
    for r in rank_majors(conn, 1)["rows"]:
        advice = assess(conn, 1, "major", r["code"])
        assert (r["tier"], r["label"], r["why"], r["lost_cp"], r["carried_cp"], r["extra_sessions"], r["graduate"]) == (
            advice["tier"], advice["label"], advice["why"], advice["lost_cp"], advice["carried_cp"], advice["extra_sessions"], advice["graduate_after"])


@pytest.mark.parametrize("key", KEYS)
def test_credit_points_kept_and_lost_add_up_to_what_the_student_has_done(students, key):
    result = rank_majors(students[key], 1)
    for r in result["rows"]:
        assert r["carried_cp"] + r["lost_cp"] == result["counted_cp"]


def test_the_sample_student_sees_a_mix_of_verdicts_best_first(students):
    result = rank_majors(students["sample"], 1)
    assert result["current"]["name"] == "Enterprise Software Development" and result["counted_cp"] == 120
    assert [r["label"] for r in result["rows"]] == ["Possible, but it costs time"] + ["Think carefully"] * 6
    assert result["rows"][0]["name"] == "Artificial Intelligence and Data Analytics" and result["rows"][0]["graduate"] == "Autumn 2029"


def test_a_first_year_loses_nothing_with_any_major_and_graduates_in_spring_2030(students):
    result = rank_majors(students["fresh"], 1)
    assert result["first_choice"] and result["counted_cp"] == 0
    assert {(r["label"], r["lost_cp"], r["graduate"]) for r in result["rows"]} == {("Good to switch", 0, "Spring 2030")}


def test_a_student_late_in_their_major_is_told_to_think_about_every_swap(students):
    assert {r["tier"] for r in rank_majors(students["late"], 1)["rows"]} == {"think"}


def test_an_unknown_order_falls_back_to_best_fit(students):
    conn = students["sample"]
    assert rank_majors(conn, 1, "nonsense")["sort"] == "fit" and rank_majors(conn, 1, "<script>")["rows"] == rank_majors(conn, 1)["rows"]


def test_row_of_takes_only_what_it_needs():
    advice = {"tier": "good", "label": "Good to switch", "why": "w", "carried_cp": 6, "lost_cp": 0, "lost": [], "carry_percent": 100, "extra_sessions": 0, "graduate_after": "Autumn 2028"}
    assert set(row_of(advice, "M", "N", False)) == {"code", "name", "is_current", "tier", "label", "why", "carried_cp", "lost_cp", "lost_subjects", "carry_percent", "extra_sessions", "graduate", "note"}


# --- the page ---------------------------------------------------------------------------------------------------------------------------------------------

def token(client):
    return TOKEN.search(client.get("/profile").get_data(as_text=True)).group(1)


def page(client, url="/major/fit"):
    res = client.get(url, follow_redirects=True)
    assert res.status_code == 200
    return res.get_data(as_text=True)


def test_it_needs_a_login(client):
    assert client.get("/major/fit").status_code == 302


def test_it_is_read_only(client, log_in):
    log_in()
    assert client.post("/major/fit", data={"csrf_token": token(client)}).status_code == 405
    for method in (client.put, client.delete, client.patch):
        assert method("/major/fit").status_code == 405


def test_it_changes_nothing(app, client, log_in):
    log_in()
    conn = db.connect(app.config["DATABASE"])
    tables = ("users", "enrolments", "planned_subjects", "subject_attempts")
    before = [sorted(tuple(r) for r in conn.execute(f"SELECT * FROM {t}")) for t in tables]  # noqa: S608
    for url in ("/major/fit", "/major/fit?sort=lost", "/major/fit?sort=graduation", "/major/fit?sort=x"):
        client.get(url)
    assert before == [sorted(tuple(r) for r in conn.execute(f"SELECT * FROM {t}")) for t in tables]  # noqa: S608
    conn.close()


def test_the_page_lists_every_major_with_its_numbers_and_a_link_to_its_swap_page(client, log_in):
    log_in()
    html = page(client)
    assert "<h1>Which major fits my progress?</h1>" in html and "Your major" in html and "Enterprise Software Development" in html
    links = re.findall(r'href="(/major/MAJ\d+)"', html)
    assert len(links) == 8 and len(set(links)) == 8  # seven swaps and the student's own major
    assert html.count("Look at this swap") == 7 and "Possible, but it costs time" in html and "Think carefully" in html
    assert "Autumn 2029" in html and "24 cp (4 subjects)" in html and "1 extra session" in html


def test_the_best_fit_order_is_numbered_and_the_others_are_not(client, log_in):
    log_in()
    ranked = page(client)
    assert "<th scope=\"col\">#</th>" in ranked and "<td>1</td>" in ranked and "<td>7</td>" in ranked
    other = page(client, "/major/fit?sort=name")
    assert "<th scope=\"col\">#</th>" not in other


def test_the_current_order_is_marked_and_names_are_in_order(client, log_in):
    log_in()
    html = page(client, "/major/fit?sort=name")
    assert re.search(r'<a href="/major/fit\?sort=name" aria-current="true">Name</a>', html)
    names = re.findall(r'<th scope="row">([^<]+)<br>', html)
    assert names[0] == "Enterprise Software Development" and names[1:] == sorted(names[1:])  # the student's own major first, then A to Z


def test_a_bad_order_is_ignored_and_never_shown_back(client, log_in):
    log_in()
    payload = '"><script>alert(1)</script>'
    html = page(client, f"/major/fit?sort={payload}")
    assert "<script>alert(1)</script>" not in html and 'aria-current="true">Best fit' in html


def test_the_table_is_accessible(client, log_in):
    log_in()
    html = page(client)
    assert '<caption class="visually-hidden">Majors, ordered by best fit' in html
    assert html.count('<th scope="col">') >= 7 and html.count('<th scope="row">') == 8
    assert '<meter min="0" max="120" value="96" optimum="120" aria-label="Credit points that carry over to Artificial Intelligence and Data Analytics">80%</meter>' in html
    assert '<span class="visually-hidden"> to Artificial Intelligence and Data Analytics</span>' in html  # a link's name says where it goes


def test_the_page_explains_how_the_fit_is_decided_from_the_advisors_own_numbers(client, log_in):
    log_in()
    html = page(client)
    assert "6 credit points or fewer would stop counting" in html and "2 or more extra sessions, or 36 or more credit points" in html


def test_the_numbers_match_what_the_swap_page_shows(client, log_in):
    log_in()
    html = page(client)
    row = re.search(r'<a href="(/major/MAJ10053)">', html).group(1)
    swap = page(client, row)
    assert "Possible, but it costs time" in swap and "Autumn 2029" in swap and "24 credit points" in swap


def test_a_first_year_gets_a_message_and_a_different_link_text(client, log_in):
    log_in()
    client.post("/simulator/reset", data={"csrf_token": token(client), "confirm": "yes", "profile": "fresh"})
    html = page(client)
    assert "You have not chosen a major yet" in html and "Nothing done yet" in html and html.count("See this major") == 8 and "Your major" not in html
    assert "Spring 2030" in html and "<meter" not in html


def test_the_majors_page_links_to_the_comparison(client, log_in):
    log_in()
    assert 'href="/major/fit">Rank all majors for my progress</a>' in page(client, "/major")


def test_the_fit_page_is_not_mistaken_for_a_major_code(client, log_in):
    log_in()
    assert client.get("/major/fit").status_code == 200 and client.get("/major/FIT").status_code in (400, 404)


def test_one_student_never_sees_anothers_numbers(client, register):
    register()
    html = page(client)
    assert "You have not chosen a major yet" in html and "Your major" not in html and "Enterprise Software Development" in html
