import pytest

from accounts.service import create_user
from degree_planner.service import PlanError, add_to_plan, get_plan, move_in_plan, remove_from_plan, suggest_plan
from enrolment.service import EnrolmentError, enrol, evaluate_subjects, withdraw
from majors.service import MajorError, choose_major, preview, swap_blockers
from subject_catalogue import service as catalogue

AUTUMN, SPRING = "Autumn 2027", "Spring 2027"
ESD, AI, BISM, QUANTUM = "MAJ03519", "MAJ10053", "MAJ02080", "MAJ02901"


@pytest.fixture()
def student(conn):
    """A new account: no major chosen yet."""
    return create_user(conn, "new.student@student.uni.edu.au", "Str0ng#Pass", AUTUMN)["id"]


def major_of(conn, user_id):
    return conn.execute("SELECT major_code FROM users WHERE id = ?", (user_id,)).fetchone()["major_code"]


def status(conn, user_id, code):
    return evaluate_subjects(conn, user_id)["subjects"][code]["status"]


# --- the majors on offer ----------------------------------------------------------------------------------

def test_the_list_of_majors_summarises_each_without_listing_subjects(conn):
    majors = {m["code"]: m for m in catalogue.list_majors(conn)}
    assert len(majors) == 8
    ai = majors[AI]
    assert (ai["core_count"], ai["option_count"], ai["choose"]) == (3, 9, 5)
    assert "core" not in ai and "options" not in ai  # a summary only, no subject lists
    assert majors[BISM]["choose"] == 0 and majors[BISM]["option_count"] == 0


def test_one_major_lists_its_core_and_options(conn):
    major = catalogue.get_major(conn, "MAJ02900")
    assert len(major["core"]) == 7
    assert {s["code"] for s in major["options"]} == {"48436", "41185"}
    assert major["choose"] == 1


def test_an_unknown_major_is_none(conn):
    assert catalogue.get_major(conn, "MAJ00000") is None
    assert catalogue.get_major(conn, None) is None


# --- a new account has no major --------------------------------------------------------------------------------

def test_a_new_account_has_no_major(conn, student):
    assert major_of(conn, student) is None and catalogue.user_major(conn, student) is None


def test_the_demo_student_has_enterprise_software_development(conn):
    assert major_of(conn, 1) == ESD and catalogue.user_major(conn, 1)["name"] == "Enterprise Software Development"


def test_without_a_major_only_the_shared_sections_apply(conn, student):
    cats = [c["category"] for c in catalogue.degree_categories(conn, student)]
    assert cats == ["core", "honours_core", "general_elective"]


def test_without_a_major_major_subjects_are_not_in_the_degree(conn, student):
    in_degree = {s["code"] for s in catalogue.degree_subjects(conn, student) if s["in_degree"]}
    assert "41039" in in_degree and "SYN101" in in_degree  # core and general electives
    assert "41025" not in in_degree and "31250" not in in_degree  # major subjects


def test_without_a_major_major_subjects_cannot_be_taken(conn, student):
    assert status(conn, student, "41025") == "blocked"
    assert evaluate_subjects(conn, student)["subjects"]["41025"]["note"] == "Choose a major to take this subject"
    with pytest.raises(EnrolmentError, match="Choose a major to take this subject"):
        enrol(conn, student, "41025", AUTUMN)


def test_without_a_major_major_subjects_cannot_be_planned(conn, student):
    with pytest.raises(PlanError, match="is part of a major. Choose a major first"):
        add_to_plan(conn, student, "41025", "Spring 2028")


# --- choosing a major --------------------------------------------------------------------------------------------

def test_choosing_a_major_confirms_it(conn, student):
    result = choose_major(conn, student, AI)
    assert result == {"major": "Artificial Intelligence and Data Analytics", "swapped": False, "plan_removed": 0}
    assert major_of(conn, student) == AI


def test_an_unknown_major_is_refused(conn, student):
    with pytest.raises(MajorError, match="does not exist"):
        choose_major(conn, student, "MAJ00000")
    assert major_of(conn, student) is None


def test_choosing_your_current_major_again_is_refused(conn, student):
    choose_major(conn, student, AI)
    with pytest.raises(MajorError, match="already your major"):
        choose_major(conn, student, AI)


def test_the_chosen_major_changes_the_degree_sections(conn, student):
    choose_major(conn, student, AI)
    cats = {c["category"]: c for c in catalogue.degree_categories(conn, student)}
    assert cats["major_core"]["required_credit_points"] == 18 and cats["major_core"]["subject_count"] == 3
    assert cats["major_elective"]["required_credit_points"] == 30 and cats["major_elective"]["subject_count"] == 9


def test_a_major_with_no_options_has_no_elective_section(conn, student):
    choose_major(conn, student, BISM)
    cats = {c["category"]: c for c in catalogue.degree_categories(conn, student)}
    assert cats["major_core"]["required_credit_points"] == 48 and cats["major_core"]["subject_count"] == 8
    assert "major_elective" not in cats


def test_compulsory_subjects_are_core_and_the_rest_are_electives(conn, student):
    choose_major(conn, student, QUANTUM)
    by_code = {s["code"]: s["category"] for s in catalogue.degree_subjects(conn, student) if s["in_degree"]}
    assert by_code["41076"] == "major_core" and by_code["41174"] == "major_elective"
    assert by_code["31250"] == "major_elective"  # core in AI and Data Analytics, an option here


def test_the_same_subject_counts_differently_in_different_majors(conn):
    a = create_user(conn, "a.student@student.uni.edu.au", "Str0ng#Pass", AUTUMN)["id"]
    b = create_user(conn, "b.student@student.uni.edu.au", "Str0ng#Pass", AUTUMN)["id"]
    choose_major(conn, a, AI)
    choose_major(conn, b, QUANTUM)

    def category_of(uid):
        return {s["code"]: s["category"] for s in catalogue.degree_subjects(conn, uid)}["31250"]

    assert category_of(a) == "major_core" and category_of(b) == "major_elective"


def test_a_subject_from_another_major_is_blocked_with_the_reason(conn, student):
    choose_major(conn, student, AI)
    info = evaluate_subjects(conn, student)["subjects"]["41025"]  # an Enterprise Software Development subject
    assert info["status"] == "blocked" and info["note"] == "Not part of your Artificial Intelligence and Data Analytics major"


def test_subjects_of_the_chosen_major_can_be_enrolled(conn, student):
    choose_major(conn, student, AI)
    assert status(conn, student, "31250") == "available"
    assert enrol(conn, student, "31250", AUTUMN) == "31250 Introduction to Data Analytics"


def test_a_larger_option_requirement_allows_more_choices(conn, student):
    choose_major(conn, student, AI)  # choose 5 of 9
    cats = evaluate_subjects(conn, student)["categories"]["major_elective"]
    assert cats["required_cp"] == 30 and cats["pool"] == 9


# --- swapping -------------------------------------------------------------------------------------------------------

def test_a_new_account_can_swap_freely(conn, student):
    choose_major(conn, student, ESD)
    result = choose_major(conn, student, QUANTUM)
    assert result["swapped"] is True and major_of(conn, student) == QUANTUM


def test_swapping_changes_what_counts(conn, student):
    choose_major(conn, student, ESD)
    choose_major(conn, student, AI)
    assert status(conn, student, "41025") == "blocked" and status(conn, student, "31250") == "available"


def test_swapping_removes_planned_subjects_that_are_not_in_the_new_major(conn, student):
    choose_major(conn, student, ESD)
    add_to_plan(conn, student, "31927", "Spring 2028")  # Enterprise Software Development only
    add_to_plan(conn, student, "41040", "Autumn 2028")  # also a core subject in AI and Data Analytics
    result = choose_major(conn, student, AI)
    assert result["plan_removed"] == 1
    planned = {r["subject_code"] for r in conn.execute("SELECT subject_code FROM planned_subjects WHERE user_id = ?", (student,))}
    assert planned == {"41040"}


def test_a_swap_is_refused_while_enrolled_in_a_subject_only_the_old_major_has(conn, student):
    choose_major(conn, student, ESD)
    enrol(conn, student, "31777", AUTUMN)  # Enterprise Software Development option, not in Quantum Computing
    with pytest.raises(MajorError, match="31777 Advanced Interaction Design \\(enrolled\\)"):
        choose_major(conn, student, QUANTUM)
    assert major_of(conn, student) == ESD


def test_withdrawing_clears_the_way_to_swap(conn, student):
    choose_major(conn, student, ESD)
    enrol(conn, student, "31777", AUTUMN)
    withdraw(conn, student, "31777")
    choose_major(conn, student, QUANTUM)
    assert major_of(conn, student) == QUANTUM


def test_a_subject_shared_with_the_new_major_does_not_block_a_swap(conn, student):
    choose_major(conn, student, ESD)
    enrol(conn, student, "41040", AUTUMN)  # an option here, core in AI and Data Analytics
    choose_major(conn, student, AI)
    assert evaluate_subjects(conn, student)["subjects"]["41040"]["status"] == "enrolled"


def test_core_subjects_never_block_a_swap(conn, student):
    choose_major(conn, student, ESD)
    enrol(conn, student, "41039", AUTUMN)
    choose_major(conn, student, QUANTUM)


def test_the_demo_student_cannot_swap_after_completing_major_subjects(conn):
    blockers = swap_blockers(conn, 1, AI)
    assert {"41025", "41026", "48433", "31282"} <= {b["code"] for b in blockers}
    with pytest.raises(MajorError, match="41025 Introduction to Software Development \\(completed\\)"):
        choose_major(conn, 1, AI)
    assert major_of(conn, 1) == ESD


def test_the_preview_says_what_choosing_would_do(conn, student):
    page = preview(conn, student, AI)
    assert page["is_current"] is False and page["has_current"] is False and page["blockers"] == []
    choose_major(conn, student, AI)
    assert preview(conn, student, AI)["is_current"] is True
    assert preview(conn, student, "MAJ00000") is None


def test_the_preview_of_another_major_lists_blockers_for_the_demo_student(conn):
    assert preview(conn, 1, QUANTUM)["blockers"] and preview(conn, 1, ESD)["is_current"] is True


# --- the planner follows the major -----------------------------------------------------------------------------------

def test_the_plan_without_a_major_asks_for_one(conn, student):
    plan = get_plan(conn, student)
    assert plan["needs_major"] is True and plan["major"] is None
    assert plan["remaining_cp"] == 192 and plan["degree_total_cp"] == 192
    assert [s["label"] for s in plan["elective_sections"]] == ["General electives"]


def test_a_suggested_plan_without_a_major_leaves_the_major_for_later(conn, student):
    added, unplaced = suggest_plan(conn, student)
    plan = get_plan(conn, student)
    assert (added, unplaced) == (23, []) and plan["remaining_cp"] == 48 and plan["complete"] is False


@pytest.mark.parametrize("major", [ESD, AI, BISM, "MAJ02900", "MAJ02092", "MAJ01156", "MAJ03445", QUANTUM])
def test_every_major_can_be_planned_in_full(conn, major):
    uid = create_user(conn, "m.student@student.uni.edu.au", "Str0ng#Pass", AUTUMN)["id"]
    choose_major(conn, uid, major)
    added, unplaced = suggest_plan(conn, uid)
    plan = get_plan(conn, uid)
    assert (added, unplaced) == (31, []) and plan["complete"] is True and plan["remaining_cp"] == 0
    assert all(s["load_cp"] <= 24 for s in plan["sessions"])


def test_the_planner_lists_the_chosen_majors_electives(conn, student):
    choose_major(conn, student, AI)
    sections = {s["label"]: s for s in get_plan(conn, student)["elective_sections"]}
    assert (sections["Major electives"]["choose"], sections["Major electives"]["need"]) == (5, 5)
    codes = {c["code"] for c in sections["Major electives"]["candidates"]}
    assert "43036" in codes and "41025" not in codes


def test_a_major_without_options_has_no_major_electives_in_the_planner(conn, student):
    choose_major(conn, student, BISM)
    assert [s["label"] for s in get_plan(conn, student)["elective_sections"]] == ["General electives"]


def test_a_plan_cannot_include_another_majors_subject(conn, student):
    choose_major(conn, student, AI)
    with pytest.raises(PlanError, match="is not part of your Artificial Intelligence and Data Analytics major"):
        add_to_plan(conn, student, "41025", "Spring 2028")


# --- the added subjects' prerequisites are enforced like the originals ---------------------------------------------------

def complete(conn, user_id, *codes):
    for code in codes:
        conn.execute(
            "INSERT INTO enrolments (user_id, subject_code, status, session_label) VALUES (?, ?, 'completed', 'Autumn 2026')",
            (user_id, code),
        )
    conn.commit()


def note(conn, user_id, code):
    return evaluate_subjects(conn, user_id)["subjects"][code]["note"]


def test_a_subject_without_a_rule_can_be_taken_straight_away(conn, student):
    choose_major(conn, student, AI)
    assert status(conn, student, "31250") == "available"  # Introduction to Data Analytics has no prerequisite


def test_a_subject_with_a_rule_is_blocked_until_it_is_met(conn, student):
    choose_major(conn, student, AI)
    assert status(conn, student, "42028") == "blocked"
    assert note(conn, student, "42028") == "Needs 31250 Introduction to Data Analytics"
    complete(conn, student, "31250")
    assert status(conn, student, "42028") == "available"


def test_and_requires_every_group(conn, student):
    choose_major(conn, student, AI)  # 31005 Machine Learning <- 31250 AND 48024
    complete(conn, student, "31250")
    assert status(conn, student, "31005") == "blocked" and "48024 Programming 2" in note(conn, student, "31005")
    complete(conn, student, "48024")
    assert status(conn, student, "31005") == "available"


def test_or_accepts_either_alternative(conn, student):
    choose_major(conn, student, "MAJ02092")  # 31264 Computer Graphics <- 31080 OR 31263
    assert status(conn, student, "31264") == "blocked"
    assert note(conn, student, "31264") == "Needs (31080 Interactive Media or 31263 Introduction to Computer Game Development)"
    complete(conn, student, "31263")
    assert status(conn, student, "31264") == "available"


def test_and_with_or_inside_names_each_missing_group(conn, student):
    choose_major(conn, student, BISM)  # 32146 <- (31250 OR 31266) AND (41040 OR 48024)
    assert note(conn, student, "32146") == (
        "Needs (31250 Introduction to Data Analytics or 31266 Introduction to Information Systems), "
        "(41040 Introduction to Artificial Intelligence or 48024 Programming 2)"
    )
    complete(conn, student, "31266")
    assert note(conn, student, "32146") == "Needs (41040 Introduction to Artificial Intelligence or 48024 Programming 2)"
    complete(conn, student, "48024")
    assert status(conn, student, "32146") == "available"


def test_an_enrolled_prerequisite_does_not_count(conn, student):
    choose_major(conn, student, AI)
    enrol(conn, student, "31250", AUTUMN)
    assert status(conn, student, "42028") == "blocked"


def test_a_corequisite_can_be_satisfied_by_being_enrolled(conn, student):
    choose_major(conn, student, "MAJ01156")  # 37161 <- 33130, which may be taken at the same time
    assert status(conn, student, "37161") == "blocked"
    enrol(conn, student, "33130", AUTUMN)
    assert status(conn, student, "37161") == "available"


def test_an_external_prerequisite_is_not_enforced(conn, student):
    choose_major(conn, student, AI)
    assert status(conn, student, "31243") == "available"  # its only lead is a subject that is not in this data


def test_the_option_limit_follows_the_chosen_major(conn, student):
    choose_major(conn, student, "MAJ02900")  # Cybersecurity and Privacy: choose 1 of 2 options
    complete(conn, student, "48730")  # Digital Forensics needs Cybersecurity
    enrol(conn, student, "48436", AUTUMN)
    assert status(conn, student, "41185") == "blocked"
    assert evaluate_subjects(conn, student)["subjects"]["41185"]["reasons"] == ["Major electives requirement already complete"]


# --- credit-point conditions ---------------------------------------------------------------------------------------------

NETWORKING = "MAJ03445"
CORE_30_WITHOUT_ROUTING = ("31275", "48730", "43037", "42891", "41759")  # 30 cp in the major, but not 31277


def test_a_credit_condition_and_a_prerequisite_are_both_reported(conn, student):
    choose_major(conn, student, NETWORKING)
    reasons = evaluate_subjects(conn, student)["subjects"]["32009"]["reasons"]
    assert reasons == [
        "Needs 31277 Routing and Switching Essentials",
        "Needs 30 credit points completed in Networking and Cybersecurity (you have 0)",
    ]


def test_the_prerequisite_alone_is_not_enough(conn, student):
    choose_major(conn, student, NETWORKING)
    complete(conn, student, "31277")
    assert evaluate_subjects(conn, student)["subjects"]["32009"]["reasons"] == [
        "Needs 30 credit points completed in Networking and Cybersecurity (you have 6)"
    ]


def test_the_credit_points_alone_do_not_replace_the_prerequisite(conn, student):
    choose_major(conn, student, NETWORKING)
    complete(conn, student, *CORE_30_WITHOUT_ROUTING)
    assert evaluate_subjects(conn, student)["subjects"]["32009"]["reasons"] == ["Needs 31277 Routing and Switching Essentials"]


def test_meeting_both_conditions_makes_the_subject_available(conn, student):
    choose_major(conn, student, NETWORKING)
    complete(conn, student, "31277", "31275", "48730", "43037", "42891")  # 30 cp in the major, including 31277
    assert status(conn, student, "32009") == "available" and status(conn, student, "32011") == "available"


def test_enrolled_credit_points_do_not_count_towards_a_condition(conn, student):
    choose_major(conn, student, NETWORKING)
    complete(conn, student, "31277")
    for code in ("31275", "43037"):
        conn.execute("INSERT INTO enrolments (user_id, subject_code, status, session_label) VALUES (?, ?, 'enrolled', ?)",
                     (student, code, AUTUMN))
    conn.commit()
    assert status(conn, student, "32009") == "blocked"


def test_a_credit_condition_counts_only_the_named_major(conn, student):
    choose_major(conn, student, NETWORKING)
    complete(conn, student, "31277", "41039", "33130", "31265", "37181", "33230")  # lots of credit, mostly outside the major
    assert "you have 6" in evaluate_subjects(conn, student)["subjects"]["32009"]["reasons"][0]


# --- planning with the new rules --------------------------------------------------------------------------------------------

def test_a_plan_follows_the_same_prerequisites(conn, student):
    choose_major(conn, student, "MAJ02900")
    with pytest.raises(PlanError, match="Needs 31251 Data Structures and Algorithms completed or planned in an earlier session"):
        add_to_plan(conn, student, "41184", "Autumn 2028")  # Secure Programming <- Data Structures and Algorithms
    # 41184 is offered in Autumn only, so it goes in the first Autumn after 31251's session.
    for code, session in [("41039", "Autumn 2027"), ("48024", "Spring 2027"), ("31251", "Autumn 2028"), ("41184", "Autumn 2029")]:
        add_to_plan(conn, student, code, session)


def test_planning_accepts_either_alternative(conn, student):
    choose_major(conn, student, "MAJ02092")
    add_to_plan(conn, student, "31263", "Autumn 2028")
    add_to_plan(conn, student, "31264", "Spring 2028")  # Computer Graphics <- 31080 OR 31263


def test_removing_one_alternative_is_fine_while_another_still_satisfies_the_rule(conn, student):
    choose_major(conn, student, "MAJ02092")
    add_to_plan(conn, student, "31080", "Autumn 2028")
    add_to_plan(conn, student, "31263", "Autumn 2028")
    add_to_plan(conn, student, "31264", "Spring 2028")
    remove_from_plan(conn, student, "31080")  # 31263 still satisfies Computer Graphics
    with pytest.raises(PlanError, match="31264 Computer Graphics is planned for Spring 2028 and needs 31263"):
        remove_from_plan(conn, student, "31263")


def test_a_corequisite_may_be_planned_in_the_same_session_but_not_later(conn, student):
    choose_major(conn, student, "MAJ01156")
    add_to_plan(conn, student, "33130", "Spring 2028")
    add_to_plan(conn, student, "37161", "Spring 2028")  # the same session is fine for a corequisite
    with pytest.raises(PlanError, match="is planned for Spring 2028 and needs 33130"):
        move_in_plan(conn, student, "33130", "Autumn 2029")


def test_a_planned_credit_condition_counts_earlier_completed_and_planned_credit(conn, student):
    choose_major(conn, student, NETWORKING)
    complete(conn, student, "31277")
    with pytest.raises(PlanError, match=r"Needs 30 credit points completed in Networking and Cybersecurity \(6 completed"):
        add_to_plan(conn, student, "32009", "Spring 2028")
    complete(conn, student, "31275", "48730", "43037", "42891")
    add_to_plan(conn, student, "32009", "Spring 2028")


def test_a_business_information_systems_student_can_still_plan_data_visualisation(conn, student):
    choose_major(conn, student, BISM)
    add_to_plan(conn, student, "31266", "Autumn 2027")  # the alternative route through Introduction to Information Systems
    add_to_plan(conn, student, "41039", "Autumn 2027")
    add_to_plan(conn, student, "48024", "Spring 2027")
    add_to_plan(conn, student, "32146", "Spring 2028")


# --- the timetable has classes for the new subjects ------------------------------------------------------------------

def test_subjects_from_other_majors_have_classes_too(conn, student):
    from timetable.service import get_timetable

    choose_major(conn, student, "MAJ03445")
    enrol(conn, student, "31277", AUTUMN)
    card = get_timetable(conn, student, AUTUMN)["subjects"][0]
    assert card["code"] == "31277" and card["lecture"] and card["components"]