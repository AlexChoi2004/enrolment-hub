import pytest

from enrolment.service import evaluate_subjects
from subject_catalogue import service
from subject_catalogue.service import FilterError, Filters

CATEGORIES = {"core", "honours_core", "major_core", "major_elective", "general_elective"}


def codes(subjects):
    return {s["code"] for s in subjects}


def test_lists_all_45_subjects(conn):
    assert len(service.list_subjects(conn)) == 45


def test_search_by_name_is_case_insensitive(conn):
    found = codes(service.list_subjects(conn, Filters(q="PROGRAMMING")))
    assert {"41039", "48024"} <= found


def test_search_by_code(conn):
    assert codes(service.list_subjects(conn, Filters(q="41026"))) == {"41026"}


def test_filter_by_category(conn):
    result = service.list_subjects(conn, Filters(category="major_core"))
    assert len(result) == 5
    assert all(s["category"] == "major_core" for s in result)


def test_session_filter_includes_subjects_offered_both_sessions(conn):
    result = service.list_subjects(conn, Filters(session="Autumn"))
    assert result
    assert all(s["sessions_offered"] in ("Autumn", "Both") for s in result)


def test_prerequisite_filter_required_vs_none(conn):
    required = service.list_subjects(conn, Filters(prereqs="required"))
    none = service.list_subjects(conn, Filters(prereqs="none"))
    assert len(required) == 12
    assert len(none) == 33
    assert codes(required).isdisjoint(codes(none))


def test_percent_sign_is_not_a_wildcard(conn):
    assert service.list_subjects(conn, Filters(q="%")) == []
    assert service.list_subjects(conn, Filters(q="_")) == []


def test_sql_injection_text_is_treated_as_plain_text(conn):
    assert service.list_subjects(conn, Filters(q="' OR 1=1 --")) == []
    assert service.list_subjects(conn, Filters(q="'; DROP TABLE subjects; --")) == []
    assert len(service.list_subjects(conn)) == 45  # table still intact


def test_relations_are_attached(conn):
    subject = service.get_subject(conn, "41026")
    assert [p["code"] for p in subject["prerequisites"]] == ["41025"]
    intro = service.get_subject(conn, "41025")
    assert "41026" in [u["code"] for u in intro["unlocks"]]


def test_subject_without_a_rule_has_no_prerequisites(conn):
    subject = service.get_subject(conn, "33130")
    assert subject["prereq_status"] == "none"
    assert subject["prerequisites"] == []


def test_get_missing_subject_returns_none(conn):
    assert service.get_subject(conn, "NOPE99") is None


def test_valid_code_pattern():
    assert service.is_valid_code("41026")
    assert service.is_valid_code("SYN101")
    assert not service.is_valid_code("bad!code")
    assert not service.is_valid_code("")
    assert not service.is_valid_code("../etc")
    assert not service.is_valid_code("a" * 11)


def test_parse_filters_accepts_valid_values():
    f = service.parse_filters(
        {"q": " web ", "category": "core", "session": "Spring", "prereqs": "required"}, CATEGORIES
    )
    assert f == Filters(q="web", category="core", session="Spring", prereqs="required")


@pytest.mark.parametrize(
    "args",
    [
        {"category": "nonsense"},
        {"session": "Winter"},
        {"prereqs": "maybe"},
        {"q": "x" * 51},
    ],
)
def test_parse_filters_rejects_malformed_values(args):
    with pytest.raises(FilterError):
        service.parse_filters(args, CATEGORIES)


def test_subjects_are_grouped_by_category_then_sorted_by_name(conn):
    result = service.list_subjects(conn)
    order = [c["category"] for c in service.list_categories(conn)]
    positions = [order.index(s["category"]) for s in result]
    assert positions == sorted(positions)  # categories stay in degree order
    core = [s["name"].lower() for s in result if s["category"] == "core"]
    assert core == sorted(core)
    assert core[0] == "business requirements modelling"


def test_categories_report_how_many_subjects_they_hold(conn):
    counts = {c["category"]: c["subject_count"] for c in service.list_categories(conn)}
    assert counts == {
        "core": 16, "honours_core": 3, "major_core": 5, "major_elective": 9, "general_elective": 12,
    }


def test_category_rules_are_plain_english(conn):
    cats = {c["category"]: c for c in service.list_categories(conn)}

    def rule(key):
        c = cats[key]
        return service.category_rule(key, c["subject_count"], c["required_credit_points"])

    assert rule("core") == "All 16 required \u00b7 96 cp"
    assert rule("honours_core") == "All 3 required \u00b7 24 cp"
    assert rule("major_elective") == "Choose 3 of 9 \u00b7 18 cp required"
    assert rule("general_elective") == "Choose 4 of 12 \u00b7 24 cp required"


def test_grouping_keeps_degree_order_and_skips_empty_groups(conn):
    categories = service.list_categories(conn)
    groups = service.group_by_category(service.list_subjects(conn), categories)
    assert [g["category"] for g in groups] == [c["category"] for c in categories]
    only_core = service.group_by_category(
        service.list_subjects(conn, Filters(category="core")), categories
    )
    assert [g["category"] for g in only_core] == ["core"]


# --- student status on the catalogue -------------------------------------------

def demo_subjects(conn, filters=None):
    progress = evaluate_subjects(conn, 1)
    subjects = service.attach_status(service.list_subjects(conn, filters), progress)
    return subjects, progress


def test_attach_status_adds_status_and_note(conn):
    subjects, _ = demo_subjects(conn)
    by_code = {s["code"]: s for s in subjects}
    assert by_code["41039"]["status"] == "completed"
    assert by_code["41026"]["status"] == "enrolled"
    assert by_code["41052"]["status"] == "available"
    assert by_code["32931"]["status"] == "blocked"
    assert by_code["32931"]["note"].startswith("Needs 32144")


def test_prerequisites_are_marked_met_in_progress_or_not_met(conn):
    by_code = {s["code"]: s for s in demo_subjects(conn)[0]}
    assert [p["state"] for p in by_code["41026"]["prerequisites"]] == ["completed"]  # needs 41025
    assert [p["state"] for p in by_code["32931"]["prerequisites"]] == ["enrolled"]  # needs 32144
    conn.execute("DELETE FROM enrolments WHERE subject_code = '41039'")
    refreshed = {s["code"]: s for s in demo_subjects(conn)[0]}
    assert [p["state"] for p in refreshed["48024"]["prerequisites"]] == ["none"]


def test_status_filter_keeps_only_matching_subjects(conn):
    subjects, _ = demo_subjects(conn)
    completed = service.filter_by_status(subjects, "completed")
    assert len(completed) == 16
    assert all(s["status"] == "completed" for s in completed)
    assert len(service.filter_by_status(subjects, "enrolled")) == 4
    assert service.filter_by_status(subjects, "") == subjects


def test_status_values_are_validated():
    assert service.parse_filters({"status": "available"}, CATEGORIES).status == "available"
    with pytest.raises(FilterError):
        service.parse_filters({"status": "maybe"}, CATEGORIES)


def test_general_electives_heading_reports_four_of_four_and_is_complete(conn):
    subjects, progress = demo_subjects(conn)
    groups = {g["category"]: g for g in service.group_by_category(subjects, service.list_categories(conn), progress)}
    general = groups["general_elective"]
    assert general["rule"] == "Choose 4 of 12 \u00b7 4 of 4 chosen"
    assert general["complete"] is True
    assert "can't enrol in any more general electives" in general["note"]


def test_major_electives_heading_is_not_complete_yet(conn):
    subjects, progress = demo_subjects(conn)
    groups = {g["category"]: g for g in service.group_by_category(subjects, service.list_categories(conn), progress)}
    assert groups["major_elective"]["rule"] == "Choose 3 of 9 \u00b7 1 of 3 chosen"
    assert groups["major_elective"]["complete"] is False
    assert groups["major_elective"]["note"] == ""


def test_required_section_heading_reports_progress(conn):
    subjects, progress = demo_subjects(conn)
    groups = {g["category"]: g for g in service.group_by_category(subjects, service.list_categories(conn), progress)}
    assert groups["core"]["rule"] == "All 16 required \u00b7 9 completed, 1 in progress"
    assert groups["core"]["complete"] is False


def test_a_fully_completed_required_section_is_marked_complete(conn):
    conn.execute("DELETE FROM enrolments WHERE subject_code IN ('41026')")
    conn.executemany(
        "INSERT OR IGNORE INTO enrolments (user_id, subject_code, status, session_label) VALUES (1, ?, 'completed', 'Autumn 2027')",
        [("41026",), ("41759",)],
    )
    subjects, progress = demo_subjects(conn)
    groups = {g["category"]: g for g in service.group_by_category(subjects, service.list_categories(conn), progress)}
    assert groups["major_core"]["complete"] is True
    assert groups["major_core"]["note"] == "Everything in this section is completed."