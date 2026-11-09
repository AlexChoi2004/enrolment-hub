import re
import sqlite3

import pytest

from features.accounts.service import create_user
from features.advisor.service import ElectiveChoiceError, validate_electives
from features.degree_planner.service import get_plan
from features.enrolment.results import record_result
from features.enrolment.service import evaluate_subjects
from features.majors.service import choose_major
from features.subject_catalogue import handbook_2027 as hb
from features.subject_catalogue import service as cat
from features.subject_catalogue.seed import seed_catalogue
from features.submajors.service import choose_electives, choose_submajor
from shared import db

SUBJECT = "https://coursehandbook.uts.edu.au/subject/{year}/{code}"
AOS = "https://coursehandbook.uts.edu.au/aos/{year}/{code}"
HUMANITARIAN_2026 = {"43029", "99200", "977917", "97901", "41130"}  # the 2026 Humanitarian Engineering page's own subjects, as supplied


@pytest.fixture()
def conn(tmp_path):
    path = tmp_path / "t.db"
    db.build_database(str(path), demo_profile="fresh")
    c = db.connect(str(path))
    yield c
    c.close()


def link(code):
    return SUBJECT.format(year=2026 if code in HUMANITARIAN_2026 else 2027, code=code)


def every_listed_code():
    codes = set(hb.NAMES)
    for lists in hb.LANGUAGES.values():
        codes |= set(lists)
    return codes


# --- the stored links -----------------------------------------------------------------------------------------------------------------------------

def test_every_subject_the_handbook_lists_has_its_own_link_stored_once(conn):
    stored = dict(conn.execute("SELECT code, handbook_url FROM subjects").fetchall())
    missing = [c for c in every_listed_code() if stored.get(c) != link(c)]
    real = conn.execute("SELECT COUNT(*) FROM subjects WHERE is_synthetic = 0").fetchone()[0]
    assert missing == [] and len(every_listed_code()) == real == 177  # every real subject in the app is one the Handbook lists, and none is missing a link


def test_the_humanitarian_engineering_subjects_keep_the_supplied_2026_links(conn):
    for code in HUMANITARIAN_2026:
        assert conn.execute("SELECT handbook_url FROM subjects WHERE code = ?", (code,)).fetchone()[0] == f"https://coursehandbook.uts.edu.au/subject/2026/{code}"
    assert conn.execute("SELECT COUNT(*) FROM subjects WHERE handbook_url LIKE '%/2026/%'").fetchone()[0] == 5


def test_nothing_is_linked_that_is_not_a_real_subject(conn):
    assert {r[0] for r in conn.execute("SELECT code FROM subjects WHERE handbook_url IS NULL")} == {r[0] for r in conn.execute("SELECT code FROM subjects WHERE is_synthetic = 1")}
    assert conn.execute("SELECT COUNT(*) FROM subjects WHERE is_synthetic = 1 AND handbook_url IS NOT NULL").fetchone()[0] == 0


def test_every_major_and_sub_major_links_to_its_overview(conn):
    for code in hb.MAJORS:
        assert conn.execute("SELECT handbook_url FROM majors WHERE code = ?", (code,)).fetchone()[0] == AOS.format(year=2027, code=code)
    for code in list(hb.SUBMAJORS) + ["SMJ09035"]:
        expected = AOS.format(year=2026 if code == "SMJ10196" else 2027, code=code)
        assert conn.execute("SELECT handbook_url FROM submajors WHERE code = ?", (code,)).fetchone()[0] == expected


def test_the_transdisciplinary_stream_is_linked_and_the_free_electives_stream_is_not_invented(conn):
    assert conn.execute("SELECT handbook_url FROM streams WHERE code = 'CBK92069'").fetchone()[0] == "https://coursehandbook.uts.edu.au/aos/2027/CBK92069"
    assert conn.execute("SELECT COUNT(*) FROM streams WHERE code = 'CBK92186'").fetchone()[0] == 0  # no link was supplied, so none is made up
    stream = next(g["stream"] for g in cat.get_submajor(conn, "SMJ10196")["all_groups"] if g["stream"])
    assert stream["handbook_url"] == "https://coursehandbook.uts.edu.au/aos/2026/CBK92069"  # listed on the 2026 page, so linked as the 2026 page links it


def test_every_subject_in_every_major_and_sub_major_carries_its_link(conn):
    for code in hb.MAJORS:
        major = cat.get_major(conn, code)
        assert all(s["handbook_url"] == link(s["code"]) for s in major["core"] + major["options"])
    for code in list(hb.SUBMAJORS) + ["SMJ09035"]:
        sub = cat.get_submajor(conn, code)
        assert all(s["handbook_url"] == link(s["code"]) for g in sub["all_groups"] for s in g["subjects"])


def test_all_eight_transdisciplinary_subjects_have_their_own_link(conn):
    for code in hb.TD_STREAM[2]:
        assert conn.execute("SELECT handbook_url FROM subjects WHERE code = ?", (code,)).fetchone()[0] == SUBJECT.format(year=2027, code=code)


def test_a_link_can_only_point_at_the_handbook(conn):
    for bad in ("https://evil.example/x", "http://coursehandbook.uts.edu.au/x", "javascript:alert(1)", "https://coursehandbook.uts.edu.au.evil.example/x"):
        if bad.startswith("https://coursehandbook.uts.edu.au."):
            continue  # a look-alike host still starts with the Handbook's name; the page also only ever prints the stored value, never builds one from input
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("UPDATE subjects SET handbook_url = ? WHERE code = '41039'", (bad,))


def test_seeding_again_changes_nothing(conn):
    before = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("subjects", "majors", "major_subjects", "submajors", "submajor_groups", "submajor_group_subjects", "streams", "stream_subjects", "requirement_categories")}  # noqa: S608
    links = conn.execute("SELECT code, handbook_url FROM subjects ORDER BY code").fetchall()
    seed_catalogue(conn)
    seed_catalogue(conn)
    after = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in before}  # noqa: S608
    assert before == after and [tuple(r) for r in conn.execute("SELECT code, handbook_url FROM subjects ORDER BY code")] == [tuple(r) for r in links]


def test_adding_the_column_to_an_older_database_keeps_its_data_and_can_be_repeated():
    old = sqlite3.connect(":memory:")
    old.executescript("CREATE TABLE subjects (code TEXT PRIMARY KEY, name TEXT); INSERT INTO subjects VALUES ('41039', 'Programming 1');")
    db.add_missing_columns(old)
    db.add_missing_columns(old)
    assert old.execute("SELECT code, name, handbook_url FROM subjects").fetchall() == [("41039", "Programming 1", None)]


def test_a_shared_subject_is_one_record_in_many_structures(conn):
    assert conn.execute("SELECT COUNT(*) FROM subjects WHERE code = '41759'").fetchone()[0] == 1  # Capstone is core in six majors
    assert conn.execute("SELECT COUNT(DISTINCT major_code) FROM major_subjects WHERE subject_code = '41759'").fetchone()[0] == 6
    assert conn.execute("SELECT COUNT(*) FROM subjects").fetchone()[0] == conn.execute("SELECT COUNT(DISTINCT code) FROM subjects").fetchone()[0]


# --- the pages ---------------------------------------------------------------------------------------------------------------------------------------

def page(client, url):
    res = client.get(url, follow_redirects=True)
    assert res.status_code == 200, url
    return res.get_data(as_text=True)


def handbook_links_in(html):
    return re.findall(r'<a class="handbook-link" href="([^"]+)" target="_blank" rel="noopener noreferrer">', html)


def test_a_major_page_links_every_subject_and_the_overview_in_a_new_tab(client, log_in):
    log_in()
    html = page(client, "/major/MAJ10053")
    assert handbook_links_in(html).count("https://coursehandbook.uts.edu.au/aos/2027/MAJ10053") == 1
    subject_links = [u for u in handbook_links_in(html) if "/subject/" in u]
    assert sorted(subject_links) == sorted(link(c) for c in ["31250", "41040", "41759", "31243", "32146", "42028", "43023", "43025", "31005", "43036", "42050", "57304"])
    assert '<th scope="col">Handbook</th>' in html and "(opens in a new tab)" in html
    assert '<td class="code"><a href="/subjects/31250">31250</a></td><td><a href="/subjects/31250">Introduction to Data Analytics</a></td>' in html  # code and name open the in-app page


def test_a_sub_major_page_links_its_subjects_and_the_2026_exceptions(client, log_in):
    log_in()
    html = page(client, "/submajor/SMJ10196")
    links = handbook_links_in(html)
    assert "https://coursehandbook.uts.edu.au/aos/2026/SMJ10196" in links and "https://coursehandbook.uts.edu.au/aos/2026/CBK92069" in links
    for code in HUMANITARIAN_2026:
        assert f"https://coursehandbook.uts.edu.au/subject/2026/{code}" in links
    for code in hb.TD_STREAM[2]:
        assert f"https://coursehandbook.uts.edu.au/subject/2027/{code}" in links  # the stream's own subjects are 2027 pages


def test_the_language_sub_major_links_the_chosen_languages_subjects(client, log_in):
    log_in()
    html = page(client, "/submajor/SMJ09035?language=CBK90498")
    assert sorted(u for u in handbook_links_in(html) if "/subject/" in u) == sorted(link(c) for c in hb.LANGUAGES["Spanish"])


def test_the_electives_page_links_the_transdisciplinary_subjects_and_the_stream(client, log_in):
    log_in()
    html = page(client, "/submajor/electives")
    links = handbook_links_in(html)
    assert "https://coursehandbook.uts.edu.au/aos/2027/CBK92069" in links
    assert all(link(c) in links for c in hb.TD_STREAM[2])
    assert "Free electives" in html and "invented sample subjects" in html  # the free electives have no Handbook list, so none is shown as real


@pytest.mark.parametrize("code", hb.TD_STREAM[2])
def test_each_transdisciplinary_subject_has_a_page_that_says_what_is_not_loaded_and_links_the_handbook(client, log_in, code):
    log_in()
    html = page(client, f"/subjects/{code}")
    assert "TD: " in html and "6 credit points" in html and handbook_links_in(html) == [SUBJECT.format(year=2027, code=code)]
    assert "Not yet populated: no description has been loaded for this subject." in html
    assert "Not yet populated: the assessment tasks and weightings have not been loaded" in html and "<table" not in html.split("<h2>Assessment</h2>")[1].split("<h2>Prerequisites</h2>")[0]
    assert "invented" not in html.split("<h2>Assessment</h2>")[1].lower() and "weighting" not in html.split("<h2>Assessment</h2>")[1].lower().replace("weightings have not been loaded", "")


def test_a_subject_page_shows_its_handbook_link(client, log_in):
    log_in()
    html = page(client, "/subjects/31251")
    assert 'Official page: <a class="handbook-link" href="https://coursehandbook.uts.edu.au/subject/2027/31251" target="_blank" rel="noopener noreferrer">Handbook' in html


def test_an_invented_sample_elective_has_no_handbook_link(client, log_in):
    log_in()
    assert handbook_links_in(page(client, "/subjects/SYN101")) == []


# --- the elective rules: 6 cp transdisciplinary + 18 cp free, never one standing in for the other ---------------------------------------------------

@pytest.fixture()
def student(conn):
    user = create_user(conn, "elective.student@student.uni.edu.au", "Str0ng#Pass", "Autumn 2027")["id"]
    choose_major(conn, user, "MAJ03519")
    choose_electives(conn, user)
    return user


def progress(conn, user, category):
    return evaluate_subjects(conn, user)["categories"][category]


def test_the_two_requirements_are_separate_and_add_to_24(conn, student):
    cats = {c["category"]: c for c in cat.degree_categories(conn, student)}
    assert (cats["td_elective"]["required_credit_points"], cats["general_elective"]["required_credit_points"]) == (6, 18)
    assert cats["td_elective"]["required_credit_points"] + cats["general_elective"]["required_credit_points"] == 24


def test_a_transdisciplinary_subject_counts_once_and_only_as_the_transdisciplinary_elective(conn, student):
    record_result(conn, student, "95003", "Autumn 2026", "passed")
    assert progress(conn, student, "td_elective")["counted_cp"] == 6 and progress(conn, student, "general_elective")["counted_cp"] == 0
    in_degree = {s["code"]: s["category"] for s in cat.degree_subjects(conn, student) if s["in_degree"]}
    assert in_degree["95003"] == "td_elective"


def test_a_transdisciplinary_subject_cannot_also_be_counted_as_a_free_elective(conn, student):
    record_result(conn, student, "95003", "Autumn 2026", "passed")
    with pytest.raises(ElectiveChoiceError, match="general electives"):  # nothing is lost by the swap, so there is nothing to count: it is refused
        validate_electives(conn, student, "major", "MAJ10053", None, ["95003"])  # swapping major: 95003 still counts as the transdisciplinary elective, so it is not "lost"


def test_free_electives_alone_do_not_satisfy_the_transdisciplinary_requirement(conn, student):
    for code in ("SYN101", "SYN103", "SYN106"):
        record_result(conn, student, code, "Autumn 2026", "passed")
    assert progress(conn, student, "general_elective")["counted_cp"] == 18 and progress(conn, student, "td_elective")["counted_cp"] == 0
    remaining = get_plan(conn, student)["remaining_cp"]
    record_result(conn, student, "95004", "Autumn 2026", "passed")
    assert get_plan(conn, student)["remaining_cp"] == remaining - 6  # only the transdisciplinary subject closes the last 6 cp


def test_once_the_transdisciplinary_slot_is_full_a_second_one_cannot_be_taken(conn, student):
    assert evaluate_subjects(conn, student)["subjects"]["95004"]["reasons"] == []  # open while the slot is empty
    record_result(conn, student, "95003", "Autumn 2026", "passed")
    second = evaluate_subjects(conn, student)["subjects"]["95004"]
    assert second["reasons"] == ["Transdisciplinary elective requirement already complete"] and second["status"] == "blocked"
    assert progress(conn, student, "general_elective")["counted_cp"] == 0  # and it does not stand in for a free elective either


def test_a_failed_transdisciplinary_subject_earns_nothing_and_can_be_taken_again(conn, student):
    record_result(conn, student, "95003", "Autumn 2026", "failed")
    assert progress(conn, student, "td_elective")["counted_cp"] == 0
    status = evaluate_subjects(conn, student)["subjects"]["95003"]["status"]
    assert status not in ("completed", "enrolled")  # it is still open to enrol in again


def test_the_transdisciplinary_stream_also_serves_humanitarian_engineering_without_counting_twice(conn):
    user = create_user(conn, "hum.student@student.uni.edu.au", "Str0ng#Pass", "Autumn 2027")["id"]
    choose_major(conn, user, "MAJ03519")
    choose_submajor(conn, user, "SMJ10196")
    record_result(conn, user, "95003", "Autumn 2026", "passed")
    in_degree = {s["code"]: s["category"] for s in cat.degree_subjects(conn, user) if s["in_degree"]}
    assert in_degree["95003"].startswith("sub_choose_") and "td_elective" not in in_degree.values()  # counted in the sub-major's stream, not as an elective too
    assert evaluate_subjects(conn, user)["categories"][in_degree["95003"]]["counted_cp"] == 6


def test_a_shared_subject_counts_once_when_it_is_in_the_major_and_the_sub_major(conn):
    user = create_user(conn, "shared.student@student.uni.edu.au", "Str0ng#Pass", "Autumn 2027")["id"]
    choose_major(conn, user, "MAJ03519")
    choose_submajor(conn, user, "SMJ10190")  # 41889 is an option in both
    record_result(conn, user, "41889", "Autumn 2026", "passed")
    subjects = {s["code"]: s for s in cat.degree_subjects(conn, user)}
    assert subjects["41889"]["category"] == "major_elective" and subjects["41889"]["overlaps_major"] is True  # counted once, in the major, and flagged
    counted = sum(c["counted_cp"] for c in evaluate_subjects(conn, user)["categories"].values())
    assert counted == 6
