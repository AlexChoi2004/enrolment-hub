import pytest

from features.subject_catalogue.submajor_data import LANGUAGES, SUBMAJORS

NON_LANGUAGE = [s for s in SUBMAJORS if s[0] != "SMJ09035"]


def groups(conn, code):
    return conn.execute("SELECT * FROM submajor_groups WHERE submajor_code = ? ORDER BY position", (code,)).fetchall()


def members(conn, group_id):
    return [r[0] for r in conn.execute("SELECT subject_code FROM submajor_group_subjects WHERE group_id = ? ORDER BY subject_code", (group_id,))]


def test_there_are_eight_sub_majors_each_worth_24_credit_points(conn):
    rows = conn.execute("SELECT code, total_cp FROM submajors").fetchall()
    assert len(rows) == 8 and {r["total_cp"] for r in rows} == {24}


@pytest.mark.parametrize("code,name,note,spec", NON_LANGUAGE)
def test_each_sub_major_adds_up_to_24_credit_points(conn, code, name, note, spec):
    assert sum(g["required_cp"] for g in groups(conn, code)) == 24


@pytest.mark.parametrize("code,name,note,spec", NON_LANGUAGE)
def test_the_option_pool_is_big_enough_for_each_choice(conn, code, name, note, spec):
    for g in groups(conn, code):
        if g["kind"] == "choose" and not g["stream_code"]:
            pool = conn.execute(
                "SELECT SUM(s.credit_points) FROM submajor_group_subjects gs JOIN subjects s ON s.code = gs.subject_code WHERE gs.group_id = ?",
                (g["id"],)).fetchone()[0]
            assert pool >= g["required_cp"]


def test_core_and_option_groups_are_stored_separately(conn):
    assert [(g["kind"], g["required_cp"]) for g in groups(conn, "SMJ10157")] == [("core", 6), ("choose", 18)]
    assert [(g["kind"], g["required_cp"]) for g in groups(conn, "SMJ10156")] == [("core", 24)]
    assert [(g["kind"], g["required_cp"]) for g in groups(conn, "SMJ10196")] == [("core", 12), ("choose", 6), ("choose", 6)]


def test_mathematical_analysis_extension_has_two_option_groups_of_6_and_18(conn):
    gs = groups(conn, "SMJ10167")
    assert [(g["kind"], g["required_cp"]) for g in gs] == [("choose", 6), ("choose", 18)]
    assert members(conn, gs[0]["id"]) == ["35005", "37262"] and len(members(conn, gs[1]["id"])) == 6
    note = conn.execute("SELECT note FROM submajors WHERE code = 'SMJ10167'").fetchone()[0]
    assert "two groups of options" in note and "6 credit points" in note and "18" in note and "Verify" not in note  # the Handbook page confirms it, so it is no longer in doubt


def test_the_supplied_core_subjects_are_exact(conn):
    assert members(conn, groups(conn, "SMJ10165")[0]["id"]) == ["37233", "37242", "37345"]
    assert members(conn, groups(conn, "SMJ10156")[0]["id"]) == ["48080", "81529", "81546", "81547"]
    assert members(conn, groups(conn, "SMJ10190")[0]["id"]) == ["40005", "40006", "41889"]


def test_a_subject_in_several_sub_majors_is_stored_once_with_a_membership_per_group(conn):
    assert conn.execute("SELECT COUNT(*) FROM subjects WHERE code = '37161'").fetchone()[0] == 1
    roles = {r["submajor_code"]: r["kind"] for r in conn.execute(
        "SELECT g.submajor_code, g.kind FROM submajor_group_subjects gs JOIN submajor_groups g ON g.id = gs.group_id WHERE gs.subject_code = '37161'")}
    assert roles == {"SMJ10166": "core", "SMJ10165": "choose"}  # core in one, optional in another


def test_a_subject_can_belong_to_a_major_and_a_sub_major_without_a_duplicate_record(conn):
    assert conn.execute("SELECT COUNT(*) FROM subjects WHERE code = '48730'").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM major_subjects WHERE subject_code = '48730'").fetchone()[0] >= 1
    assert conn.execute("SELECT COUNT(*) FROM submajor_group_subjects WHERE subject_code = '48730'").fetchone()[0] == 1


def test_every_listed_subject_exists_in_the_catalogue(conn):
    orphans = conn.execute(
        "SELECT gs.subject_code FROM submajor_group_subjects gs LEFT JOIN subjects s ON s.code = gs.subject_code WHERE s.code IS NULL").fetchall()
    assert orphans == []


def test_the_language_sub_major_has_six_programs_of_eight_credit_point_subjects(conn):
    gs = groups(conn, "SMJ09035")
    assert len(gs) == 6 and {g["language_program"] for g in gs} == set(LANGUAGES)
    assert all(g["kind"] == "choose" and g["required_cp"] == 24 for g in gs)
    lote = [r[0] for g in gs for r in conn.execute("SELECT subject_code FROM submajor_group_subjects WHERE group_id = ?", (g["id"],))]
    assert len(lote) == len(set(lote)) == 59  # no subject belongs to two languages
    cps = {r[0] for r in conn.execute("SELECT credit_points FROM subjects WHERE code IN (%s)" % ",".join("?" * len(lote)), lote)}
    assert cps == {8}


def test_each_language_has_the_supplied_number_of_subjects(conn):
    sizes = {g["language_name"]: len(members(conn, g["id"])) for g in groups(conn, "SMJ09035")}
    assert sizes == {"Chinese": 13, "French": 10, "German": 8, "Italian": 8, "Japanese": 10, "Spanish": 10}


def test_the_stream_is_stored_apart_from_subjects_and_holds_the_eight_handbook_subjects(conn):
    stream = conn.execute("SELECT * FROM streams WHERE code = 'CBK92069'").fetchone()
    assert stream["name"] == "Transdisciplinary Electives" and stream["cp"] == 6 and "eight subjects" in stream["note"]
    members_of_stream = sorted(r[0] for r in conn.execute("SELECT subject_code FROM stream_subjects WHERE stream_code = 'CBK92069'"))
    assert members_of_stream == [f"9500{n}" for n in range(2, 10)]
    group = [g for g in groups(conn, "SMJ10196") if g["stream_code"]][0]
    assert sorted(r[0] for r in conn.execute("SELECT subject_code FROM stream_subjects WHERE stream_code = ?", (group["stream_code"],))) == members_of_stream


def test_the_new_subjects_are_unverified_not_invented(conn):
    for code in ("37242", "81529", "97101", "977917", "95003"):
        row = conn.execute("SELECT prereq_status FROM subjects WHERE code = ?", (code,)).fetchone()
        assert row[0] == "unknown"
        assert conn.execute("SELECT COUNT(*) FROM subject_descriptions WHERE subject_code = ?", (code,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM prerequisites WHERE subject_code = ?", (code,)).fetchone()[0] == 0


def test_the_sub_major_data_records_that_it_was_checked_against_the_handbook(conn):
    rows = conn.execute("SELECT source, academic_year, verification FROM submajors").fetchall()
    assert all(r["academic_year"] == 2027 and r["verification"] == "verified" and "checked against the UTS Handbook" in r["source"] and "8 November 2026" in r["source"] for r in rows)


def test_the_database_refuses_a_sub_major_that_is_not_24_credit_points(conn):
    with pytest.raises(Exception, match="CHECK"):
        conn.execute("INSERT INTO submajors (code, name, total_cp, source, verification) VALUES ('SMJ99999', 'Bad', 18, 's', 'supplied')")


def test_seeding_twice_adds_no_duplicates(conn):
    from features.subject_catalogue.seed import seed_submajors

    before = [conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("submajors", "submajor_groups", "submajor_group_subjects", "streams")]
    seed_submajors(conn)
    conn.commit()
    assert [conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("submajors", "submajor_groups", "submajor_group_subjects", "streams")] == before
