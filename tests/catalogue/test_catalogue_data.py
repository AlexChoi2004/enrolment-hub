import sqlite3

import pytest

from subject_catalogue.seed_data import TOTAL_CREDIT_POINTS


def credit_points(conn, category):
    row = conn.execute(
        "SELECT COALESCE(SUM(credit_points), 0) AS cp FROM subjects WHERE category = ?",
        (category,),
    ).fetchone()
    return row["cp"]


def test_course_and_major_metadata(conn):
    course = conn.execute("SELECT * FROM courses").fetchone()
    assert course["code"] == "C09119"
    assert course["major_code"] == "MAJ03519"
    assert course["handbook_year"] == 2027


def test_requirement_totals_add_up_to_degree_total(conn):
    total = conn.execute(
        "SELECT SUM(required_credit_points) AS t FROM requirement_categories"
    ).fetchone()["t"]
    assert total == TOTAL_CREDIT_POINTS == 192


def test_core_subjects_are_16_and_96_cp(conn):
    n = conn.execute("SELECT COUNT(*) AS n FROM subjects WHERE category='core'").fetchone()["n"]
    assert n == 16
    assert credit_points(conn, "core") == 96


def test_honours_core_is_24_cp_with_12cp_project_b(conn):
    assert credit_points(conn, "honours_core") == 24
    cp = conn.execute("SELECT credit_points FROM subjects WHERE code='31482'").fetchone()[0]
    assert cp == 12


def test_major_core_is_five_subjects_30_cp(conn):
    n = conn.execute("SELECT COUNT(*) AS n FROM subjects WHERE category='major_core'").fetchone()["n"]
    assert n == 5
    assert credit_points(conn, "major_core") == 30


def test_major_electives_offer_nine_to_choose_three_from(conn):
    n = conn.execute("SELECT COUNT(*) AS n FROM subjects WHERE category='major_elective'").fetchone()["n"]
    assert n == 9
    required = conn.execute(
        "SELECT required_credit_points FROM requirement_categories WHERE category='major_elective'"
    ).fetchone()[0]
    assert required == 18  # 3 x 6 cp


def test_general_electives_are_synthetic_and_enough_to_fill_24_cp(conn):
    rows = conn.execute("SELECT * FROM subjects WHERE category='general_elective'").fetchall()
    assert 10 <= len(rows) <= 20
    assert all(r["is_synthetic"] == 1 for r in rows)
    assert all(r["code"].startswith("SYN") for r in rows)
    assert sum(r["credit_points"] for r in rows) >= 24


def test_handbook_subjects_are_not_marked_synthetic(conn):
    n = conn.execute(
        "SELECT COUNT(*) AS n FROM subjects WHERE category <> 'general_elective' AND is_synthetic = 1"
    ).fetchone()["n"]
    assert n == 0


def test_exactly_12_supplied_prerequisite_rules(conn):
    n = conn.execute("SELECT COUNT(*) AS n FROM prerequisites").fetchone()["n"]
    assert n == 12


def test_specific_prerequisite_rule(conn):
    row = conn.execute(
        "SELECT prereq_code FROM prerequisites WHERE subject_code = ?", ("41026",)
    ).fetchone()
    assert row["prereq_code"] == "41025"


def test_subjects_with_a_rule_require_prerequisites_and_others_have_none(conn):
    with_rule = conn.execute("SELECT prereq_status FROM subjects WHERE code='41026'").fetchone()[0]
    without_rule = conn.execute("SELECT prereq_status FROM subjects WHERE code='33130'").fetchone()[0]
    assert with_rule == "required"
    assert without_rule == "none"


def test_schema_still_allows_an_explicit_unknown_status(conn):
    conn.execute("UPDATE subjects SET prereq_status = 'unknown' WHERE code = '33130'")
    status = conn.execute("SELECT prereq_status FROM subjects WHERE code='33130'").fetchone()[0]
    assert status == "unknown"


def test_schema_rejects_other_prerequisite_statuses(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE subjects SET prereq_status = 'maybe' WHERE code = '33130'")


def test_prerequisite_graph_has_no_cycles(conn):
    edges = {}
    for row in conn.execute("SELECT subject_code, prereq_code FROM prerequisites"):
        edges.setdefault(row["subject_code"], []).append(row["prereq_code"])

    visiting, done = set(), set()

    def visit(code):
        if code in done:
            return
        assert code not in visiting, f"cycle through {code}"
        visiting.add(code)
        for nxt in edges.get(code, []):
            visit(nxt)
        visiting.discard(code)
        done.add(code)

    for code in edges:
        visit(code)


def test_database_rejects_prerequisite_for_missing_subject(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO prerequisites VALUES ('41026', 'NOPE')")


def test_database_rejects_self_prerequisite(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO prerequisites VALUES ('41026', '41026')")


def test_seeding_twice_does_not_duplicate_rows(conn):
    from subject_catalogue.seed import seed_catalogue

    before = conn.execute("SELECT COUNT(*) FROM subjects").fetchone()[0]
    seed_catalogue(conn)
    after = conn.execute("SELECT COUNT(*) FROM subjects").fetchone()[0]
    assert before == after