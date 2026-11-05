"""Swap advice: should this student change major, sub-major or electives, and what would it cost them?

Everything here is worked out by plain rules from the student's own record, so it is repeatable and checkable. The AI
features only EXPLAIN these results and answer "what if" questions; they never decide them, and they can never make
the swap: the student always confirms it themselves.

What is calculated:
  * how far through the degree (and the major) the student is;
  * which subjects they have done or are doing would carry over, and how many credit points would stop counting;
  * the extra credit points and sessions that would be needed to graduate, and the projected graduation session;
  * a verdict: good to switch, costs time, or think carefully.
Extra subjects mean extra tuition (HECS or otherwise); no dollar figure is shown because fees vary and the app does not
know them. Nothing here changes any data: each assessment is worked out on a copy that is rolled back.
"""
import math

from degree_planner.service import DEGREE_CREDIT_POINTS, get_plan
from enrolment.service import current_session_of, next_session
from subject_catalogue.service import degree_subjects, get_major, get_submajor

SESSION_CP = 24
KINDS = ("major", "submajor", "electives")
TIERS = {"good": "Good to switch", "costs_time": "Possible, but it costs time", "think": "Think carefully"}
# Tier rules (credit points that would stop counting). Shown to the student, so they can see why.
GOOD_MAX_EXTRA_CP = 6  # one subject
THINK_EXTRA_SESSIONS = 2  # about a year
THINK_EXTRA_CP = 36  # six subjects
THINK_MAJOR_PROGRESS = 0.75  # this far through the major...
THINK_MAX_CARRY_SHARE = 0.25  # ...with almost nothing carrying over


def session_after(label, steps):
    for _ in range(steps):
        label = next_session(label)
    return label


def _counts(conn, user_id):
    """What counts towards the degree right now: credit points done, in progress, and within the major."""
    in_degree = {s["code"]: s for s in degree_subjects(conn, user_id) if s["in_degree"]}
    status = {r["subject_code"]: r["status"] for r in conn.execute(
        "SELECT subject_code, status FROM enrolments WHERE user_id = ?", (user_id,))}
    done = {c: status[c] for c in in_degree if status.get(c) in ("completed", "enrolled")}
    cp = {c: in_degree[c]["credit_points"] for c in done}
    return {
        "counted": done, "cp": cp,
        "completed_cp": sum(cp[c] for c in done if done[c] == "completed"),
        "enrolled_cp": sum(cp[c] for c in done if done[c] == "enrolled"),
        "major_cp": sum(cp[c] for c in done if in_degree[c]["category"] in ("major_core", "major_elective")),
        "electives_cp": sum(cp[c] for c in done if in_degree[c]["category"] == "general_elective"),
    }


def _apply(conn, user_id, kind, code, language):
    if kind == "major":
        conn.execute("UPDATE users SET major_code = ? WHERE id = ?", (code, user_id))
    elif kind == "submajor":
        conn.execute("UPDATE users SET submajor_code = ?, submajor_language = ?, general_electives = 0 WHERE id = ?",
                     (code, language, user_id))
    else:
        conn.execute("UPDATE users SET submajor_code = NULL, submajor_language = NULL, general_electives = 1 WHERE id = ?",
                     (user_id,))


def _after(conn, user_id, kind, code, language, elective_codes=()):
    """The same numbers if the swap were made, worked out on a copy that is rolled back (nothing is saved).

    elective_codes are subjects the student would choose to count as general electives; they only take effect on the
    general electives path. Also returns the credit points of that block already used (done, in progress or planned)."""
    _apply(conn, user_id, kind, code, language)
    try:
        on_path = conn.execute("SELECT general_electives FROM users WHERE id = ?", (user_id,)).fetchone()[0]
        if on_path:
            for c in elective_codes:
                conn.execute("INSERT OR IGNORE INTO elective_credits (user_id, subject_code) VALUES (?, ?)", (user_id, c))
        counts = _counts(conn, user_id)
        planned_electives = sum(r[0] for r in conn.execute(
            "SELECT s.credit_points FROM planned_subjects p JOIN subjects s ON s.code = p.subject_code"
            " WHERE p.user_id = ? AND s.category = 'general_elective'", (user_id,))) if on_path else 0
        return counts, get_plan(conn, user_id)["notes"], bool(on_path), planned_electives
    finally:
        conn.rollback()


def _target_name(conn, kind, code, language):
    if kind == "electives":
        return "General electives"
    if kind == "major":
        return (get_major(conn, code) or {}).get("name", code)
    sub = get_submajor(conn, code, language) or {}
    return sub.get("name", code) + (f" ({sub['language_name']})" if sub.get("language_name") else "")


class ElectiveChoiceError(ValueError):
    """The subjects chosen to count as general electives are not allowed. The message is safe to show."""


def validate_electives(conn, user_id, kind, code, language, codes):
    """The subjects the student may count as general electives for this swap, or an ElectiveChoiceError."""
    codes = list(dict.fromkeys(codes))
    if not codes:
        return []
    advice = assess(conn, user_id, kind, code, language)
    offer = advice["electives_offer"] if advice else None
    if offer is None:
        raise ElectiveChoiceError("There is no room for general electives with this choice.")
    eligible = {e["code"]: e for e in offer["eligible"]}
    unknown = [c for c in codes if c not in eligible]
    if unknown:
        raise ElectiveChoiceError("These can't be counted as general electives: " + ", ".join(unknown) + ".")
    total = sum(eligible[c]["credit_points"] for c in codes)
    if total > offer["space_cp"]:
        raise ElectiveChoiceError(f"Only {offer['space_cp']} credit points of general electives are free; you chose {total}.")
    return codes


def assess(conn, user_id, kind, code=None, language=None, elective_codes=()):
    """The facts and the verdict for one possible swap. Returns None when the target does not exist.

    elective_codes: subjects the student would count as general electives (already checked by validate_electives)."""
    if kind not in KINDS:
        raise ValueError("kind must be major, submajor or electives")
    if kind == "major" and get_major(conn, code) is None:
        return None
    if kind == "submajor" and get_submajor(conn, code) is None:
        return None
    mine = conn.execute("SELECT major_code, submajor_code, general_electives FROM users WHERE id = ?", (user_id,)).fetchone()
    first_choice = (mine["major_code"] is None) if kind == "major" else (mine["submajor_code"] is None and not mine["general_electives"])
    before = _counts(conn, user_id)
    after, notes, on_electives_path, planned_electives = _after(conn, user_id, kind, code, language)
    offer = None
    lost_before = [c for c in before["counted"] if c not in after["counted"]]
    if on_electives_path and lost_before:
        space = max(0, 24 - after["electives_cp"] - planned_electives)
        if space > 0:
            names = {r["code"]: r["name"] for r in conn.execute("SELECT code, name FROM subjects")}
            offer = {
                "space_cp": space,
                "eligible": [{"code": c, "name": names[c], "credit_points": before["cp"][c], "status": before["counted"][c]}
                             for c in sorted(lost_before)],
            }
            offer["max_cp"] = min(space, sum(e["credit_points"] for e in offer["eligible"]))
    if elective_codes:  # the numbers the student would really get, with their choices applied
        after, notes, _, _ = _after(conn, user_id, kind, code, language, elective_codes)
    current = current_session_of(conn, user_id)

    counted_before = before["completed_cp"] + before["enrolled_cp"]
    counted_after = after["completed_cp"] + after["enrolled_cp"]
    carried = [c for c in before["counted"] if c in after["counted"]]
    lost = [c for c in before["counted"] if c not in after["counted"]]
    carried_cp = sum(before["cp"][c] for c in carried)
    lost_cp = sum(before["cp"][c] for c in lost)
    extra_cp = max(0, counted_before - counted_after)
    carry_share = carried_cp / counted_before if counted_before else 1.0
    major_progress = before["major_cp"] / 48

    sessions_before = math.ceil(max(0, DEGREE_CREDIT_POINTS - counted_before) / SESSION_CP)
    sessions_after = math.ceil(max(0, DEGREE_CREDIT_POINTS - counted_after) / SESSION_CP)
    extra_sessions = max(0, sessions_after - sessions_before)
    extra_subjects = math.ceil(extra_cp / 6)

    reasons, triggers = [], []  # reasons: the facts behind the verdict; triggers: the RULES that decided it
    if extra_cp <= GOOD_MAX_EXTRA_CP:
        tier = "good"
        if extra_cp == 0:
            reasons.append("Everything you have done still counts, so nothing is lost.")
        else:
            reasons.append(f"Only {extra_cp} credit points would stop counting: about one extra subject.")
    else:
        tier = "costs_time"
        reasons.append(f"{extra_cp} credit points you have done would stop counting.")
        if extra_sessions >= THINK_EXTRA_SESSIONS or extra_cp >= THINK_EXTRA_CP:
            tier = "think"
            reasons.append(f"That is about {extra_subjects} extra subjects and {extra_sessions} extra session(s) of study.")
            if extra_sessions >= THINK_EXTRA_SESSIONS:
                triggers.append(f"it needs {THINK_EXTRA_SESSIONS} or more extra sessions")
            if extra_cp >= THINK_EXTRA_CP:
                triggers.append(f"{THINK_EXTRA_CP} or more credit points would stop counting")
        if kind == "major" and major_progress >= THINK_MAJOR_PROGRESS and carry_share < THINK_MAX_CARRY_SHARE:
            tier = "think"
            reasons.append(
                f"You are {round(major_progress * 100)}% through your current major and only {round(carry_share * 100)}% "
                "of what you have done carries over."
            )
            triggers.append(f"you are {round(THINK_MAJOR_PROGRESS * 100)}% or more through your major with under "
                            f"{round(THINK_MAX_CARRY_SHARE * 100)}% carrying over")
    unfinishable = any("can't be planned" in n or "Only " in n for n in notes)
    if unfinishable:
        tier = tier if tier != "good" else "costs_time"
        reasons.append("Some of its requirements can't be completed from your current degree (see the notes below).")
    # The one-line "why this verdict": the rule that applied. It says what the numbers below do NOT: which line they crossed.
    if tier == "good":
        why = ("Because everything you have done still counts." if extra_cp == 0
               else f"Because at most one subject ({GOOD_MAX_EXTRA_CP} credit points) would stop counting.")
    elif tier == "costs_time" and unfinishable and extra_cp <= GOOD_MAX_EXTRA_CP:
        why = "Because some of its requirements can't be completed from your current degree (see the notes below)."
    elif tier == "costs_time":
        why = (f"Because more than one subject ({GOOD_MAX_EXTRA_CP} credit points) would stop counting, but not enough to be a serious setback "
               f"({THINK_EXTRA_SESSIONS} extra sessions or {THINK_EXTRA_CP} credit points).")
    else:
        why = "Because " + " and ".join(triggers) + "."

    needs_ack = tier != "good"
    ack = (f"I understand this adds about {extra_subjects} extra subject(s) and moves my graduation back by "
           f"{extra_sessions} session(s), which means extra tuition.") if needs_ack else ""
    return {
        "kind": kind, "first_choice": first_choice,  # a first choice has nothing to swap from, so no advice is shown for it
        "target": _target_name(conn, kind, code, language), "tier": tier, "label": TIERS[tier],
        "progress": {
            "counted_cp": counted_before, "degree_cp": DEGREE_CREDIT_POINTS,
            "percent": round(100 * counted_before / DEGREE_CREDIT_POINTS),
            "major_cp": before["major_cp"], "major_percent": round(100 * major_progress),
        },
        "carried_cp": carried_cp, "lost_cp": lost_cp, "extra_cp": extra_cp, "extra_subjects": extra_subjects,
        "extra_sessions": extra_sessions, "carry_percent": round(100 * carry_share),
        "lost": [{"code": c, "credit_points": before["cp"][c], "status": before["counted"][c]} for c in sorted(lost)],
        "graduate_before": session_after(current, sessions_before),
        "graduate_after": session_after(current, sessions_after),
        "electives_offer": offer, "counted_as_electives": list(elective_codes),
        "reasons": reasons, "why": why, "notes": notes, "needs_ack": needs_ack, "ack_text": ack,
        "tuition_note": "Extra subjects mean extra tuition (HECS or otherwise). The app does not know your fees, so no dollar amount is shown.",
        "rules": [
            f"Good to switch: {GOOD_MAX_EXTRA_CP} credit points (one subject) or fewer would stop counting.",
            f"Think carefully: {THINK_EXTRA_SESSIONS} or more extra sessions, {THINK_EXTRA_CP} or more credit points lost, or "
            f"{round(THINK_MAJOR_PROGRESS * 100)}% or more through your major with under {round(THINK_MAX_CARRY_SHARE * 100)}% carrying over.",
            "Anything in between: possible, but it costs time.",
        ],
    }
