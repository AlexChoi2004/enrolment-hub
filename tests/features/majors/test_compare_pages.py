import re

import pytest

from shared import db

TOKEN = re.compile(r'name="csrf_token" value="([^"]+)"')


def page(client, url, status=200):
    res = client.get(url, follow_redirects=True)
    assert res.status_code == status, (url, res.status_code)
    return res.get_data(as_text=True)


# --- compare two majors ------------------------------------------------------------------------------------------------------------------------------

def test_it_needs_a_login(client):
    assert client.get("/major/compare").status_code == 302


def test_without_a_choice_it_shows_the_form_with_every_major_in_both_menus(client, log_in):
    log_in()
    html = page(client, "/major/compare")
    assert "<h1>Compare two majors</h1>" in html and 'for="cmp-a">First major</label>' in html and 'for="cmp-b">Second major</label>' in html
    assert html.count('<option value="MAJ') == 16 and "Compare</button>" in html and "Verdict" not in html
    assert '<option value="MAJ03519" selected>' in html  # the student's own major is already picked as the first


def test_two_majors_are_compared(client, log_in):
    log_in()
    html = page(client, "/major/compare?a=MAJ02900&b=MAJ03445")
    assert "Partly similar" in html and "Cybersecurity and Privacy and Networking and Cybersecurity are partly similar" in html
    assert "<h2>What they share</h2>" in html and "<h2>What is different</h2>" in html and "<h2>Focus</h2>" in html and "<h2>In their descriptions</h2>" in html
    assert "33% of the smaller program" in html and "Digital Forensics" in html and "Mobile Networking" in html
    assert "<strong>Both:</strong> Cybersecurity and privacy" in html and "Only Networking and Cybersecurity:</strong> Networking and infrastructure" in html


def test_the_order_does_not_change_the_verdict(client, log_in):
    log_in()
    one = page(client, "/major/compare?a=MAJ02900&b=MAJ03445")
    two = page(client, "/major/compare?a=MAJ03445&b=MAJ02900")
    assert "Partly similar" in one and "Partly similar" in two and "33% of the smaller program" in two


def test_a_pair_with_nothing_in_common_says_so(client, log_in):
    log_in()
    html = page(client, "/major/compare?a=MAJ02080&b=MAJ01156")
    assert "Nothing in common" in html and "share no subjects" in html and "No subject appears in both." in html


def test_the_form_keeps_what_was_picked(client, log_in):
    log_in()
    html = page(client, "/major/compare?a=MAJ02900&b=MAJ03445")
    assert '<option value="MAJ02900" selected>' in html and '<option value="MAJ03445" selected>' in html


def test_picking_the_same_major_twice_asks_for_two_different_ones(client, log_in):
    log_in()
    html = page(client, "/major/compare?a=MAJ02900&b=MAJ02900")
    assert "Pick two different majors to compare." in html and "<h2>What they share</h2>" not in html


@pytest.mark.parametrize("query", ["a=MAJ99999&b=MAJ02900", "a=MAJ02900&b=MAJ99999"])
def test_a_major_that_does_not_exist_is_a_404(client, log_in, query):
    log_in()
    assert client.get(f"/major/compare?{query}").status_code == 404


@pytest.mark.parametrize("bad", ["x", "MAJ1", "../../etc", "MAJ02900'; DROP TABLE users;--", '"><script>alert(1)</script>', "maj02900", "A" * 300])
def test_a_malformed_code_is_a_400_and_never_echoed(client, log_in, bad):
    log_in()
    res = client.get("/major/compare", query_string={"a": bad, "b": "MAJ02900"})
    assert res.status_code == 400 and (len(bad) < 4 or bad not in res.get_data(as_text=True))  # a short payload could appear in any sentence


def test_it_is_read_only_and_changes_nothing(app, client, log_in):
    log_in()
    token = TOKEN.search(client.get("/profile").get_data(as_text=True)).group(1)
    assert client.post("/major/compare", data={"csrf_token": token}).status_code == 405
    conn = db.connect(app.config["DATABASE"])
    tables = ("users", "enrolments", "planned_subjects")
    before = [sorted(tuple(r) for r in conn.execute(f"SELECT * FROM {t}")) for t in tables]  # noqa: S608
    page(client, "/major/compare?a=MAJ02900&b=MAJ03445")
    assert before == [sorted(tuple(r) for r in conn.execute(f"SELECT * FROM {t}")) for t in tables]  # noqa: S608
    conn.close()


def test_the_page_is_never_cached(client, log_in):
    log_in()
    assert client.get("/major/compare?a=MAJ02900&b=MAJ03445").headers["Cache-Control"] == "no-store"


def test_each_program_in_the_result_links_to_its_own_page(client, log_in):
    log_in()
    html = page(client, "/major/compare?a=MAJ02900&b=MAJ03445")
    assert 'href="/major/MAJ02900"' in html and 'href="/major/MAJ03445"' in html


def test_the_table_is_accessible(client, log_in):
    log_in()
    html = page(client, "/major/compare?a=MAJ02900&b=MAJ03445")
    assert '<caption class="visually-hidden">Subjects in both Cybersecurity and Privacy and Networking and Cybersecurity</caption>' in html
    assert html.count('<th scope="col">') == 6 and 'aria-labelledby="cmp-verdict"' in html and html.count("<h1>") == 1


def test_the_rules_are_explained_from_the_real_cut_offs(client, log_in):
    log_in()
    assert "50% or more is closely related" in page(client, "/major/compare?a=MAJ02900&b=MAJ03445") and "25% or more is partly similar" in page(client, "/major/compare?a=MAJ02900&b=MAJ03445")


def test_the_majors_page_and_the_fit_page_link_to_it(client, log_in):
    log_in()
    assert 'href="/major/compare">Compare two majors</a>' in page(client, "/major") and 'href="/major/compare">Compare two majors</a>' in page(client, "/major/fit")


# --- the About tab ---------------------------------------------------------------------------------------------------------------------------------------

def test_a_major_page_still_opens_on_its_subjects_with_two_tabs(client, log_in):
    log_in()
    html = page(client, "/major/MAJ10053")
    assert '<nav class="tt-tabs" aria-label="Major sections">' in html and '<a href="/major/MAJ10053" aria-current="page">Subjects</a>' in html
    assert '<a href="/major/MAJ10053?tab=about">About</a>' in html and "<h2>Core subjects" in html and "About this major" not in html


def test_the_about_tab_shows_the_summary_the_focus_and_the_handbook_link(client, log_in):
    log_in()
    html = page(client, "/major/MAJ10053?tab=about")
    assert '<a href="/major/MAJ10053?tab=about" aria-current="page">About</a>' in html and "<h2 id=\"about-title\">About this major</h2>" in html
    assert "Covers the computing techniques behind artificial intelligence and data analytics" in html and "retrieved 2026-11-08" in html
    assert "<strong>Artificial intelligence and machine learning</strong>" in html and "<strong>Data analysis and visualisation</strong>" in html
    assert '<a href="https://coursehandbook.uts.edu.au/aos/2027/MAJ10053" target="_blank" rel="noopener noreferrer">' in html and "(opens in a new tab)" in html
    assert "<h2>Core subjects" not in html and 'href="/major/compare?a=MAJ10053">Compare with another major</a>' in html


def test_a_major_whose_handbook_page_has_no_overview_says_so_and_still_links_to_the_handbook(client, log_in):
    log_in()
    html = page(client, "/major/MAJ01156?tab=about")  # Mathematical Analysis: the Handbook page lists a structure but no overview
    assert "has no overview, so there is no description to summarise" in html and "https://coursehandbook.uts.edu.au/aos/2027/MAJ01156" in html
    assert "No written summary has been added" not in html and "<strong>Mathematics</strong>" in html  # the focus still comes from its subjects


def test_a_major_with_a_summary_shows_it_with_its_source_and_a_handbook_note(client, log_in):
    log_in()
    html = page(client, "/major/MAJ03445?tab=about")
    assert "Gives students the knowledge and skills to design networks" in html and "retrieved 2026-11-08" in html
    assert "take 41039 Programming 1 rather than 48023 Programming Fundamentals" in html  # the Handbook's note about this major


@pytest.mark.parametrize("tab", ["", "subjects", "ABOUT", "about%20", "x", "%3Cscript%3E", "about%26tab%3Dx"])
def test_any_other_tab_value_shows_the_subjects(client, log_in, tab):
    log_in()
    html = page(client, f"/major/MAJ10053?tab={tab}")
    assert "<h2>Core subjects" in html and "About this major" not in html


def test_the_swap_form_is_still_on_the_subjects_tab_and_not_on_the_about_tab(client, log_in):
    log_in()
    assert "/major/MAJ10053/choose" in page(client, "/major/MAJ10053") and "/major/MAJ10053/choose" not in page(client, "/major/MAJ10053?tab=about")
