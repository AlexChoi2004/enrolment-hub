import json

import pytest

from features.accounts.service import create_user
from features.enrolment.results import record_result
from features.enrolment.service import enrol
from features.majors.service import choose_major
from features.submajors.service import choose_submajor
from ai_services.tools.registry import TOOLS, call_tool, tool_specs

AUTUMN = "Autumn 2027"
USER_WORDS = {"user", "user_id", "student", "student_id", "id", "email", "account"}

VALID_CALLS = {
    "search_subjects": {"query": "Programming"},
    "get_subject_info": {"code": "41026"},
    "check_prerequisites": {"code": "41052"},
    "list_offerings": {"code": "41026"},
    "check_plan_placement": {"code": "41052", "session": "Spring 2027"},
    "get_my_plan": {},
    "get_session_workload": {"session": "Autumn 2027"},
    "find_clash_free_classes": {"code": "41026", "session": "Autumn 2027"},
    "get_my_results": {},
    "get_swap_advice": {"kind": "major", "code": "MAJ10053"},
}


@pytest.fixture()
def fresh(conn):
    user = create_user(conn, "new.student@student.uni.edu.au", "Str0ng#Pass", AUTUMN)["id"]
    choose_major(conn, user, "MAJ03519")
    choose_submajor(conn, user, "SMJ10156")
    return user


def run(conn, user, name, **args):
    return call_tool(conn, user, name, args)


def data(conn, user, name, **args):
    result = run(conn, user, name, **args)
    assert result["ok"], result
    return result["data"]


# --- the registry -----------------------------------------------------------------------------------------------------------

def test_every_tool_has_a_description_and_a_closed_schema():
    specs = tool_specs()
    assert len(specs) == len(TOOLS) == 10 and set(VALID_CALLS) == set(TOOLS)
    for spec in specs:
        assert spec["description"] and spec["input_schema"]["type"] == "object"
        assert spec["input_schema"]["additionalProperties"] is False
        assert set(spec["input_schema"]["required"]) <= set(spec["input_schema"]["properties"])


def test_the_specs_can_be_sent_as_json():
    assert json.loads(json.dumps(tool_specs()))


def test_no_tool_lets_the_caller_name_a_student():
    for spec in tool_specs():
        assert not (set(spec["input_schema"]["properties"]) & USER_WORDS), spec["name"]


@pytest.mark.parametrize("name", list(VALID_CALLS))
def test_every_tool_works_for_the_demo_student_and_returns_plain_json(conn, name):
    result = call_tool(conn, 1, name, VALID_CALLS[name])
    assert result["ok"] is True
    assert json.loads(json.dumps(result["data"])) == result["data"]


# --- the student is chosen by the server ------------------------------------------------------------------------------------

@pytest.mark.parametrize("word", sorted(USER_WORDS))
def test_a_model_cannot_ask_about_another_student(conn, fresh, word):
    result = call_tool(conn, fresh, "get_my_results", {word: 1})
    assert result == {"ok": False, "error": f"Unknown argument: {word}"}


def test_each_student_gets_only_their_own_data(conn, fresh):
    john = data(conn, 1, "get_my_results")
    new = data(conn, fresh, "get_my_results")
    assert john["passed_credit_points"] == 96 and new["passed_credit_points"] == 0 and new["sessions"] == []
    assert data(conn, 1, "get_my_plan")["period"]["year"] == 3 and data(conn, fresh, "get_my_plan")["period"]["year"] == 1


def test_a_students_own_failure_is_not_visible_to_another(conn, fresh):
    enrol(conn, fresh, "41039", AUTUMN)
    record_result(conn, fresh, "41039", AUTUMN, "failed")
    assert data(conn, fresh, "get_my_results")["needs_retake"] == ["41039"]
    assert data(conn, 1, "get_my_results")["needs_retake"] == []


# --- the arguments are checked before anything runs ----------------------------------------------------------------------

@pytest.mark.parametrize("name,args,message", [
    ("get_subject_info", {}, "Missing required argument: code"),
    ("get_subject_info", {"code": None}, "Missing required argument: code"),
    ("get_subject_info", {"code": 41039}, "code must be text."),
    ("get_subject_info", {"code": "41039'; DROP TABLE subjects;--"}, "code is not in the expected format."),
    ("get_subject_info", {"code": "../../etc/passwd"}, "code is not in the expected format."),
    ("get_subject_info", {"code": "x" * 500}, "code is too long."),
    ("check_plan_placement", {"code": "41052", "session": "Winter 2027"}, "session is not in the expected format."),
    ("check_plan_placement", {"code": "41052"}, "Missing required argument: session"),
    ("get_swap_advice", {"kind": "everything"}, "kind must be one of: major, submajor, electives"),
    ("get_swap_advice", {"kind": "major", "code": "BAD"}, "code is not in the expected format."),
    ("get_swap_advice", {"kind": "major", "code": "MAJ10053", "language": "xx"}, "language is not in the expected format."),
    ("search_subjects", {"query": "q" * 61}, "query is too long."),
    ("get_my_plan", {"anything": 1}, "Unknown argument: anything"),
])
def test_bad_arguments_are_refused_with_a_clear_message(conn, name, args, message):
    assert call_tool(conn, 1, name, args) == {"ok": False, "error": message}


def test_arguments_must_be_an_object(conn):
    assert call_tool(conn, 1, "get_subject_info", "41039") == {"ok": False, "error": "Arguments must be an object."}
    assert call_tool(conn, 1, "get_my_plan", None)["ok"] is True  # a tool with no arguments


def test_an_unknown_tool_is_refused(conn):
    assert call_tool(conn, 1, "delete_everything", {}) == {"ok": False, "error": "Unknown tool: delete_everything"}


def test_a_bad_call_never_raises(conn):
    for name in TOOLS:
        for args in ({"code": {"a": 1}}, {"session": ["x"]}, {"kind": 5}, {"query": 1.5}, [], 7):
            result = call_tool(conn, 1, name, args)
            assert set(result) <= {"ok", "data", "error"}


# --- nothing is ever changed -----------------------------------------------------------------------------------------------------

def snapshot(conn):
    tables = ("users", "enrolments", "planned_subjects", "class_choices", "subject_attempts", "prerequisites", "subjects")
    return {t: sorted(tuple(r) for r in conn.execute(f"SELECT * FROM {t}")) for t in tables}  # noqa: S608


def test_no_tool_changes_any_data(conn):
    before = snapshot(conn)
    for name, args in VALID_CALLS.items():
        call_tool(conn, 1, name, args)
    call_tool(conn, 1, "get_swap_advice", {"kind": "electives"})
    call_tool(conn, 1, "get_swap_advice", {"kind": "submajor", "code": "SMJ10157"})
    assert snapshot(conn) == before


def test_asking_for_swap_advice_leaves_the_students_choices_alone(conn):
    call_tool(conn, 1, "get_swap_advice", {"kind": "major", "code": "MAJ03445"})
    assert tuple(conn.execute("SELECT major_code, submajor_code FROM users WHERE id = 1").fetchone()) == ("MAJ03519", "SMJ10156")


# --- what each tool says ----------------------------------------------------------------------------------------------------------

def test_search_finds_subjects_by_part_of_a_name_or_code(conn):
    names = [m["name"] for m in data(conn, 1, "search_subjects", query="programming")["matches"]]
    assert "Programming 1" in names and "Programming 2" in names
    assert data(conn, 1, "search_subjects", query="41039")["matches"][0]["name"] == "Programming 1"


def test_search_is_limited_and_treats_wildcards_as_plain_text(conn):
    assert len(data(conn, 1, "search_subjects", query="a")["matches"]) <= 10
    assert data(conn, 1, "search_subjects", query="%")["matches"] == []
    assert run(conn, 1, "search_subjects", query="   ") == {"ok": False, "error": "query must not be empty."}


def test_subject_info_has_the_facts_and_the_students_own_status(conn):
    info = data(conn, 1, "get_subject_info", code="41052")
    assert info["name"] == "Advanced Algorithms" and info["credit_points"] == 6 and info["sessions_offered"] == "Spring"
    assert info["assessment_load"] == 4 and "not a UTS rating" in info["assessment_load_note"]
    assert info["my_status"] == "available" and info["assessments_known"] is True
    assert "due week 4 (illustrative)" in info["assessment_summary"]


def test_subject_info_keeps_and_or_logic_and_credit_conditions(conn):
    assert data(conn, 1, "get_subject_info", code="41181")["prerequisites"] == [
        "(31257 Information System Development Methodologies or 31266 Introduction to Information Systems or 31268 Web Systems or 41092 Network Fundamentals)",
        "41039 Programming 1"]
    assert data(conn, 1, "get_subject_info", code="31272")["prerequisites"][-1] == "72 credit points completed in your degree"
    assert data(conn, 1, "get_subject_info", code="41039")["prerequisites"] == []


def test_unconfirmed_assessment_information_says_not_enough_context(conn):
    info = data(conn, 1, "get_subject_info", code="41759")  # Capstone
    assert info["assessments_known"] is False and info["assessment_summary"].startswith("Not enough context")
    assert info["assessment_load"] is None


def test_the_unconfirmed_student_reported_tasks_never_reach_the_model(conn):
    text = json.dumps(run(conn, 1, "get_subject_info", code="43030")).lower()
    assert "job advertisement" not in text and "development portfolio" not in text and "not enough context" in text


def test_an_unknown_subject_is_a_clear_error(conn):
    assert run(conn, 1, "get_subject_info", code="00000") == {"ok": False, "error": "There is no subject 00000."}
    assert run(conn, 1, "list_offerings", code="00000")["ok"] is False


def test_prerequisite_checks_name_a_failed_prerequisite(conn, fresh):
    enrol(conn, fresh, "41039", AUTUMN)
    record_result(conn, fresh, "41039", AUTUMN, "failed")
    result = data(conn, fresh, "check_prerequisites", code="48024")
    assert result["status"] == "blocked" and "(failed: retake it first)" in result["note"]
    assert data(conn, fresh, "check_prerequisites", code="41039")["needs_retake"] is True


def test_a_subject_outside_the_students_degree_is_reported_as_not_part_of_it(conn, fresh):
    result = data(conn, fresh, "check_prerequisites", code="43025")  # a Quantum Computing core subject
    assert result["status"] == "blocked" and result["reasons"][0].startswith("Not part of your Enterprise Software Development major")


def test_prerequisite_check_for_a_subject_that_does_not_exist_is_refused(conn, fresh):
    assert run(conn, fresh, "check_prerequisites", code="00000") == {"ok": False, "error": "There is no subject 00000."}


def test_offerings_show_which_sessions_are_open(conn):
    result = data(conn, 1, "list_offerings", code="41052")  # Spring only
    assert result["sessions_offered"] == "Spring" and result["open_for_enrolment"] == ["Spring 2027"]
    assert data(conn, 1, "list_offerings", code="31265")["open_for_enrolment"] == ["Autumn 2027", "Spring 2027"]


def test_placement_checks_say_why_a_subject_would_be_refused(conn):
    ok = data(conn, 1, "check_plan_placement", code="41052", session="Spring 2027")
    assert ok["allowed"] is True and ok["reason"] is None
    no = data(conn, 1, "check_plan_placement", code="41052", session="Autumn 2028")
    assert no["allowed"] is False and "not offered in Autumn 2028" in no["reason"]
    assert data(conn, 1, "check_plan_placement", code="00000", session="Spring 2027")["reason"] == "That subject does not exist."


def test_the_plan_summary_has_the_period_counts_and_sessions(conn):
    plan = data(conn, 1, "get_my_plan")
    assert plan["period"] == {"label": AUTUMN, "year": 3, "semester": 1} and plan["counts"]["completed"] == 16
    assert plan["sessions"][0]["label"] == AUTUMN and len(plan["sessions"][0]["enrolled"]) == 4
    assert plan["sessions"][0]["workload"]["verdict"] == "Heavy" and plan["remaining_cp"] > 0


def test_the_plan_summary_lists_failed_subjects_and_stranded_plans(conn, fresh):
    from features.degree_planner.service import add_to_plan
    from features.simulator.service import complete_semester

    enrol(conn, fresh, "41039", AUTUMN)
    add_to_plan(conn, fresh, "33130", AUTUMN)
    complete_semester(conn, fresh, {"41039": {"result": "failed", "mark": None}})
    complete_semester(conn, fresh, {})
    plan = data(conn, fresh, "get_my_plan")
    assert any("41039 Programming 1" in s for s in plan["failed_to_retake"])
    assert any("33130" in s for s in plan["needs_rescheduling"])


def test_the_workload_tool_carries_the_caveats(conn):
    text = data(conn, 1, "get_session_workload", session=AUTUMN)["text"]
    assert text.startswith("Autumn 2027: Heavy workload") and "not a UTS rating" in text and "illustrative" in text
    assert run(conn, 1, "get_session_workload", session="Autumn 2040")["ok"] is False


def test_clash_free_classes_lists_only_options_that_do_not_clash(conn):
    result = data(conn, 1, "find_clash_free_classes", code="41026", session=AUTUMN)
    assert result["components"] and all("clash_free" in c for c in result["components"])
    assert run(conn, 1, "find_clash_free_classes", code="41039", session=AUTUMN)["error"] == "You are not enrolled in 41039 in Autumn 2027."
    assert run(conn, 1, "find_clash_free_classes", code="41026", session="Autumn 2031")["ok"] is False


def test_results_are_labelled_simulated_and_newest_first(conn):
    results = data(conn, 1, "get_my_results")
    assert "not genuine UTS academic records" in results["data_note"]
    assert results["sessions"][0]["session"] == AUTUMN and results["sessions"][-1]["session"] == "Autumn 2025"
    assert any("Programming 1: Passed (" in line and "attempt 1" in line for g in results["sessions"] for line in g["results"])


def test_swap_advice_matches_the_pages(conn):
    advice = data(conn, 1, "get_swap_advice", kind="major", code="MAJ10053")
    assert advice["label"] == "Possible, but it costs time" and advice["lost_cp"] == 24 and advice["extra_sessions"] == 1
    assert (advice["graduate_before"], advice["graduate_after"]) == ("Spring 2028", "Autumn 2029")
    assert advice["needs_ack"] is True and "$" not in json.dumps(advice)


def test_the_tool_says_when_it_would_be_a_first_choice(conn, fresh):
    brand_new = create_user(conn, "brand.new@student.uni.edu.au", "Str0ng#Pass", AUTUMN)["id"]
    advice = data(conn, brand_new, "get_swap_advice", kind="major", code="MAJ10053")
    assert advice["first_choice"] is True and "nothing to swap from" in advice["note"]
    assert "note" not in data(conn, 1, "get_swap_advice", kind="major", code="MAJ10053")


def test_swap_advice_for_electives_and_sub_majors(conn):
    assert data(conn, 1, "get_swap_advice", kind="electives")["target"] == "General electives"
    assert data(conn, 1, "get_swap_advice", kind="submajor", code="SMJ09035", language="CBK90495")["target"].endswith("(Japanese)")


@pytest.mark.parametrize("args,message", [
    ({"kind": "major"}, "code is required for a major or sub-major."),
    ({"kind": "major", "code": "SMJ10157"}, "That code does not match the kind."),
    ({"kind": "submajor", "code": "MAJ10053"}, "That code does not match the kind."),
    ({"kind": "major", "code": "MAJ00000"}, "That major or sub-major does not exist."),
])
def test_swap_advice_refuses_wrong_targets(conn, args, message):
    assert run(conn, 1, "get_swap_advice", **args) == {"ok": False, "error": message}
