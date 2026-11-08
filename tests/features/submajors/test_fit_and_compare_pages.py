import re

import pytest

from features.advisor.service import assess
from features.submajors.fit import ELECTIVES, ELECTIVES_NAME, rank_submajors
from features.subject_catalogue.service import list_submajors
from shared import db

TOKEN = re.compile(r'name="csrf_token" value="([^"]+)"')
PRESETS = ["fresh", "sample", "late", "failed"]


def page(client, url, status=200):
    res = client.get(url, follow_redirects=True)
    assert res.status_code == status, (url, res.status_code)
    return res.get_data(as_text=True)


def reset_to(client, key):
    token = TOKEN.search(client.get("/profile").get_data(as_text=True)).group(1)
    client.post("/simulator/reset", data={"csrf_token": token, "confirm": "yes", "profile": key})


@pytest.fixture(scope="module")
def students(tmp_path_factory):
    out = {}
    for key in PRESETS:
        path = tmp_path_factory.mktemp(key) / "t.db"
        db.build_database(str(path), demo_profile=key)
        out[key] = db.connect(str(path))
    yield out
    for c in out.values():
        c.close()


# --- fit for my progress: sub-majors ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("key", PRESETS)
def test_every_sub_major_and_general_electives_are_listed_once(students, key):
    conn = students[key]
    result = rank_submajors(conn, 1)
    codes = [r["code"] for r in result["rows"]] + ([result["current"]["code"]] if result["current"] else [])
    assert sorted(codes) == sorted([s["code"] for s in list_submajors(conn)] + [ELECTIVES]) and len(codes) == len(set(codes)) == 9


@pytest.mark.parametrize("key", PRESETS)
def test_each_row_is_exactly_the_swap_advice_for_that_option(students, key):
    conn = students[key]
    for r in rank_submajors(conn, 1)["rows"]:
        advice = assess(conn, 1, "electives") if r["code"] == ELECTIVES else assess(conn, 1, "submajor", r["code"])
        assert (r["tier"], r["label"], r["why"], r["lost_cp"], r["extra_sessions"], r["graduate"]) == (
            advice["tier"], advice["label"], advice["why"], advice["lost_cp"], advice["extra_sessions"], advice["graduate_after"])


def test_the_students_own_sub_major_is_kept_apart_and_electives_is_an_option_to_move_to(students):
    result = rank_submajors(students["sample"], 1)
    assert result["current"]["name"] == "Innovation and Entrepreneurship" and ELECTIVES in [r["code"] for r in result["rows"]]
    assert next(r for r in result["rows"] if r["code"] == ELECTIVES)["name"] == ELECTIVES_NAME


def test_a_first_year_can_lose_nothing_and_the_language_program_says_it_depends(students):
    result = rank_submajors(students["fresh"], 1)
    assert result["first_choice"] and result["current"] is None and result["counted_cp"] == 0
    lote = next(r for r in result["rows"] if r["code"] == "SMJ09035")
    assert lote["note"] == "The subjects depend on the language you choose." and all(r["lost_cp"] == 0 for r in result["rows"])


def test_an_unknown_order_falls_back_to_best_fit(students):
    conn = students["sample"]
    assert rank_submajors(conn, 1, "nonsense")["rows"] == rank_submajors(conn, 1)["rows"]


def test_the_fit_page_for_sub_majors(client, log_in):
    log_in()
    html = page(client, "/submajor/fit")
    assert "<h1>Which sub-major fits my progress?</h1>" in html and "Your choice" in html and "Innovation and Entrepreneurship" in html
    assert "General electives (no sub-major)" in html and 'href="/submajor/electives"' in html and html.count("Look at this swap") == 8
    assert "The subjects depend on the language you choose." in html and 'aria-current="true">Best fit' in html
    assert '<th scope="col">Sub-major</th>' in html and "Sub-majors, ordered by best fit" in html


def test_the_fit_page_for_a_first_year(client, log_in):
    log_in()
    reset_to(client, "fresh")
    html = page(client, "/submajor/fit")
    assert "You have not chosen a sub-major or general electives yet" in html and html.count("See this sub-major") == 9 and "Spring 2030" in html


def test_fit_needs_a_login_and_is_read_only(client, log_in):
    assert client.get("/submajor/fit").status_code == 302
    log_in()
    assert client.post("/submajor/fit").status_code == 405 and client.get("/submajor/fit?sort=<script>").status_code == 200


def test_the_sub_majors_page_links_to_both(client, log_in):
    log_in()
    html = page(client, "/submajor")
    assert 'href="/submajor/fit">Rank all sub-majors for my progress</a>' in html and 'href="/submajor/compare">Compare two sub-majors</a>' in html


# --- compare two sub-majors ---------------------------------------------------------------------------------------------------------------------------------

def test_two_sub_majors_are_compared(client, log_in):
    log_in()
    html = page(client, "/submajor/compare?a=SMJ10167&b=SMJ10166")
    assert "<h1>Compare two sub-majors</h1>" in html and "Closely related" in html and "57% of the smaller program" in html
    assert "Stochastic Processes and Financial Mathematics" in html and "<strong>Both:</strong> Mathematics" in html and "<strong>Both:</strong> Statistics and probability" in html
    assert '<option value="SMJ10167" selected>' in html and 'for="cmp-a">First sub-major</label>' in html


def test_unrelated_sub_majors(client, log_in):
    log_in()
    html = page(client, "/submajor/compare?a=SMJ10196&b=SMJ10190")
    assert "Nothing in common" in html and "They share no focus area." in html


def test_the_language_program_is_explained_not_compared(client, log_in):
    log_in()
    html = page(client, "/submajor/compare?a=SMJ09035&b=SMJ10157")
    assert "Cannot compare subject by subject" in html and "depend on the language you choose" in html and "<h2>What they share</h2>" not in html
    assert "Official description in the Handbook" in html


def test_sub_major_validation(client, log_in):
    log_in()
    assert client.get("/submajor/compare?a=SMJ99999&b=SMJ10157").status_code == 404
    assert client.get("/submajor/compare?a=MAJ02900&b=SMJ10157").status_code == 400  # a major is not a sub-major
    assert client.get("/submajor/compare?a=SMJ10157&b=SMJ10157").status_code == 200
    assert "Pick two different sub-majors to compare." in page(client, "/submajor/compare?a=SMJ10157&b=SMJ10157")
    res = client.get("/submajor/compare", query_string={"a": "'; DROP TABLE users;--", "b": "SMJ10157"})
    assert res.status_code == 400 and "DROP TABLE" not in res.get_data(as_text=True)


def test_compare_needs_a_login_and_is_read_only(client, log_in):
    assert client.get("/submajor/compare").status_code == 302
    log_in()
    assert client.post("/submajor/compare").status_code == 405


def test_the_compare_route_is_not_mistaken_for_a_sub_major_code(client, log_in):
    log_in()
    assert client.get("/submajor/compare").status_code == 200 and client.get("/submajor/fit").status_code == 200 and client.get("/submajor/COMPARE").status_code in (400, 404)


# --- the About tab ---------------------------------------------------------------------------------------------------------------------------------------------

def test_a_sub_major_page_has_the_same_two_tabs_and_opens_on_its_subjects(client, log_in):
    log_in()
    html = page(client, "/submajor/SMJ10157")
    assert '<nav class="tt-tabs" aria-label="Sub-major sections">' in html and '<a href="/submajor/SMJ10157" aria-current="page">Subjects</a>' in html
    assert "About this sub-major" not in html and "/submajor/SMJ10157/choose" in html


def test_the_sub_major_about_tab(client, log_in):
    log_in()
    html = page(client, "/submajor/SMJ10157?tab=about")
    assert "About this sub-major" in html and "<strong>Cybersecurity and privacy</strong> <span class=\"muted\">(7 subjects" in html
    assert 'https://coursehandbook.uts.edu.au/aos/2027/SMJ10157" target="_blank" rel="noopener noreferrer"' in html and "/submajor/SMJ10157/choose" not in html
    assert "24 credit points:" in html and 'href="/submajor/compare?a=SMJ10157">Compare with another sub-major</a>' in html


def test_the_2026_handbook_page_is_linked_for_humanitarian_engineering(client, log_in):
    log_in()
    assert "https://coursehandbook.uts.edu.au/aos/2026/SMJ10196" in page(client, "/submajor/SMJ10196?tab=about")


def test_the_language_programs_about_tab_does_not_pretend_to_have_a_focus(client, log_in):
    log_in()
    html = page(client, "/submajor/SMJ09035?tab=about")
    assert "no focus area can be worked out yet" in html and "The subjects depend on the language you choose" in html
