"""The app's majors, sub-majors, language lists and subject names, checked against the Handbook's 2027 structure as supplied on 8 November 2026
(features/subject_catalogue/handbook_2027.py). If the app drifts from it, or the Handbook data is updated, these tests say exactly where."""
import pytest

from features.subject_catalogue import handbook_2027 as hb
from features.subject_catalogue import service as cat
from features.subject_catalogue import submajor_data as sd
from shared import db


@pytest.fixture(scope="module")
def conn(tmp_path_factory):
    path = tmp_path_factory.mktemp("check") / "t.db"
    db.build_database(str(path), demo_profile="fresh")
    c = db.connect(str(path))
    yield c
    c.close()


@pytest.mark.parametrize("code", list(hb.MAJORS))
def test_a_major_has_the_handbooks_core_and_options(conn, code):
    want, major = hb.MAJORS[code], cat.get_major(conn, code)
    assert sorted(s["code"] for s in major["core"]) == sorted(want["core"])
    assert sorted(s["code"] for s in major["options"]) == sorted(c for _, _, codes in want["choose"] for c in codes)
    assert major["core_cp"] == 6 * len(want["core"]) and major["options_cp"] == sum(cp for _, cp, _ in want["choose"]) and major["core_cp"] + major["options_cp"] == want["cp"] == 48
    assert major["choose"] == sum(cp for _, cp, _ in want["choose"]) // 6


@pytest.mark.parametrize("code", list(hb.SUBMAJORS))
def test_a_sub_major_has_the_handbooks_groups_and_credit_points(conn, code):
    want, sub = hb.SUBMAJORS[code], cat.get_submajor(conn, code)
    core = [s["code"] for g in sub["groups"] if g["kind"] == "core" for s in g["subjects"]]
    choose = [(g["required_cp"], sorted(s["code"] for s in g["subjects"])) for g in sub["groups"] if g["kind"] == "choose" and not g["stream_code"]]
    assert sorted(core) == sorted(want["core"])
    assert sorted(choose) == sorted((cp, sorted(codes)) for _, cp, codes in want["choose"])
    assert sub["total_cp"] == want["cp"] == 24
    streams = [(g["stream_code"], g["required_cp"]) for g in sub["groups"] if g["stream_code"]]
    assert streams == want.get("stream", [])


def test_the_language_sub_major_has_the_six_handbook_language_programs_exactly(conn):
    sub = cat.get_submajor(conn, "SMJ09035")
    assert {l["name"]: sorted(s["code"] for s in l["subjects"]) for l in sub["languages"]} == {name: sorted(codes) for name, codes in hb.LANGUAGES.items()}
    assert {l["code"] for l in sub["languages"]} == {"CBK90494", "CBK90497", "CBK90499", "CBK90500", "CBK90495", "CBK90498"}
    assert all(s["credit_points"] == 8 for l in sub["languages"] for s in l["subjects"]) and sd.LANGUAGE_CP == 8


def test_every_subject_the_handbook_lists_is_in_the_app_with_its_name_and_credit_points(conn):
    rows = {r["code"]: (r["name"], r["credit_points"]) for r in conn.execute("SELECT code, name, credit_points FROM subjects")}
    for code, name in hb.NAMES.items():
        assert code in rows, code
        assert rows[code][0].lower() == name.lower() and rows[code][1] == hb.CREDIT_POINTS.get(code, 6), code  # (capitalisation differs for one name)


def test_the_core_and_honours_core_subjects_are_the_handbooks(conn):
    core = {r[0] for r in conn.execute("SELECT code FROM subjects WHERE category = 'core'")}
    honours = {r[0]: r[1] for r in conn.execute("SELECT code, credit_points FROM subjects WHERE category = 'honours_core'")}
    assert core == {"33130", "37181", "41039", "31265", "33230", "31269", "31271", "48024", "31268", "41092", "41078", "41080", "43030", "31251", "41079", "31272"}
    assert sum(1 for _ in core) * 6 == 96 and honours == {"32144": 6, "32931": 6, "31482": 12} and sum(honours.values()) == 24


def test_the_degree_adds_up_to_192_with_the_electives_split_in_two(conn):
    cats = {r["category"]: r["required_credit_points"] for r in conn.execute("SELECT category, required_credit_points FROM requirement_categories")}
    assert (cats["core"], cats["honours_core"], cats["td_elective"], cats["general_elective"]) == (96, 24, 6, 18)
    assert 96 + 24 + 48 + cats["td_elective"] + cats["general_elective"] == 192 and cats["td_elective"] + cats["general_elective"] == hb.ELECTIVES_BLOCK["cp"] == 24


def test_the_transdisciplinary_stream_has_exactly_the_eight_handbook_subjects(conn):
    stream, cp, codes = hb.TD_STREAM
    assert sorted(r[0] for r in conn.execute("SELECT subject_code FROM stream_subjects WHERE stream_code = ?", (stream,))) == sorted(codes)
    assert {r[0] for r in conn.execute("SELECT code FROM subjects WHERE category = 'td_elective'")} == set(codes) and cp == 6
    assert {r[0] for r in conn.execute("SELECT credit_points FROM subjects WHERE category = 'td_elective'")} == {6}


def test_the_free_electives_stream_has_no_made_up_handbook_subject_list():
    stream, cp = hb.ELECTIVES_BLOCK["free"]
    assert stream == "CBK92186" and cp == 18  # the Handbook gives no list: any subject can be a free elective
