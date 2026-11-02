import pytest

from accounts.service import create_user
from degree_planner.service import PlanError, add_to_plan, get_plan, suggest_plan
from enrolment.service import EnrolmentError, enrol, evaluate_subjects
from majors.service import choose_major
from subject_catalogue import service as catalogue
from submajors.service import SubmajorError, choose_submajor, impact, preview

AUTUMN = "Autumn 2027"
ESD = "MAJ03519"
OPTIMISATION, HUMANITARIAN, INFOSEC, INNOVATION = "SMJ10165", "SMJ10196", "SMJ10157", "SMJ10156"
IOS, MATH_EXT, STATS, LOTE = "SMJ10190", "SMJ10167", "SMJ10166", "SMJ09035"
JAPANESE, CHINESE = "CBK90495", "CBK90494"


@pytest.fixture()
def student(conn):
    """A new account with the Enterprise Software Development major and no sub-major yet."""
    user = create_user(conn, "new.student@student.uni.edu.au", "Str0ng#Pass", AUTUMN)["id"]
    choose_major(conn, user, ESD)
    return user


def complete(conn, user_id, *codes):
    for code in codes:
        conn.execute("INSERT INTO enrolments (user_id, subject_code, status, session_label) VALUES (?, ?, 'completed', 'Autumn 2026')", (user_id, code))
    conn.commit()


def categories(conn, user_id):
    return {c["category"]: c for c in catalogue.degree_categories(conn, user_id)}


def category_of(conn, user_id, code):
    return {s["code"]: s["category"] for s in catalogue.degree_subjects(conn, user_id)}[code]


def status(conn, user_id, code):
    return evaluate_subjects(conn, user_id)["subjects"][code]["status"]


# --- browsing --------------------------------------------------------------------------------------------------------

def test_every_sub_major_can_be_listed_with_its_structure(conn):
    listed = {s["code"]: s for s in catalogue.list_submajors(conn)}
    assert len(listed) == 8
    assert (listed[INFOSEC]["core_cp"], listed[INFOSEC]["choose_cp"]) == (6, 18)
    assert (listed[INNOVATION]["core_cp"], listed[INNOVATION]["choose_cp"]) == (24, 0)
    assert listed[LOTE]["is_language"] is True and len(listed[LOTE]["languages"]) == 6


def test_a_sub_major_shows_its_core_and_option_groups(conn):
    sub = catalogue.get_submajor(conn, INFOSEC)
    assert [(g["kind"], g["required_cp"], len(g["subjects"])) for g in sub["all_groups"]] == [("core", 6, 1), ("choose", 18, 6)]


def test_an_unknown_sub_major_is_none(conn):
    assert catalogue.get_submajor(conn, "SMJ00000") is None and catalogue.get_submajor(conn, None) is None


# --- selecting -------------------------------------------------------------------------------------------------------

def test_a_new_account_has_no_sub_major(conn, student):
    assert catalogue.user_submajor(conn, student) is None


def test_selecting_a_sub_major_confirms_it(conn, student):
    result = choose_submajor(conn, student, INFOSEC)
    assert result["submajor"] == "Information Security" and result["swapped"] is False
    assert catalogue.user_submajor(conn, student)["code"] == INFOSEC


def test_the_demo_student_already_has_one(conn):
    assert catalogue.user_submajor(conn, 1)["code"] == INNOVATION


def test_an_unknown_sub_major_is_refused(conn, student):
    with pytest.raises(SubmajorError, match="does not exist"):
        choose_submajor(conn, student, "SMJ00000")


def test_choosing_the_same_sub_major_again_is_refused(conn, student):
    choose_submajor(conn, student, INFOSEC)
    with pytest.raises(SubmajorError, match="already your sub-major"):
        choose_submajor(conn, student, INFOSEC)


def test_a_language_is_ignored_for_a_sub_major_that_has_none(conn, student):
    choose_submajor(conn, student, INFOSEC, JAPANESE)
    assert catalogue.user_submajor(conn, student)["language"] is None


# --- the structure counts towards the degree ----------------------------------------------------------------------------

def test_the_four_degree_parts_add_up_to_192(conn, student):
    choose_submajor(conn, student, INFOSEC)
    total = sum(c["required_credit_points"] for c in categories(conn, student).values())
    assert total == 96 + 24 + 48 + 24 == 192


def test_core_and_option_requirements_are_separate(conn, student):
    choose_submajor(conn, student, INFOSEC)
    cats = categories(conn, student)
    assert cats["sub_core"]["required_credit_points"] == 6
    options = [c for k, c in cats.items() if k.startswith("sub_choose_")]
    assert len(options) == 1 and options[0]["required_credit_points"] == 18 and options[0]["label"] == "Sub-major options"
    assert category_of(conn, student, "41181") == "sub_core"
    assert category_of(conn, student, "48730") == options[0]["category"]


def test_a_sub_major_with_two_option_groups_keeps_them_separate(conn, student):
    choose_submajor(conn, student, MATH_EXT)
    groups = sorted(c["required_credit_points"] for k, c in categories(conn, student).items() if k.startswith("sub_choose_"))
    assert groups == [6, 18]
    assert category_of(conn, student, "35005") != category_of(conn, student, "37335")


def test_a_subject_can_be_core_in_one_sub_major_and_an_option_in_another(conn, student):
    choose_submajor(conn, student, STATS)
    assert category_of(conn, student, "37161") == "sub_core"
    choose_submajor(conn, student, OPTIMISATION)
    assert category_of(conn, student, "37161").startswith("sub_choose_")  # an option here, core in Statistical Analysis


def test_a_subject_in_two_sub_majors_is_stored_once(conn):
    assert conn.execute("SELECT COUNT(*) FROM subjects WHERE code = '37242'").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(DISTINCT group_id) FROM submajor_group_subjects WHERE subject_code = '37242'").fetchone()[0] == 3


def test_a_subject_outside_the_sub_major_is_not_in_the_degree(conn, student):
    choose_submajor(conn, student, INFOSEC)
    assert status(conn, student, "37242") == "blocked"
    assert evaluate_subjects(conn, student)["subjects"]["37242"]["note"] == "Not part of your Information Security sub-major"


def test_without_a_sub_major_its_subjects_say_to_choose_one(conn, student):
    assert evaluate_subjects(conn, student)["subjects"]["37242"]["note"] == "Choose a sub-major to take this subject"


def test_the_plan_asks_for_a_sub_major_and_counts_its_24_cp(conn, student):
    plan = get_plan(conn, student)
    assert plan["needs_submajor"] is True and plan["remaining_cp"] == 192
    choose_submajor(conn, student, INFOSEC)
    assert get_plan(conn, student)["needs_submajor"] is False and get_plan(conn, student)["remaining_cp"] == 192


# --- completing core subjects and option groups ----------------------------------------------------------------------------

def test_core_progress_counts_completed_subjects(conn, student):
    choose_submajor(conn, student, INNOVATION)
    complete(conn, student, "48080", "81529")
    progress = evaluate_subjects(conn, student)["categories"]["sub_core"]
    assert (progress["completed"], progress["counted_cp"], progress["required_cp"]) == (2, 12, 24)


def test_options_count_up_to_the_required_credit_points(conn, student):
    choose_submajor(conn, student, INFOSEC)
    complete(conn, student, "41182", "41183")
    group = next(c for k, c in evaluate_subjects(conn, student)["categories"].items() if k.startswith("sub_choose_"))
    assert group["counted_cp"] == 12 and group["required_cp"] == 18
    assert status(conn, student, "41184") != "completed"


def test_a_group_cannot_be_exceeded_when_enrolling(conn, student):
    choose_submajor(conn, student, INFOSEC)
    complete(conn, student, "41182", "41183", "41184")  # 18 cp: the group is full
    with pytest.raises(EnrolmentError, match="Sub-major options requirement already complete"):
        enrol(conn, student, "41180", AUTUMN)


def test_a_group_cannot_be_exceeded_in_the_plan(conn, student):
    choose_submajor(conn, student, INFOSEC)
    add_to_plan(conn, student, "41039", "Autumn 2027")
    for code, session in [("41182", "Autumn 2028"), ("41183", "Spring 2028"), ("41185", "Spring 2029")]:
        add_to_plan(conn, student, code, session)
    with pytest.raises(PlanError, match="Sub-major options requirement would be exceeded"):
        add_to_plan(conn, student, "41180", "Autumn 2029")


def test_each_group_is_capped_separately(conn, student):
    choose_submajor(conn, student, MATH_EXT)
    complete(conn, student, "35005")  # fills the 6 cp group
    assert "Sub-major options group 1 requirement already complete" in evaluate_subjects(conn, student)["subjects"]["37262"]["reasons"]
    assert "Sub-major options group 1" not in " ".join(evaluate_subjects(conn, student)["subjects"]["37335"]["reasons"])


def test_prerequisites_still_apply_to_sub_major_subjects(conn, student):
    choose_submajor(conn, student, INFOSEC)
    assert evaluate_subjects(conn, student)["subjects"]["41183"]["note"].startswith("Needs (")  # needs another security subject first
    complete(conn, student, "41182")
    assert status(conn, student, "41183") == "available"


def test_credit_point_conditions_still_apply_to_sub_major_subjects(conn, student):
    choose_submajor(conn, student, INFOSEC)  # 42036/42037 need 30 cp in another major, so use a degree-wide one instead
    assert evaluate_subjects(conn, student)["subjects"]["41181"]["status"] in ("blocked", "available")


# --- overlaps with the major ---------------------------------------------------------------------------------------------

def test_a_subject_in_both_the_major_and_the_sub_major_counts_once(conn):
    user = create_user(conn, "overlap@student.uni.edu.au", "Str0ng#Pass", AUTUMN)["id"]
    choose_major(conn, user, "MAJ03445")  # Networking and Cybersecurity: 48730 is core here
    choose_submajor(conn, user, INFOSEC)  # ... and an option of Information Security
    subjects = {s["code"]: s for s in catalogue.degree_subjects(conn, user)}
    assert subjects["48730"]["category"] == "major_core" and subjects["48730"]["overlaps_major"] is True
    group = next(c for k, c in categories(conn, user).items() if k.startswith("sub_choose_"))
    assert group["subject_count"] == 5  # six options, minus the one counted in the major
    assert subjects["41182"]["overlaps_major"] is False


def test_the_preview_flags_overlapping_subjects(conn):
    user = create_user(conn, "overlap@student.uni.edu.au", "Str0ng#Pass", AUTUMN)["id"]
    choose_major(conn, user, "MAJ03445")
    sub = preview(conn, user, INFOSEC)
    assert sub["overlap_count"] == 1
    flagged = [s["code"] for g in sub["all_groups"] for s in g["subjects"] if s["overlaps_major"]]
    assert flagged == ["48730"]


# --- swapping -----------------------------------------------------------------------------------------------------------

def test_swapping_is_always_allowed_and_nothing_done_is_deleted(conn):
    before = conn.execute("SELECT COUNT(*) FROM enrolments WHERE user_id = 1").fetchone()[0]
    result = choose_submajor(conn, 1, INFOSEC)  # the demo student has completed all of Innovation and Entrepreneurship
    assert result["swapped"] is True and result["no_longer_counted"] == 4
    assert conn.execute("SELECT COUNT(*) FROM enrolments WHERE user_id = 1").fetchone()[0] == before


def test_after_a_swap_the_old_sub_majors_subjects_stop_counting(conn):
    choose_submajor(conn, 1, INFOSEC)
    assert category_of(conn, 1, "48080") is None
    assert "sub_core" in categories(conn, 1) and categories(conn, 1)["sub_core"]["required_credit_points"] == 6


def test_the_preview_lists_what_would_stop_counting(conn):
    effect = impact(conn, 1, INFOSEC)
    assert [item["subject_code"] for item in effect["lost"]] == ["48080", "81529", "81546", "81547"]
    assert preview(conn, 1, INFOSEC)["impact"]["lost"]
    assert preview(conn, 1, INNOVATION)["is_current"] is True and not preview(conn, 1, INNOVATION)["impact"]["lost"]


def test_previewing_never_changes_anything(conn):
    preview(conn, 1, INFOSEC)
    assert catalogue.user_submajor(conn, 1)["code"] == INNOVATION


def test_swapping_removes_planned_subjects_that_are_not_in_the_new_sub_major(conn, student):
    choose_submajor(conn, student, INNOVATION)
    add_to_plan(conn, student, "48080", "Autumn 2027")
    add_to_plan(conn, student, "41039", "Autumn 2027")  # core for everyone
    result = choose_submajor(conn, student, INFOSEC)
    assert result["plan_removed"] == 1
    planned = {r[0] for r in conn.execute("SELECT subject_code FROM planned_subjects WHERE user_id = ?", (student,))}
    assert planned == {"41039"}


def test_a_major_swap_is_not_blocked_by_sub_major_subjects(conn, student):
    choose_submajor(conn, student, INFOSEC)
    complete(conn, student, "41181")  # counts in the sub-major whichever major is chosen
    choose_major(conn, student, "MAJ10053")


# --- the language sub-major --------------------------------------------------------------------------------------------------

def test_the_language_sub_major_needs_exactly_one_language(conn, student):
    with pytest.raises(SubmajorError, match="Choose one language program"):
        choose_submajor(conn, student, LOTE)
    with pytest.raises(SubmajorError, match="Choose one language program"):
        choose_submajor(conn, student, LOTE, "CBK99999")


def test_choosing_a_language_makes_only_that_languages_subjects_count(conn, student):
    choose_submajor(conn, student, LOTE, JAPANESE)
    sub = catalogue.user_submajor(conn, student)
    assert sub["language"] == JAPANESE and sub["language_name"] == "Japanese"
    assert category_of(conn, student, "97201") is not None  # Japanese Language and Culture 1
    assert category_of(conn, student, "97101") is None  # a Chinese subject
    assert evaluate_subjects(conn, student)["subjects"]["97101"]["note"] == "Not part of your Language Other Than English (LOTE) sub-major"


def test_languages_cannot_be_combined(conn, student):
    choose_submajor(conn, student, LOTE, JAPANESE)
    group = next(c for k, c in categories(conn, student).items() if k.startswith("sub_choose_"))
    assert group["required_credit_points"] == 24 and group["label"] == "Sub-major language: Japanese"
    assert group["subject_count"] == 10  # only the Japanese program


def test_changing_language_swaps_the_whole_program(conn, student):
    choose_submajor(conn, student, LOTE, JAPANESE)
    result = choose_submajor(conn, student, LOTE, CHINESE)
    assert result["swapped"] is True and result["language"] == "Chinese"
    assert category_of(conn, student, "97201") is None and category_of(conn, student, "97101") is not None


def test_the_same_language_again_is_refused(conn, student):
    choose_submajor(conn, student, LOTE, JAPANESE)
    with pytest.raises(SubmajorError, match="already your sub-major"):
        choose_submajor(conn, student, LOTE, JAPANESE)


def test_language_subjects_are_eight_credit_points_and_three_fill_the_group(conn, student):
    choose_submajor(conn, student, LOTE, JAPANESE)
    complete(conn, student, "97201", "97202", "97203")
    group = next(c for k, c in evaluate_subjects(conn, student)["categories"].items() if k.startswith("sub_choose_"))
    assert group["counted_cp"] == 24 and group["required_cp"] == 24
    assert evaluate_subjects(conn, student)["subjects"]["97204"]["reasons"] == ["Sub-major language: Japanese requirement already complete"]


def test_a_language_group_is_planned_in_eight_credit_point_steps(conn, student):
    choose_submajor(conn, student, LOTE, JAPANESE)
    section = next(s for s in get_plan(conn, student)["elective_sections"] if s["label"] == "Sub-major language: Japanese")
    assert (section["choose"], section["chosen"], section["need"]) == (3, 0, 3)  # three subjects of 8 cp


def test_language_prerequisites_are_not_enforced_because_they_are_not_verified(conn, student):
    choose_submajor(conn, student, LOTE, JAPANESE)
    assert conn.execute("SELECT prereq_status FROM subjects WHERE code = '97204'").fetchone()[0] == "unknown"
    assert status(conn, student, "97204") in ("available", "blocked")


# --- streams -----------------------------------------------------------------------------------------------------------------

def test_a_stream_is_not_a_subject_and_has_no_subjects_loaded_yet(conn):
    assert conn.execute("SELECT COUNT(*) FROM subjects WHERE code = 'CBK92069'").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM streams WHERE code = 'CBK92069'").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM stream_subjects WHERE stream_code = 'CBK92069'").fetchone()[0] == 0


def test_a_requirement_with_no_subjects_loaded_cannot_be_planned_and_says_so(conn, student):
    choose_submajor(conn, student, HUMANITARIAN)
    suggest_plan(conn, student)
    plan = get_plan(conn, student)
    assert plan["complete"] is False
    assert any("CBK92069" in note and "have not been loaded" in note for note in plan["notes"])
    assert plan["remaining_cp"] == 6  # exactly the stream's 6 cp


def test_the_stream_is_shown_with_its_note(conn):
    group = next(g for g in catalogue.get_submajor(conn, HUMANITARIAN)["all_groups"] if g["stream"])
    assert group["stream"]["code"] == "CBK92069" and "require verification" in group["stream"]["note"]


# --- full plans ---------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("major,submajor", [
    (ESD, OPTIMISATION), (ESD, INFOSEC), (ESD, INNOVATION), (ESD, STATS), ("MAJ02080", IOS),
])
def test_a_degree_with_each_sub_major_can_be_planned_in_full(conn, major, submajor):
    user = create_user(conn, "plan@student.uni.edu.au", "Str0ng#Pass", AUTUMN)["id"]
    choose_major(conn, user, major)
    choose_submajor(conn, user, submajor)
    added, unplaced = suggest_plan(conn, user)
    plan = get_plan(conn, user)
    assert unplaced == [] and plan["complete"] is True and plan["remaining_cp"] == 0
    assert all(s["load_cp"] <= 24 for s in plan["sessions"])


def test_a_sub_major_that_overlaps_the_major_is_flagged_not_double_counted(conn):
    user = create_user(conn, "plan@student.uni.edu.au", "Str0ng#Pass", AUTUMN)["id"]
    choose_major(conn, user, ESD)  # 41889 is an Enterprise Software Development option AND core in iOS Industry
    choose_submajor(conn, user, IOS)
    suggest_plan(conn, user)
    plan = get_plan(conn, user)
    assert plan["complete"] is False and plan["remaining_cp"] == 6  # the overlapping subject counts once, in the major
    assert any("Only 12 cp of subjects are available for Sub-major core" in note for note in plan["notes"])


def test_a_sub_major_whose_prerequisites_are_outside_the_degree_is_incomplete_not_faked(conn):
    user = create_user(conn, "plan@student.uni.edu.au", "Str0ng#Pass", AUTUMN)["id"]
    choose_major(conn, user, ESD)  # 37262 needs 37161 and 35005 needs 35007, neither of which is in this degree
    choose_submajor(conn, user, MATH_EXT)
    suggest_plan(conn, user)
    assert get_plan(conn, user)["complete"] is False


def test_a_degree_with_a_language_can_be_planned_in_full(conn):
    user = create_user(conn, "plan@student.uni.edu.au", "Str0ng#Pass", AUTUMN)["id"]
    choose_major(conn, user, ESD)
    choose_submajor(conn, user, LOTE, JAPANESE)
    added, unplaced = suggest_plan(conn, user)
    plan = get_plan(conn, user)
    assert unplaced == [] and plan["complete"] is True and plan["planned_cp"] == 192
    assert all(s["load_cp"] <= 24 for s in plan["sessions"])
    assert added == 30  # three 8 cp language subjects instead of four 6 cp ones


def test_the_completed_cp_are_never_counted_twice(conn):
    plan = get_plan(conn, 1)
    assert plan["completed_cp"] + plan["enrolled_cp"] + plan["planned_cp"] + plan["remaining_cp"] == 192
