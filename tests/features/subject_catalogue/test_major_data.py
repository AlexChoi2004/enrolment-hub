import pytest

from features.subject_catalogue.seed_data import HANDBOOK_PREREQUISITES, PREREQUISITES
from features.subject_catalogue.service import load_credit_requirements, load_prerequisites

# (code, name, core subjects, options in the pool, how many options to choose)
MAJORS = [
    ("MAJ03519", "Enterprise Software Development", 5, 9, 3),
    ("MAJ10053", "Artificial Intelligence and Data Analytics", 3, 9, 5),
    ("MAJ02080", "Business Information Systems Management", 8, 0, 0),
    ("MAJ02900", "Cybersecurity and Privacy", 7, 2, 1),
    ("MAJ02092", "Interaction Design", 7, 7, 1),
    ("MAJ01156", "Mathematical Analysis", 7, 2, 1),
    ("MAJ03445", "Networking and Cybersecurity", 6, 9, 2),
    ("MAJ02901", "Quantum Computing", 5, 9, 3),
]


def membership(conn, major):
    return conn.execute(
        "SELECT subject_code, role FROM major_subjects WHERE major_code = ? ORDER BY subject_code", (major,)
    ).fetchall()


def test_there_are_eight_majors(conn):
    assert conn.execute("SELECT COUNT(*) FROM majors").fetchone()[0] == 8


@pytest.mark.parametrize("code,name,core,pool,choose", MAJORS)
def test_each_major_has_the_supplied_structure(conn, code, name, core, pool, choose):
    major = conn.execute("SELECT * FROM majors WHERE code = ?", (code,)).fetchone()
    assert major["name"] == name
    rows = membership(conn, code)
    assert sum(r["role"] == "core" for r in rows) == core
    assert sum(r["role"] == "option" for r in rows) == pool
    assert major["core_cp"] == core * 6
    assert major["options_cp"] == choose * 6


@pytest.mark.parametrize("code,name,core,pool,choose", MAJORS)
def test_every_major_totals_exactly_48_credit_points(conn, code, name, core, pool, choose):
    major = conn.execute("SELECT core_cp, options_cp FROM majors WHERE code = ?", (code,)).fetchone()
    assert major["core_cp"] + major["options_cp"] == 48
    assert core * 6 + choose * 6 == 48


@pytest.mark.parametrize("code,name,core,pool,choose", MAJORS)
def test_the_option_pool_is_big_enough_for_the_choice(conn, code, name, core, pool, choose):
    assert pool >= choose


def test_the_database_refuses_a_major_that_is_not_48_credit_points(conn):
    with pytest.raises(Exception, match="CHECK"):
        conn.execute("INSERT INTO majors (code, name, core_cp, options_cp) VALUES ('MAJ99999', 'Bad', 30, 6)")


def test_business_information_systems_has_no_options(conn):
    assert conn.execute("SELECT options_cp FROM majors WHERE code = 'MAJ02080'").fetchone()[0] == 0
    assert all(r["role"] == "core" for r in membership(conn, "MAJ02080"))


def test_every_membership_points_at_a_real_subject_and_major(conn):
    orphans = conn.execute(
        "SELECT ms.* FROM major_subjects ms LEFT JOIN subjects s ON s.code = ms.subject_code"
        " LEFT JOIN majors m ON m.code = ms.major_code WHERE s.code IS NULL OR m.code IS NULL"
    ).fetchall()
    assert orphans == []


def test_roles_are_only_core_or_option(conn):
    assert {r[0] for r in conn.execute("SELECT DISTINCT role FROM major_subjects")} == {"core", "option"}


def test_a_shared_subject_is_stored_once_with_a_membership_per_major(conn):
    capstone = conn.execute("SELECT COUNT(*) FROM subjects WHERE code = '41759'").fetchone()[0]
    majors = {r[0] for r in conn.execute("SELECT major_code FROM major_subjects WHERE subject_code = '41759'")}
    assert capstone == 1
    assert majors == {"MAJ03519", "MAJ10053", "MAJ02080", "MAJ02092", "MAJ03445", "MAJ02901"}


def test_a_subject_can_be_core_in_one_major_and_an_option_in_another(conn):
    roles = dict(conn.execute("SELECT major_code, role FROM major_subjects WHERE subject_code = '31250'").fetchall())
    assert roles == {"MAJ10053": "core", "MAJ02901": "option"}  # Introduction to Data Analytics
    roles = dict(conn.execute("SELECT major_code, role FROM major_subjects WHERE subject_code = '41889'").fetchall())
    assert roles == {"MAJ03519": "option", "MAJ02092": "option"}


def test_no_subject_code_is_duplicated(conn):
    total = conn.execute("SELECT COUNT(*) FROM subjects").fetchone()[0]
    assert total == conn.execute("SELECT COUNT(DISTINCT code) FROM subjects").fetchone()[0] == 181


def test_the_original_enterprise_software_data_is_unchanged(conn):
    stored = {r[0]: r[1] for r in conn.execute("SELECT category, COUNT(*) FROM subjects GROUP BY category")}
    assert stored["core"] == 16 and stored["honours_core"] == 3
    assert stored["major_core"] == 5 and stored["major_elective"] == 9 and stored["general_elective"] == 12
    assert stored["major_other"] == 60 + 76  # the other majors' subjects plus the sub-major-only subjects


def test_added_subjects_are_six_or_eight_credit_points_with_valid_offerings(conn):
    rows = conn.execute("SELECT credit_points, sessions_offered FROM subjects WHERE category = 'major_other'").fetchall()
    assert rows and all(r["credit_points"] in (6, 8) and r["sessions_offered"] in ("Autumn", "Spring", "Both") for r in rows)
    assert {r["credit_points"] for r in rows} == {6, 8}  # languages are 8 cp


# --- prerequisites: the added subjects follow the same model as the original ones -------------------------------

def test_prerequisite_status_is_unknown_only_for_subjects_not_researched_yet(conn):
    states = {r[0] for r in conn.execute("SELECT DISTINCT prereq_status FROM subjects")}
    assert states == {"required", "none", "unknown"}  # unknown: sub-major-only subjects not researched yet


def test_a_subject_is_required_exactly_when_it_has_a_rule(conn):
    with_rules = {r[0] for r in conn.execute(
        "SELECT subject_code FROM prerequisites UNION SELECT subject_code FROM credit_requirements")}
    required = {r[0] for r in conn.execute("SELECT code FROM subjects WHERE prereq_status = 'required'")}
    assert required == with_rules
    unknown = {r[0] for r in conn.execute("SELECT code FROM subjects WHERE prereq_status = 'unknown'")}
    assert len(unknown) == 76 and unknown.isdisjoint(with_rules)


def test_the_twelve_original_rules_are_kept_and_the_handbook_rules_are_added_on_top(conn):
    total = conn.execute("SELECT COUNT(*) FROM prerequisites").fetchone()[0]
    assert len(PREREQUISITES) == 12
    assert total == len(PREREQUISITES) + len(HANDBOOK_PREREQUISITES)


def test_alternatives_are_stored_as_one_group_and_ands_as_separate_groups(conn):
    rules = load_prerequisites(conn)
    # 41181 <- (31257 OR 31266 OR 31268 OR 41092) AND 41039
    assert [g["codes"] for g in rules["41181"]] == [["31257", "31266", "31268", "41092"], ["41039"]]
    # 31005 <- 31250 AND 48024
    assert [g["codes"] for g in rules["31005"]] == [["31250"], ["48024"]]
    # 31264 <- 31080 OR 31263
    assert [g["codes"] for g in rules["31264"]] == [["31080", "31263"]]
    # 32931 <- 32144 OR 41079 (the second route comes from the handbook)
    assert [g["codes"] for g in rules["32931"]] == [["32144", "41079"]]


def test_corequisites_are_flagged_as_concurrent(conn):
    rules = load_prerequisites(conn)
    concurrent = {s for s, groups in rules.items() if any(g["concurrent"] for g in groups)}
    assert concurrent == {"37161", "31263", "68416"}
    assert rules["37161"] == [{"codes": ["33130"], "concurrent": True}]
    assert rules["31263"] == [{"codes": ["31080", "48024"], "concurrent": True}]


def test_credit_point_conditions_are_separate_from_subject_prerequisites(conn):
    credit = load_credit_requirements(conn)
    assert credit["32009"] == [{"major_code": "MAJ03445", "major_name": "Networking and Cybersecurity", "min_cp": 30}]
    assert credit["32011"][0]["min_cp"] == 30
    rules = load_prerequisites(conn)
    assert [g["codes"] for g in rules["32009"]] == [["31277"]]  # only the subject is a prerequisite
    assert "MAJ03445" not in {c for groups in rules.values() for g in groups for c in g["codes"]}


def test_every_prerequisite_refers_to_real_subjects(conn):
    orphans = conn.execute(
        "SELECT p.subject_code FROM prerequisites p LEFT JOIN subjects a ON a.code = p.subject_code"
        " LEFT JOIN subjects b ON b.code = p.prereq_code WHERE a.code IS NULL OR b.code IS NULL"
    ).fetchall()
    assert orphans == []


def test_an_external_prerequisite_is_a_note_not_a_rule(conn):
    note = conn.execute("SELECT note FROM prerequisite_notes WHERE subject_code = '31243'").fetchone()[0]
    assert "41004" in note and "external" in note
    assert conn.execute("SELECT COUNT(*) FROM prerequisites WHERE subject_code = '31243'").fetchone()[0] == 0
    assert conn.execute("SELECT prereq_status FROM subjects WHERE code = '31243'").fetchone()[0] == "none"


def test_the_handbook_rules_replace_the_old_leads_on_original_subjects(conn):
    rules = load_prerequisites(conn)
    assert [g["codes"] for g in rules["41040"]] == [["41039"]]  # was only a lead before
    assert [g["codes"] for g in rules["31777"]] == [["31260"]]
    assert "31260" not in rules  # the handbook lists no prerequisite for Fundamentals of Interaction Design


def test_32146_is_a_note_not_a_rule_because_its_prerequisite_is_not_in_every_major_that_needs_it(conn):
    assert "32146" not in load_prerequisites(conn)
    note = conn.execute("SELECT note FROM prerequisite_notes WHERE subject_code = '32146'").fetchone()[0]
    assert "(31250 AND 48024)" in note and "Not enforced here" in note


def test_the_handbook_wording_is_kept_where_the_app_cannot_enforce_all_of_it(conn):
    note = conn.execute("SELECT note FROM prerequisite_notes WHERE subject_code = '41040'").fetchone()[0]
    assert note.startswith("UTS Handbook requisite: (48023 OR 41039)") and "Only the subjects in this app are enforced" in note
    assert conn.execute("SELECT COUNT(*) FROM prerequisite_notes WHERE subject_code = '31005'").fetchone()[0] == 1  # 41091 is not in the app


def test_degree_wide_credit_conditions_are_stored_without_a_major(conn):
    credit = load_credit_requirements(conn)
    assert credit["31272"] == [{"major_code": None, "major_name": "your degree", "min_cp": 72}]
    assert credit["31269"][0]["min_cp"] == 18 and credit["41078"][0]["min_cp"] == 36
    assert credit["42036"] == credit["42037"] == credit["32011"]  # the same 30 cp in the Networking major


def test_the_database_refuses_a_bad_concurrent_flag(conn):
    with pytest.raises(Exception, match="CHECK"):
        conn.execute("INSERT INTO prerequisites (subject_code, prereq_code, concurrent) VALUES ('31005', '33130', 5)")
