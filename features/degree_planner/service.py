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

from features.enrolment.results import failed_subjects
from features.enrolment.service import (
    CURRENT_SESSION,
    current_session_of,
    semester_number,
    study_year,
    MAX_CP_PER_SESSION,
    offered_in,
    session_sort_key,
)
from features.workload.service import context_for_ai, load_context, session_workload, suggest_moves
from features.subject_catalogue.service import (
    DEGREE_CREDIT_POINTS,
    ELECTIVE_CREDIT_POINTS,
    MAJOR_CREDIT_POINTS,
    SUBMAJOR_CREDIT_POINTS,
    degree_categories,
    degree_subjects,
    group_text,
    is_choose_category,
    load_credit_requirements,
    load_prerequisites,
    uses_general_electives,
    user_major,
    user_submajor,
)

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
    """What the rules need, for THIS student's degree.

    `subjects` holds every subject; those outside the student's degree (a major they did not choose)
    have in_degree False and no category, so they can't be planned and count towards nothing.
    """
    sections = {c["category"]: c for c in degree_categories(conn, user_id)}
    subjects = {}
    for s in degree_subjects(conn, user_id):
        section = sections.get(s["category"])
        subjects[s["code"]] = {
            "code": s["code"], "name": s["name"], "credit_points": s["credit_points"],
            "category": s["category"], "sessions_offered": s["sessions_offered"],
            "in_degree": s["in_degree"], "stored_category": s["stored_category"],
            "category_label": section["label"] if section else None,
            "required_cp": section["required_credit_points"] if section else 0,
            "sort_order": section["sort_order"] if section else 99,
        }
    major = user_major(conn, user_id)
    submajor = user_submajor(conn, user_id)
    membership = (
        {r[0] for r in conn.execute("SELECT subject_code FROM major_subjects")},
        {r[0] for r in conn.execute("SELECT subject_code FROM submajor_group_subjects")},
    )
    rules = defaultdict(list, load_prerequisites(conn))  # {subject: [group, ...]}
    prereqs = defaultdict(list)  # every prerequisite code of a subject, flat (for "who depends on this")
    for subject, groups in rules.items():
        prereqs[subject] = [c for g in groups for c in g["codes"]]
    major_members = defaultdict(set)
    for r in conn.execute("SELECT major_code, subject_code FROM major_subjects"):
        major_members[r["major_code"]].add(r["subject_code"])
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
        if subjects.get(r["subject_code"], {}).get("in_degree")  # ignore anything left over from another major
    }
    return {
        "current": current_session_of(conn, user_id),
        "subjects": subjects, "prereqs": prereqs, "rules": rules, "records": records, "plan": plan, "major": major,
        "submajor": submajor, "electives": uses_general_electives(conn, user_id), "membership": membership,
        "failed": failed_subjects(conn, user_id),  # failed and not yet passed: they need a retake
        "degree_categories": list(sections.values()),
        "credit_rules": load_credit_requirements(conn), "major_members": major_members,
    }


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
    if not subject["in_degree"]:
        in_major, in_sub = code in state["membership"][0], code in state["membership"][1]
        major, sub = state["major"], state["submajor"]
        if subject["stored_category"] in ("general_elective", "td_elective"):
            if sub is not None:
                return f"{label} is not part of your degree: you chose the {sub['name']} sub-major instead of general electives."
            return f"{label} is a general elective. Choose general electives or a sub-major first."
        if in_sub and not in_major and sub is None and state["electives"]:
            return f"{label} is not part of your degree: you chose general electives instead of a sub-major."
        if in_major and major is None:
            return f"{label} is part of a major. Choose a major first."
        if in_sub and not in_major and sub is None:
            return f"{label} is part of a sub-major. Choose a sub-major first."
        if in_major and in_sub and sub is not None:
            return f"{label} is not part of your {major['name']} major or your {sub['name']} sub-major."
        if in_sub and not in_major:
            return f"{label} is not part of your {sub['name']} sub-major."
        if major is not None:
            return f"{label} is not part of your {major['name']} major."
        return f"{label} is not part of your degree."
    record = state["records"].get(code)
    if record and record[0] == "completed":
        return f"You have already completed {label}."
    if record and record[0] == "enrolled":
        return f"You are already enrolled in {label}."
    if not ignore_self and code in state["plan"]:
        return f"{label} is already planned for {state['plan'][code]}."

    window = plan_sessions(state["current"])
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

    def satisfied_by(p, concurrent):
        rec = state["records"].get(p)
        if rec and rec[0] == "completed":
            return True
        when = rec[1] if rec and rec[0] == "enrolled" else (state["plan"].get(p) if p != code else None)
        if when is None:
            return False
        earlier, here = session_sort_key(when), session_sort_key(session)
        return earlier <= here if concurrent else earlier < here  # a corequisite may be in the same session

    names = {c: s_["name"] + (" (failed: retake it first)" if c in state["failed"] else "")
             for c, s_ in state["subjects"].items()}
    missing = [g for g in state["rules"].get(code, []) if not any(satisfied_by(p, g["concurrent"]) for p in g["codes"])]
    if missing:
        return f"Needs {', '.join(group_text(names, g) for g in missing)} completed or planned in an earlier session."
    for req in state["credit_rules"].get(code, []):
        have = _major_credit(state, req["major_code"], session)
        if have < req["min_cp"]:
            return (
                f"Needs {req['min_cp']} credit points completed in {req['major_name']} "
                f"({have} completed, or planned in earlier sessions)."
            )

    if is_choose_category(subject["category"]):
        counted = _category_counted(state, subject["category"], ignore=code if ignore_self else None)
        if counted + subject["credit_points"] > subject["required_cp"]:
            return (
                f"{subject['category_label']} requirement would be exceeded "
                f"({counted} of {subject['required_cp']} credit points already completed, enrolled or planned)."
            )
    return None


def _major_credit(state, major_code, session):
    """Credit points in a major that are completed, or enrolled/planned in a strictly earlier session."""
    total = 0
    if major_code is None:  # a condition on the whole degree
        codes = [c for c, s in state["subjects"].items() if s["in_degree"]]
    else:
        codes = state["major_members"].get(major_code, ())
    for code in codes:
        cp = state["subjects"][code]["credit_points"]
        rec = state["records"].get(code)
        if rec and rec[0] == "completed":
            total += cp
            continue
        when = rec[1] if rec else state["plan"].get(code)
        if when is not None and session_sort_key(when) < session_sort_key(session):
            total += cp
    return total


def _dependents_problem(state, code, new_session=None):
    """A planned subject that would stop being valid if `code` were removed (new_session None) or moved."""
    for other, other_session in sorted(state["plan"].items()):
        if other == code or code not in state["prereqs"][other]:
            continue
        trial = dict(state)
        trial["plan"] = dict(state["plan"])
        if new_session is None:
            trial["plan"].pop(code, None)
        else:
            trial["plan"][code] = new_session
        if _check_placement(trial, other, other_session, ignore_self=True) is not None:
            return f"{_label(state, other)} is planned for {other_session} and needs {_label(state, code)} first."
    return None


def _valid_sessions(state, code, ignore_self=False, exclude=None):
    return [
        s for s in plan_sessions(state["current"])
        if s != exclude and _check_placement(state, code, s, ignore_self=ignore_self) is None
    ]


# --- reading the plan (Read) ----------------------------------------------------------------------

def check_placement(conn, user_id, subject_code, session_label):
    """Would this subject be allowed in this session of the plan? Changes nothing. Returns {allowed, reason}."""
    state = _state(conn, user_id)
    if subject_code not in state["subjects"]:
        return {"allowed": False, "reason": "That subject does not exist."}
    problem = _check_placement(state, subject_code, session_label, ignore_self=subject_code in state["plan"])
    return {"allowed": problem is None, "reason": problem}


def get_plan(conn, user_id):
    state = _state(conn, user_id)
    subjects = state["subjects"]
    loads = _loads(state)

    sessions = []
    problems = []
    for label in plan_sessions(state["current"]):
        enrolled = [
            {"code": c, "name": subjects[c]["name"], "credit_points": subjects[c]["credit_points"],
             "category_label": subjects[c]["category_label"] or "Doesn't count towards your degree"}
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
                "move_sessions": [
                    s for s in _valid_sessions(state, code, ignore_self=True, exclude=session)
                    if _dependents_problem(state, code, s) is None  # nothing planned later needs it earlier
                ],
            })
        sessions.append({"label": label, "load_cp": loads[label], "enrolled": enrolled, "planned": planned})

    # Workload for every session, with moves that would lighten a heavy one (rules in code, never the AI).
    wl = load_context(conn)
    codes_by_session = {s["label"]: [i["code"] for i in s["enrolled"] + s["planned"]] for s in sessions}
    for s in sessions:
        s["workload"] = session_workload(wl, codes_by_session[s["label"]])
        s["suggestions"] = suggest_moves(
            wl, codes_by_session, s["label"], [(p["code"], p["move_sessions"]) for p in s["planned"]]
        )

    outstanding, elective_needs, elective_sections = [], [], []
    categories = {}
    for subject in subjects.values():
        if subject["in_degree"]:
            categories.setdefault(subject["category"], subject)
    for category, sample in sorted(categories.items(), key=lambda kv: kv[1]["sort_order"]):
        members = sorted((s for s in subjects.values() if s["category"] == category), key=lambda s: s["code"])
        untaken = [s for s in members if s["code"] not in state["records"] and s["code"] not in state["plan"]]
        if is_choose_category(category):
            counted = _category_counted(state, category)
            unit = min((s["credit_points"] for s in members), default=ELECTIVE_CREDIT_POINTS)  # 6, or 8 for languages
            choose = sample["required_cp"] // unit
            chosen = counted // unit
            need = max(0, (sample["required_cp"] - counted) // unit)
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
                    "retake": s["code"] in state["failed"], "last_result": state["failed"].get(s["code"]),
                })
    outstanding.sort(key=lambda o: (o["category_label"], o["name"].lower()))

    # Failed subjects that still need a retake, and where each one stands.
    retakes = []
    for code, f in sorted(state["failed"].items()):
        if code not in subjects or not subjects[code]["in_degree"]:
            continue
        record = state["records"].get(code)
        stage = "enrolled" if record and record[0] == "enrolled" else "planned" if code in state["plan"] else "needs"
        retakes.append({
            "code": code, "name": subjects[code]["name"], "credit_points": subjects[code]["credit_points"],
            "stage": stage, "session": (record[1] if stage == "enrolled" else state["plan"].get(code)),
            "attempts": f["attempts"], "last_session": f["last_session"], "last_mark": f["last_mark"],
            "sessions": _valid_sessions(state, code) if stage == "needs" else [],
        })
    past_plans = []
    for code, session in sorted(state["plan"].items()):
        if session_sort_key(session) < session_sort_key(state["current"]):
            past_plans.append({
                "code": code, "name": subjects[code]["name"], "credit_points": subjects[code]["credit_points"],
                "session": session,
                "problem": f"Planned for {session}, which has passed. Move it to a future session or remove it.",
                "move_sessions": _valid_sessions(state, code, ignore_self=True),
            })
    counts = {
        "past": len(past_plans),
        "completed": sum(1 for c, (st, _) in state["records"].items() if st == "completed" and subjects[c]["in_degree"]),
        "enrolled": sum(1 for c, (st, _) in state["records"].items() if st == "enrolled" and subjects[c]["in_degree"]),
        "planned": len(state["plan"]),
        "blocked": sum(1 for s in sessions for p in s["planned"] if p["problem"]),
        "retake": sum(1 for r in retakes if r["stage"] == "needs"),
    }

    def cp(status):  # only what counts towards this degree, so nothing is counted twice or outside the degree
        return sum(subjects[c]["credit_points"] for c, (st, _) in state["records"].items()
                   if st == status and subjects[c]["in_degree"])

    extra_cp = sum(subjects[c]["credit_points"] for c, (st, _) in state["records"].items() if not subjects[c]["in_degree"])

    planned_cp = sum(subjects[c]["credit_points"] for c in state["plan"])
    remaining = 0
    notes = []
    for c in state["degree_categories"]:  # every requirement, even one whose subjects have not been loaded yet
        remaining += max(0, c["required_credit_points"] - _category_counted(state, c["category"]))
        available = sum(s["credit_points"] for s in subjects.values() if s["category"] == c["category"])
        if available == 0:
            notes.append(f"The subjects for {c['label']} have not been loaded, so this can't be planned yet.")
        elif available < c["required_credit_points"]:
            notes.append(
                f"Only {available} cp of subjects are available for {c['label']} (it needs {c['required_credit_points']} cp) "
                "because some of its subjects also count in your major. Check the course rules for a substitute."
            )
    if state["major"] is None:
        remaining += MAJOR_CREDIT_POINTS  # the major's 48 cp can't be planned until a major is chosen
    if state["submajor"] is None and not state["electives"]:
        remaining += SUBMAJOR_CREDIT_POINTS  # nor the 24 cp block: a sub-major or general electives, not chosen yet
    if state["submajor"] is not None and state["submajor"]["needs_language"]:
        remaining += SUBMAJOR_CREDIT_POINTS
        notes.append("Choose a language program for your language sub-major.")
    commenced = conn.execute("SELECT commencement_session FROM users WHERE id = ?", (user_id,)).fetchone()[0]
    return {
        "period": {"label": state["current"], "year": study_year(commenced, state["current"]),
                   "semester": semester_number(state["current"])},
        "sessions": sessions,
        "past_plans": past_plans,
        "outstanding": outstanding,
        "elective_needs": elective_needs,
        "elective_sections": elective_sections,
        "problems": problems,
        "retakes": retakes,
        "counts": counts,
        "extra_cp": extra_cp,  # done, but not counting towards this degree (for example after changing major)
        "completed_cp": cp("completed"),
        "enrolled_cp": cp("enrolled"),
        "planned_cp": planned_cp,
        "remaining_cp": remaining,
        "degree_total_cp": DEGREE_CREDIT_POINTS,
        "has_plan": bool(state["plan"]),
        "major": state["major"],
        "needs_major": state["major"] is None,
        "submajor": state["submajor"],
        "needs_submajor": state["submajor"] is None and not state["electives"],  # neither alternative chosen yet
        "uses_electives": state["electives"],
        "notes": notes,
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
    stale = [c for c, s in state["plan"].items() if session_sort_key(s) < session_sort_key(state["current"])]
    for code in stale:  # planned for a session that has passed: plan them again from here
        conn.execute("DELETE FROM planned_subjects WHERE user_id = ? AND subject_code = ?", (user_id, code))
        del state["plan"][code]
    depths = _depths(state)
    subjects = state["subjects"]

    def untaken(code):
        return code not in state["records"] and code not in state["plan"]

    def pick_required(session):
        options = [
            s for s in subjects.values()
            if s["in_degree"] and not is_choose_category(s["category"]) and untaken(s["code"])
            and _check_placement(state, s["code"], session) is None
        ]
        if not options:
            return None
        options.sort(key=lambda s: (-depths[s["code"]], 0 if s["sessions_offered"] != "Both" else 1, s["code"]))
        return options[0]["code"]

    def pick_elective(session):
        present = {s["category"] for s in subjects.values() if s["in_degree"] and is_choose_category(s["category"])}
        for category in sorted(present, key=lambda c: next(
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
    for session in plan_sessions(state["current"]):
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
        if s["in_degree"] and not is_choose_category(s["category"]) and untaken(s["code"])
    ]
    return len(added), sorted(unplaced)
