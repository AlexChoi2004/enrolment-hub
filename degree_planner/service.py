"""Degree planner: plan subjects into future sessions and check the plan against the rules.

A plan is not an enrolment. The same checks run whether a student adds a subject by hand or asks
for a suggested plan, so a suggestion can never contain something a manual change would refuse.

Rules for placing a subject in a session:
  - it is not already completed, enrolled or planned
  - the session is inside the planning window and the subject is offered in it
  - the session stays within 24 credit points (counting what is already enrolled there)
  - every prerequisite is completed, or enrolled/planned in a strictly earlier session
  - the elective requirement is not exceeded (counting completed, enrolled and planned subjects)
"""
from collections import defaultdict

from enrolment.service import (
    CURRENT_SESSION,
    MAX_CP_PER_SESSION,
    offered_in,
    session_sort_key,
)
from subject_catalogue.service import ELECTIVE_CATEGORIES, ELECTIVE_CREDIT_POINTS

PLAN_SESSIONS = 10  # five years of Autumn and Spring sessions from the current one


class PlanError(Exception):
    """A plan change was refused. The message is safe to show to the student."""


def plan_sessions(current_session=CURRENT_SESSION, count=PLAN_SESSIONS):
    season, year = current_session.split()
    year = int(year)
    sessions = []
    for _ in range(count):
        sessions.append(f"{season} {year}")
        season, year = ("Spring", year) if season == "Autumn" else ("Autumn", year + 1)
    return sessions


# --- loading what the rules need ------------------------------------------------------------

def _state(conn, user_id):
    subjects = {
        r["code"]: dict(r)
        for r in conn.execute(
            "SELECT s.code, s.name, s.credit_points, s.category, s.sessions_offered,"
            " c.label AS category_label, c.required_credit_points AS required_cp, c.sort_order"
            " FROM subjects s JOIN requirement_categories c ON c.category = s.category"
        )
    }
    prereqs = defaultdict(list)
    for r in conn.execute("SELECT subject_code, prereq_code FROM prerequisites ORDER BY prereq_code"):
        prereqs[r["subject_code"]].append(r["prereq_code"])
    records = {
        r["subject_code"]: (r["status"], r["session_label"])
        for r in conn.execute(
            "SELECT subject_code, status, session_label FROM enrolments WHERE user_id = ?", (user_id,)
        )
    }
    plan = {
        r["subject_code"]: r["session_label"]
        for r in conn.execute(
            "SELECT subject_code, session_label FROM planned_subjects WHERE user_id = ?", (user_id,)
        )
    }
    return {"subjects": subjects, "prereqs": prereqs, "records": records, "plan": plan}


def _label(state, code):
    return f"{code} {state['subjects'][code]['name']}"


def _loads(state, ignore=None):
    loads = defaultdict(int)
    for code, (status, session) in state["records"].items():
        if status == "enrolled":
            loads[session] += state["subjects"][code]["credit_points"]
    for code, session in state["plan"].items():
        if code != ignore:
            loads[session] += state["subjects"][code]["credit_points"]
    return loads


def _category_counted(state, category, ignore=None):
    total = 0
    for code, subject in state["subjects"].items():
        if subject["category"] != category or code == ignore:
            continue
        if code in state["records"] or code in state["plan"]:
            total += subject["credit_points"]
    return total


def _check_placement(state, code, session, ignore_self=False):
    """Why this subject can't go in this session, or None if it can."""
    subject = state["subjects"].get(code)
    if subject is None:
        return "That subject does not exist."
    label = _label(state, code)
    record = state["records"].get(code)
    if record and record[0] == "completed":
        return f"You have already completed {label}."
    if record and record[0] == "enrolled":
        return f"You are already enrolled in {label}."
    if not ignore_self and code in state["plan"]:
        return f"{label} is already planned for {state['plan'][code]}."

    window = plan_sessions()
    if session not in window:
        return f"Choose a session from {window[0]} to {window[-1]}."
    if not offered_in(subject["sessions_offered"], session):
        return f"{label} is not offered in {session}."

    already = _loads(state, ignore=code if ignore_self else None)[session]
    if already + subject["credit_points"] > MAX_CP_PER_SESSION:
        return (
            f"{session} would go over {MAX_CP_PER_SESSION} credit points "
            f"({already} already enrolled or planned)."
        )

    missing = []
    for p in state["prereqs"][code]:
        if state["records"].get(p, (None, None))[0] == "completed":
            continue
        when = None
        if state["records"].get(p, (None, None))[0] == "enrolled":
            when = state["records"][p][1]
        elif p in state["plan"] and p != code:
            when = state["plan"][p]
        if when is None or session_sort_key(when) >= session_sort_key(session):
            missing.append(p)
    if missing:
        names = ", ".join(_label(state, p) for p in missing)
        return f"Needs {names} completed or planned in an earlier session."

    if subject["category"] in ELECTIVE_CATEGORIES:
        counted = _category_counted(state, subject["category"], ignore=code if ignore_self else None)
        if counted + subject["credit_points"] > subject["required_cp"]:
            return (
                f"{subject['category_label']} requirement would be exceeded "
                f"({counted} of {subject['required_cp']} credit points already completed, enrolled or planned)."
            )
    return None


def _dependents_problem(state, code, new_session=None):
    """A planned subject that needs `code` earlier than it would now be (or at all)."""
    for other, other_session in sorted(state["plan"].items()):
        if other != code and code in state["prereqs"][other]:
            if new_session is None or session_sort_key(new_session) >= session_sort_key(other_session):
                return f"{_label(state, other)} is planned for {other_session} and needs {_label(state, code)} first."
    return None


def _valid_sessions(state, code, ignore_self=False, exclude=None):
    return [
        s for s in plan_sessions()
        if s != exclude and _check_placement(state, code, s, ignore_self=ignore_self) is None
    ]


# --- reading the plan (Read) ----------------------------------------------------------------------

def get_plan(conn, user_id):
    state = _state(conn, user_id)
    subjects = state["subjects"]
    loads = _loads(state)

    sessions = []
    problems = []
    for label in plan_sessions():
        enrolled = [
            {"code": c, "name": subjects[c]["name"], "credit_points": subjects[c]["credit_points"],
             "category_label": subjects[c]["category_label"]}
            for c, (status, session) in sorted(state["records"].items())
            if status == "enrolled" and session == label
        ]
        planned = []
        for code, session in sorted(state["plan"].items()):
            if session != label:
                continue
            problem = _check_placement(state, code, session, ignore_self=True)
            if problem:
                problems.append(f"{_label(state, code)} in {session}: {problem}")
            planned.append({
                "code": code,
                "name": subjects[code]["name"],
                "credit_points": subjects[code]["credit_points"],
                "category_label": subjects[code]["category_label"],
                "problem": problem,
                "move_sessions": _valid_sessions(state, code, ignore_self=True, exclude=session),
            })
        sessions.append({"label": label, "load_cp": loads[label], "enrolled": enrolled, "planned": planned})

    outstanding, elective_needs, elective_sections = [], [], []
    categories = {}
    for subject in subjects.values():
        categories.setdefault(subject["category"], subject)
    for category, sample in sorted(categories.items(), key=lambda kv: kv[1]["sort_order"]):
        members = sorted((s for s in subjects.values() if s["category"] == category), key=lambda s: s["code"])
        untaken = [s for s in members if s["code"] not in state["records"] and s["code"] not in state["plan"]]
        if category in ELECTIVE_CATEGORIES:
            counted = _category_counted(state, category)
            choose = sample["required_cp"] // ELECTIVE_CREDIT_POINTS
            chosen = counted // ELECTIVE_CREDIT_POINTS
            need = max(0, (sample["required_cp"] - counted) // ELECTIVE_CREDIT_POINTS)
            section = {
                "label": sample["category_label"],
                "choose": choose,  # how many the degree asks for
                "chosen": chosen,  # completed, enrolled or planned so far
                "need": need,
                "complete": need == 0,
                "candidates": [
                    {"code": s["code"], "name": s["name"], "credit_points": s["credit_points"],
                     "sessions": _valid_sessions(state, s["code"])}
                    for s in sorted(untaken, key=lambda s: s["name"].lower())
                ] if need else [],
            }
            elective_sections.append(section)  # always shown, so a finished section stays visible
            if need:
                elective_needs.append(section)
            elif counted > sample["required_cp"]:
                problems.append(f"Your plan has more {sample['category_label'].lower()} than the degree needs.")
        else:
            for s in untaken:
                outstanding.append({
                    "code": s["code"], "name": s["name"], "credit_points": s["credit_points"],
                    "category_label": s["category_label"], "sessions": _valid_sessions(state, s["code"]),
                })
    outstanding.sort(key=lambda o: (o["category_label"], o["name"].lower()))

    def cp(status):
        return sum(subjects[c]["credit_points"] for c, (st, _) in state["records"].items() if st == status)

    planned_cp = sum(subjects[c]["credit_points"] for c in state["plan"])
    degree_total = sum(
        s["required_cp"] for s in categories.values()
    )
    remaining = 0
    for category, sample in categories.items():
        remaining += max(0, sample["required_cp"] - _category_counted(state, category))
    return {
        "sessions": sessions,
        "outstanding": outstanding,
        "elective_needs": elective_needs,
        "elective_sections": elective_sections,
        "problems": problems,
        "completed_cp": cp("completed"),
        "enrolled_cp": cp("enrolled"),
        "planned_cp": planned_cp,
        "remaining_cp": remaining,
        "degree_total_cp": degree_total,
        "has_plan": bool(state["plan"]),
        "complete": remaining == 0 and not problems,
    }


# --- changing the plan (Create, Update, Delete) ------------------------------------------------------

def add_to_plan(conn, user_id, subject_code, session_label):
    state = _state(conn, user_id)
    problem = _check_placement(state, subject_code, session_label)
    if problem:
        raise PlanError(problem)
    conn.execute(
        "INSERT INTO planned_subjects (user_id, subject_code, session_label) VALUES (?, ?, ?)",
        (user_id, subject_code, session_label),
    )
    conn.commit()
    return _label(state, subject_code)


def move_in_plan(conn, user_id, subject_code, new_session):
    state = _state(conn, user_id)
    if subject_code not in state["subjects"]:
        raise PlanError("That subject does not exist.")
    label = _label(state, subject_code)
    if subject_code not in state["plan"]:
        raise PlanError(f"{label} is not in your plan.")
    if state["plan"][subject_code] == new_session:
        raise PlanError(f"{label} is already planned for {new_session}.")
    problem = _check_placement(state, subject_code, new_session, ignore_self=True)
    if problem:
        raise PlanError(problem)
    problem = _dependents_problem(state, subject_code, new_session)
    if problem:
        raise PlanError(f"Can't move {label} to {new_session}: {problem}")
    conn.execute(
        "UPDATE planned_subjects SET session_label = ? WHERE user_id = ? AND subject_code = ?",
        (new_session, user_id, subject_code),
    )
    conn.commit()
    return label


def remove_from_plan(conn, user_id, subject_code):
    state = _state(conn, user_id)
    if subject_code not in state["subjects"]:
        raise PlanError("That subject does not exist.")
    label = _label(state, subject_code)
    if subject_code not in state["plan"]:
        raise PlanError(f"{label} is not in your plan.")
    problem = _dependents_problem(state, subject_code)
    if problem:
        raise PlanError(f"Can't remove {label}: {problem}")
    conn.execute(
        "DELETE FROM planned_subjects WHERE user_id = ? AND subject_code = ?", (user_id, subject_code)
    )
    conn.commit()
    return label


def clear_plan(conn, user_id):
    cur = conn.execute("DELETE FROM planned_subjects WHERE user_id = ?", (user_id,))
    conn.commit()
    return cur.rowcount


# --- suggesting a plan ------------------------------------------------------------------------------------

def _depths(state):
    """How many subjects are stacked on top of each one (longest chain of dependents)."""
    dependents = defaultdict(list)
    for code, needed in state["prereqs"].items():
        for p in needed:
            dependents[p].append(code)
    memo = {}

    def depth(code):
        if code not in memo:
            memo[code] = 1 + max((depth(d) for d in dependents[code]), default=0)
        return memo[code]

    return {code: depth(code) for code in state["subjects"]}


def suggest_plan(conn, user_id):
    """Fill the plan with whatever is still needed, session by session, using the placement rules.

    Required subjects go first (the longest prerequisite chains earliest), then electives fill
    the room that is left. Existing planned subjects are never moved. Returns (added, unplaced).
    """
    state = _state(conn, user_id)
    depths = _depths(state)
    subjects = state["subjects"]

    def untaken(code):
        return code not in state["records"] and code not in state["plan"]

    def pick_required(session):
        options = [
            s for s in subjects.values()
            if s["category"] not in ELECTIVE_CATEGORIES and untaken(s["code"])
            and _check_placement(state, s["code"], session) is None
        ]
        if not options:
            return None
        options.sort(key=lambda s: (-depths[s["code"]], 0 if s["sessions_offered"] != "Both" else 1, s["code"]))
        return options[0]["code"]

    def pick_elective(session):
        for category in sorted(ELECTIVE_CATEGORIES, key=lambda c: next(
                s["sort_order"] for s in subjects.values() if s["category"] == c)):
            sample = next(s for s in subjects.values() if s["category"] == category)
            if _category_counted(state, category) >= sample["required_cp"]:
                continue
            options = [
                s for s in subjects.values()
                if s["category"] == category and untaken(s["code"])
                and _check_placement(state, s["code"], session) is None
            ]
            if options:
                options.sort(key=lambda s: (len(state["prereqs"][s["code"]]),
                                            0 if s["sessions_offered"] != "Both" else 1, s["name"].lower()))
                return options[0]["code"]
        return None

    added = []
    for session in plan_sessions():
        while True:
            code = pick_required(session) or pick_elective(session)
            if code is None:
                break
            state["plan"][code] = session
            added.append((code, session))

    conn.executemany(
        "INSERT INTO planned_subjects (user_id, subject_code, session_label) VALUES (?, ?, ?)",
        [(user_id, code, session) for code, session in added],
    )
    conn.commit()

    unplaced = [
        _label(state, s["code"]) for s in subjects.values()
        if s["category"] not in ELECTIVE_CATEGORIES and untaken(s["code"])
    ]
    return len(added), sorted(unplaced)