import pytest

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


def test_prerequisite_filter_supplied_vs_not_supplied(conn):
    supplied = service.list_subjects(conn, Filters(prereqs="supplied"))
    unknown = service.list_subjects(conn, Filters(prereqs="not_supplied"))
    assert len(supplied) == 12
    assert len(unknown) == 33
    assert codes(supplied).isdisjoint(codes(unknown))


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


def test_unknown_prerequisites_have_empty_list_and_unknown_status(conn):
    subject = service.get_subject(conn, "33130")
    assert subject["prereq_status"] == "not_supplied"
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
        {"q": " web ", "category": "core", "session": "Spring", "prereqs": "supplied"}, CATEGORIES
    )
    assert f == Filters(q="web", category="core", session="Spring", prereqs="supplied")


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