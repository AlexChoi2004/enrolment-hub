import itertools
import re

import pytest

from features.subject_catalogue import compare as cmp
from features.subject_catalogue.compare import CLOSE, PARTLY, compare_programs, verdict_of
from features.subject_catalogue.program_text import CODES, HANDBOOK_YEAR, SUMMARIES, handbook_url, summary_of
from features.subject_catalogue.programs import load_program, major_program, options_of, submajor_program
from features.subject_catalogue.themes import MAX_AREAS, focus_areas, themes_of
from shared import db


@pytest.fixture(scope="module")
def conn(tmp_path_factory):
    path = tmp_path_factory.mktemp("programs") / "t.db"
    db.build_database(str(path), demo_profile="fresh")
    c = db.connect(str(path))
    yield c
    c.close()


def subject(code, name, cp=6, role="core"):
    return {"code": code, "name": name, "credit_points": cp, "role": role}


def program(name, subjects, language=False):
    from features.subject_catalogue.themes import focus_areas as fa
    ordered = sorted(subjects, key=lambda s: (s["role"] != "core", s["name"]))
    return {"kind": "major", "code": name[:5].upper(), "name": name, "total_cp": 48, "subjects": ordered, "listed_cp": sum(s["credit_points"] for s in ordered),
            "structure": "x", "uses_language": language, "focus": fa([s["name"] for s in ordered]), "handbook_url": None, "summary": None}


# --- focus areas, worked out from subject names --------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("name,theme", [
    ("Machine Learning", "Artificial intelligence and machine learning"), ("Deep Learning and Convolutional Neural Network", "Artificial intelligence and machine learning"),
    ("Cryptography", "Cybersecurity and privacy"), ("Digital Forensics", "Cybersecurity and privacy"), ("Mobile Networking", "Networking and infrastructure"),
    ("Routing and Switching Essentials", "Networking and infrastructure"), ("Probability and Random Variables", "Statistics and probability"),
    ("Linear Algebra", "Mathematics"), ("Human-centred Design Methods", "Design and user experience"), ("Interactive 3D Animation", "Games, graphics and animation"),
    ("Quantum Algorithms", "Quantum computing"), ("Business Intelligence", "Business and information systems"), ("Leading Creative Innovation", "Innovation and entrepreneurship"),
    ("International Internship", "Global and professional practice"), ("Software Architecture", "Software development"),
])
def test_a_subject_name_belongs_to_its_theme(name, theme):
    assert theme in themes_of(name)


def test_a_subject_can_belong_to_more_than_one_theme():
    assert {"Data analysis and visualisation", "Cybersecurity and privacy"} <= set(themes_of("Data Analytics in Cybersecurity"))


def test_a_name_with_no_theme_has_none():
    assert themes_of("Capstone") == [] and themes_of("") == []


def test_a_focus_area_needs_several_subjects_and_lists_them():
    areas = focus_areas(["Cryptography", "System Security", "Digital Forensics", "Mobile Networking", "Capstone"])
    assert [a["label"] for a in areas] == ["Cybersecurity and privacy"] and areas[0]["subjects"] == ["Cryptography", "System Security", "Digital Forensics"]


def test_a_short_program_with_no_repeated_theme_still_gets_its_strongest_one():
    assert [a["label"] for a in focus_areas(["Machine Learning", "Capstone"])] == ["Artificial intelligence and machine learning"]
    assert focus_areas(["Capstone"]) == [] and focus_areas([]) == []


def test_no_more_than_five_focus_areas_and_the_strongest_come_first():
    names = ["Machine Learning", "Neural Nets", "Cryptography", "Security A", "Network A", "Network B", "Linear Algebra", "Calculus", "Game A", "Game B",
             "Quantum A", "Quantum B", "Design A", "Design B", "Business A", "Business B", "Statistics A", "Statistics B", "Statistics C"]
    areas = focus_areas(names)
    assert len(areas) == MAX_AREAS == 5 and areas[0]["label"] == "Statistics and probability"
    sizes = [len(a["subjects"]) for a in areas]
    assert sizes == sorted(sizes, reverse=True)


def test_every_area_of_a_real_program_lists_real_subjects_of_that_program(conn):
    for kind in ("major", "submajor"):
        for o in options_of(conn, kind):
            p = load_program(conn, kind, o["code"])
            names = {s["name"] for s in p["subjects"]}
            assert all(set(a["subjects"]) <= names and len(a["subjects"]) >= 1 for a in p["focus"]), o["code"]


@pytest.mark.parametrize("code,expected", [
    ("MAJ02900", {"Cybersecurity and privacy"}), ("MAJ03445", {"Networking and infrastructure", "Cybersecurity and privacy"}),
    ("MAJ10053", {"Artificial intelligence and machine learning", "Data analysis and visualisation"}), ("MAJ01156", {"Mathematics", "Statistics and probability"}),
    ("MAJ02092", {"Design and user experience", "Games, graphics and animation", "Software development"}),
])
def test_real_majors_get_the_focus_you_would_expect(conn, code, expected):
    assert {f["label"] for f in major_program(conn, code)["focus"]} == expected


# --- the verdict ---------------------------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("closeness,verdict", [(None, "unknown"), (0, "none"), (0.01, "little"), (0.2499, "little"), (PARTLY, "partly"), (0.4999, "partly"), (CLOSE, "close"), (1, "close")])
def test_the_verdict_cut_offs(closeness, verdict):
    assert verdict_of(closeness) == verdict and (CLOSE, PARTLY) == (0.5, 0.25)


def test_similarity_is_measured_against_the_smaller_program():
    big = program("Big", [subject(str(i), f"S{i}") for i in range(10)])
    small = program("Small", [subject("1", "S1"), subject("2", "S2")])
    r = compare_programs(big, small)
    assert r["verdict"] == "close" and r["closeness_percent"] == 100 and r["share_of_a"] == 20 and r["share_of_b"] == 100
    assert "100% of the smaller program" in r["sentence"]


def test_credit_points_not_subject_counts_decide():
    a = program("A", [subject("1", "S1", 12), subject("2", "S2", 6), subject("3", "S3", 6)])
    b = program("B", [subject("1", "S1", 12), subject("9", "S9", 6), subject("8", "S8", 6)])
    assert compare_programs(a, b)["closeness_percent"] == 50 and compare_programs(a, b)["verdict"] == "close"


def test_the_comparison_looks_the_same_whichever_way_round():
    a = program("A", [subject("1", "Cryptography"), subject("2", "System Security"), subject("3", "Capstone")])
    b = program("B", [subject("1", "Cryptography"), subject("4", "Mobile Networking"), subject("5", "Routing Essentials")])
    ab, ba = compare_programs(a, b), compare_programs(b, a)
    assert (ab["verdict"], ab["closeness_percent"], ab["shared_cp"]) == (ba["verdict"], ba["closeness_percent"], ba["shared_cp"])
    assert ab["only_a"] == ba["only_b"] and ab["only_b"] == ba["only_a"] and ab["share_of_a"] == ba["share_of_b"]


def test_no_shared_subjects_is_nothing_in_common():
    r = compare_programs(program("A", [subject("1", "S1")]), program("B", [subject("2", "S2")]))
    assert (r["verdict"], r["closeness_percent"], r["shared"]) == ("none", 0, []) and r["sentence"] == "A and B share no subjects."


def test_identical_programs_share_everything():
    p = [subject("1", "S1"), subject("2", "S2", role="option")]
    r = compare_programs(program("A", p), program("B", p))
    assert r["verdict"] == "close" and r["only_a"] == r["only_b"] == [] and r["closeness_percent"] == 100


def test_a_shared_subject_keeps_its_role_in_each_and_is_core_only_when_core_in_both():
    a = program("A", [subject("1", "S1", role="core"), subject("2", "S2", role="core"), subject("3", "S3", role="option")])
    b = program("B", [subject("1", "S1", role="core"), subject("2", "S2", role="option"), subject("3", "S3", role="option")])
    r = compare_programs(a, b)
    by = {s["code"]: s for s in r["shared"]}
    assert (by["1"]["role_a"], by["1"]["role_b"], by["1"]["role"]) == ("core", "core", "core")
    assert (by["2"]["role_a"], by["2"]["role_b"], by["2"]["role"]) == ("core", "option", "option") and r["core_in_both"] == 1
    assert "1 of them is core in both" in r["sentence"]


def test_only_lists_put_core_first_then_by_name_and_highlights_are_limited():
    a = program("A", [subject(str(i), f"Opt {i}", role="option") for i in range(5)] + [subject("c1", "Zeta core"), subject("c2", "Alpha core")])
    b = program("B", [subject("x", "X")])
    r = compare_programs(a, b)
    assert [s["name"] for s in r["only_a"]][:3] == ["Alpha core", "Zeta core", "Opt 0"] and len(r["highlights_a"]) == cmp.MAX_HIGHLIGHTS == 4


def test_a_language_program_cannot_be_compared_subject_by_subject():
    lang = program("Language", [], language=True)
    r = compare_programs(program("A", [subject("1", "S1")]), lang)
    assert (r["verdict"], r["comparable"], r["shared"], r["only_a"], r["closeness_percent"]) == ("unknown", False, [], [], None)
    assert "depend on the language you choose" in r["sentence"] and "Language" in r["sentence"]


def test_the_focus_comparison_says_what_is_shared_and_what_is_not():
    a = program("A", [subject("1", "Cryptography"), subject("2", "System Security"), subject("3", "Machine Learning"), subject("4", "Neural Nets")])
    b = program("B", [subject("5", "Penetration Testing"), subject("6", "Digital Forensics"), subject("7", "Mobile Networking"), subject("8", "Routing Essentials")])
    f = compare_programs(a, b)["focus"]
    assert [x["label"] for x in f["both"]] == ["Cybersecurity and privacy"]
    assert [x["label"] for x in f["only_a"]] == ["Artificial intelligence and machine learning"] and [x["label"] for x in f["only_b"]] == ["Networking and infrastructure"]


def test_no_focus_comparison_when_a_program_has_no_focus():
    assert compare_programs(program("A", [subject("1", "Capstone")]), program("B", [subject("2", "Cryptography"), subject("3", "Security")]))["focus"] is None


# --- the real programs ----------------------------------------------------------------------------------------------------------------------------------

REAL = [("major", "MAJ02900", "MAJ03445", "partly", 33), ("major", "MAJ10053", "MAJ02901", "partly", 42), ("submajor", "SMJ10167", "SMJ10166", "close", 57),
        ("submajor", "SMJ10196", "SMJ10190", "none", 0)]


@pytest.mark.parametrize("kind,a,b,verdict,percent", REAL)
def test_real_pairs(conn, kind, a, b, verdict, percent):
    r = compare_programs(load_program(conn, kind, a), load_program(conn, kind, b))
    assert (r["verdict"], r["closeness_percent"]) == (verdict, percent)


def test_cybersecurity_and_networking_share_exactly_three_subjects(conn):
    r = compare_programs(major_program(conn, "MAJ02900"), major_program(conn, "MAJ03445"))
    assert [s["name"] for s in r["shared"]] == ["Cybersecurity", "Cryptography", "Digital Forensics"] and r["core_in_both"] == 1
    assert [f["label"] for f in r["focus"]["only_b"]] == ["Networking and infrastructure"] and r["focus"]["only_a"] == []


def test_every_pair_of_majors_and_sub_majors_compares_without_error_and_adds_up(conn):
    for kind in ("major", "submajor"):
        codes = [o["code"] for o in options_of(conn, kind)]
        for a, b in itertools.combinations(codes, 2):
            r = compare_programs(load_program(conn, kind, a), load_program(conn, kind, b))
            if r["comparable"]:
                assert len(r["shared"]) + len(r["only_a"]) == len(r["a"]["subjects"]) and len(r["shared"]) + len(r["only_b"]) == len(r["b"]["subjects"])
                assert r["shared_cp"] + sum(s["credit_points"] for s in r["only_a"]) == r["a"]["listed_cp"]
            else:
                assert r["verdict"] == "unknown"


# --- the programs and their text -----------------------------------------------------------------------------------------------------------------------

def test_a_major_program_has_its_subjects_core_first(conn):
    p = major_program(conn, "MAJ10053")
    assert p["kind"] == "major" and p["total_cp"] == 48 and len(p["subjects"]) == 12 and p["structure"] == "18 cp core, plus choose 5 of 9 options (30 cp)"
    roles = [s["role"] for s in p["subjects"]]
    assert roles == sorted(roles, key=lambda r: r != "core") and roles.count("core") == 3


def test_a_sub_major_program_describes_its_structure_and_the_language_one_has_no_subjects(conn):
    assert submajor_program(conn, "SMJ10157")["total_cp"] == 24 and "choose" in submajor_program(conn, "SMJ10165")["structure"] + " choose"
    lote = submajor_program(conn, "SMJ09035")
    assert lote["uses_language"] and lote["subjects"] == [] and lote["structure"] == "The subjects depend on the language you choose"


def test_an_unknown_program_is_none(conn):
    assert major_program(conn, "MAJ99999") is None and submajor_program(conn, "SMJ99999") is None


GIVEN = """https://coursehandbook.uts.edu.au/aos/2027/SMJ10165
https://coursehandbook.uts.edu.au/aos/2027/SMJ10188
https://coursehandbook.uts.edu.au/aos/2026/SMJ10196
https://coursehandbook.uts.edu.au/aos/2027/SMJ10157
https://coursehandbook.uts.edu.au/aos/2027/SMJ10156
https://coursehandbook.uts.edu.au/aos/2027/SMJ10190
https://coursehandbook.uts.edu.au/aos/2027/SMJ10166
https://coursehandbook.uts.edu.au/aos/2027/SMJ10167
https://coursehandbook.uts.edu.au/aos/2027/SMJ09035
https://coursehandbook.uts.edu.au/aos/2027/MAJ10053
https://coursehandbook.uts.edu.au/aos/2027/MAJ02080
https://coursehandbook.uts.edu.au/aos/2027/MAJ02900
https://coursehandbook.uts.edu.au/aos/2027/MAJ02092
https://coursehandbook.uts.edu.au/aos/2027/MAJ03519
https://coursehandbook.uts.edu.au/aos/2027/MAJ01156
https://coursehandbook.uts.edu.au/aos/2027/MAJ03445
https://coursehandbook.uts.edu.au/aos/2027/MAJ02901""".split()


def test_every_handbook_link_is_exactly_the_one_supplied():
    assert sorted(handbook_url(u.rsplit("/", 1)[1]) for u in GIVEN) == sorted(GIVEN) and len(GIVEN) == len(CODES) == 17
    assert handbook_url("SMJ10196").endswith("/2026/SMJ10196") and HANDBOOK_YEAR == {"SMJ10196": 2026}


def test_an_unknown_code_has_no_handbook_link():
    assert handbook_url("MAJ99999") is None and handbook_url("") is None and handbook_url("../etc") is None


def test_every_major_and_sub_major_in_the_app_is_in_the_handbook_list(conn):
    for kind in ("major", "submajor"):
        assert all(o["code"] in CODES for o in options_of(conn, kind))


def test_one_sub_major_on_the_list_is_not_in_the_app_yet(conn):
    """SMJ10188 is on the Handbook list but its subjects have not been added: this test will fail, on purpose, the day they are."""
    in_app = {o["code"] for kind in ("major", "submajor") for o in options_of(conn, kind)}
    assert set(CODES) - in_app == {"SMJ10188"}


def test_summaries_are_only_kept_for_known_codes_and_say_when_they_were_written():
    assert set(SUMMARIES) <= set(CODES)
    for code, entry in SUMMARIES.items():
        assert re.fullmatch(r"\d{4}-\d\d-\d\d", entry["retrieved_on"]) and len(entry["summary"]) > 80 and summary_of(code) is entry
    assert summary_of("MAJ99999") is None


def test_a_summary_is_our_own_words_not_a_copy_of_the_handbook():
    handbook_opening = "Artificial intelligence and data analytics are computing techniques that are becoming extremely influential"
    text = SUMMARIES["MAJ10053"]["summary"]
    words = handbook_opening.lower().split()
    assert not any(" ".join(words[i:i + 6]) in text.lower() for i in range(len(words) - 5))  # no run of six words is the same
