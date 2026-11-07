"""The dashboard: where the student stands at a glance.

Everything here comes from what the planner, the eligibility rules and the catalogue already decide: this module gathers and
shapes it, and adds no rules of its own. The result is plain data (numbers, labels and links) with a fixed shape, because a
React and TypeScript page reads it. That shape is a contract: frontend/src/contract.ts describes it, and a test fails if the two
drift apart.
"""
from features.advisor.service import SESSION_CP, room_in_current_session, session_after, sessions_after_current
from features.degree_planner.service import get_plan
from features.enrolment.service import current_session_of
from features.subject_catalogue.service import degree_categories, degree_subjects, user_major, user_submajor

MAX_SESSIONS = 6  # sessions shown: the current one, then the next ones that have something in them
MAX_STEPS = 5
PENDING = {  # shown until the student chooses, so the bars still add up to the whole degree
    "major_pending": ("Major (not chosen yet)", 48),
    "submajor_pending": ("Sub-major or electives (not chosen yet)", 24),
}


def _categories(conn, user_id, plan):
    """Credit points per requirement: done, in progress and planned, each capped so a category never shows more than it needs."""
    status = {r["subject_code"]: r["status"] for r in conn.execute("SELECT subject_code, status FROM enrolments WHERE user_id = ?", (user_id,))}
    planned = {r["subject_code"] for r in conn.execute("SELECT subject_code FROM planned_subjects WHERE user_id = ?", (user_id,))}
    totals = {}
    for s in degree_subjects(conn, user_id):
        if not s["in_degree"]:
            continue
        entry = totals.setdefault(s["category"], {"completed": 0, "enrolled": 0, "planned": 0})
        state = status.get(s["code"])
        if state == "completed":
            entry["completed"] += s["credit_points"]
        elif state == "enrolled":
            entry["enrolled"] += s["credit_points"]
        elif s["code"] in planned:
            entry["planned"] += s["credit_points"]
    out = []
    for c in degree_categories(conn, user_id):
        required, t = c["required_credit_points"], totals.get(c["category"], {"completed": 0, "enrolled": 0, "planned": 0})
        done = min(t["completed"], required)
        doing = min(t["enrolled"], required - done)
        later = min(t["planned"], required - done - doing)
        out.append({"key": c["category"], "label": c["label"], "required_cp": required, "completed_cp": done, "enrolled_cp": doing,
                    "planned_cp": later, "pending": False})
    if plan["needs_major"]:
        out.append({"key": "major_pending", "label": PENDING["major_pending"][0], "required_cp": 48, "completed_cp": 0, "enrolled_cp": 0,
                    "planned_cp": 0, "pending": True})
    if plan["needs_submajor"]:
        out.append({"key": "submajor_pending", "label": PENDING["submajor_pending"][0], "required_cp": 24, "completed_cp": 0, "enrolled_cp": 0,
                    "planned_cp": 0, "pending": True})
    return out


def _graduation(conn, user_id, plan, current):
    """The session the degree finishes in if every session from now is filled to 24 credit points (the advisor's own rule)."""
    counted = plan["completed_cp"] + plan["enrolled_cp"]
    remaining = max(0, plan["degree_total_cp"] - counted)
    after_current = sessions_after_current(counted, room_in_current_session(conn, user_id, current))
    return {"session": session_after(current, after_current), "sessions_left": after_current, "remaining_cp": remaining,
            "finished": plan["degree_total_cp"] - counted <= 0}


def _sessions(plan, current):
    out = []
    for s in plan["sessions"]:
        if s["label"] != current and not (s["enrolled"] or s["planned"]):
            continue
        out.append({"label": s["label"], "current": s["label"] == current, "load_cp": s["load_cp"], "enrolled": len(s["enrolled"]),
                    "planned": len(s["planned"]), "workload": s["workload"]["status"], "workload_label": s["workload"]["label"]})
    return out[:MAX_SESSIONS]


def _next_steps(plan, sessions, current, room_now):
    steps = []
    if plan["needs_major"]:
        steps.append({"kind": "setup", "severity": "warning", "text": "Choose your major, so its 48 credit points are in your plan.", "href": "/major"})
    if plan["needs_submajor"]:
        steps.append({"kind": "setup", "severity": "warning", "text": "Choose a sub-major or general electives for the last 24 credit points.", "href": "/submajor"})
    for r in plan["retakes"]:
        steps.append({"kind": "retake", "severity": "warning", "text": f"{r['code']} {r['name']} was failed: retake it before anything that needs it.", "href": "/planner"})
    problems = [p for s in plan["sessions"] for p in s["planned"] if p.get("problem")]
    for p in problems[:2]:
        steps.append({"kind": "blocked", "severity": "warning", "text": f"{p['code']} {p['name']} is planned but blocked: {p['problem']}", "href": "/planner"})
    if plan["past_plans"]:
        n = len(plan["past_plans"])
        steps.append({"kind": "reschedule", "severity": "warning", "text": f"{n} planned subject{'s' if n != 1 else ''} need{'' if n != 1 else 's'} rescheduling: their session has passed.", "href": "/planner"})
    for s in sessions:
        if s["workload"] in ("heavy", "too_heavy"):
            steps.append({"kind": "workload", "severity": "info", "text": f"{s['label']} looks {s['workload_label'].lower()}: have a look at its workload in the planner.", "href": "/planner"})
            break
    if room_now > 0 and not plan["needs_major"]:
        steps.append({"kind": "enrol", "severity": "info", "text": f"You have {room_now} credit points of room in {current}: enrol in a subject.", "href": "/subjects"})
    elif room_now > 0:
        steps.append({"kind": "enrol", "severity": "info", "text": f"You can enrol in core subjects now ({room_now} credit points of room in {current}).", "href": "/subjects"})
    if not plan["has_plan"] and not plan["needs_major"] and plan["remaining_cp"] > 0:
        steps.append({"kind": "plan", "severity": "info", "text": "Use Suggest a plan to lay out your remaining sessions.", "href": "/planner"})
    return steps[:MAX_STEPS]


def build_dashboard(conn, user_id):
    """The whole dashboard as plain data, for one student."""
    plan = get_plan(conn, user_id)
    current = current_session_of(conn, user_id)
    sessions = _sessions(plan, current)
    in_current = next((s["load_cp"] for s in sessions if s["current"]), 0)
    major, sub = user_major(conn, user_id), user_submajor(conn, user_id)
    name = conn.execute("SELECT display_name FROM users WHERE id = ?", (user_id,)).fetchone()[0]
    pathway = {"kind": "submajor", "name": sub["name"]} if sub else ({"kind": "electives", "name": "General electives"} if plan["uses_electives"]
                                                                       else {"kind": None, "name": None})
    return {
        "student": {"display_name": name},
        "period": {"label": plan["period"]["label"], "year": plan["period"]["year"], "semester": plan["period"]["semester"]},
        "degree": {"total_cp": plan["degree_total_cp"], "completed_cp": plan["completed_cp"], "enrolled_cp": plan["enrolled_cp"],
                   "planned_cp": plan["planned_cp"], "remaining_cp": plan["remaining_cp"]},
        "counts": {"completed": plan["counts"]["completed"], "enrolled": plan["counts"]["enrolled"], "planned": plan["counts"]["planned"],
                   "retake": plan["counts"]["retake"], "blocked": plan["counts"]["blocked"]},
        "choices": {"major": {"name": major["name"] if major else None}, "pathway": pathway},
        "categories": _categories(conn, user_id, plan),
        "graduation": _graduation(conn, user_id, plan, current),
        "sessions": sessions,
        "next_steps": _next_steps(plan, sessions, current, max(0, SESSION_CP - in_current)),
    }
