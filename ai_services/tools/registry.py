"""The tools the AI features may call. Every one is READ-ONLY and scoped to the signed-in student.

Design rules (they are tested):
  * the student is chosen by the SERVER from the session, never by the model: no tool takes a user id, and an unknown
    argument is refused, so a model (or a prompt injection) cannot ask about anyone else;
  * every argument is validated against a schema before anything runs (type, pattern, allowed values, length);
  * no tool changes any data. They return facts; the student makes every change themselves in the normal pages;
  * answers come from the same functions the pages use, so the AI can never disagree with the app;
  * unconfirmed assessment information stays "not enough context" (it comes through subject_catalogue.assessments).
The same registry feeds the AI mode, the RAG answers and the MCP server, so there is one set of tools to check.
"""
import re

from features.advisor.service import KINDS, assess
from features.degree_planner.service import check_placement, get_plan
from features.enrolment.service import current_session_of, evaluate_subjects, open_sessions
from features.subject_catalogue.assessments import ai_context
from features.subject_catalogue.service import get_subject, prerequisite_lines
from features.timetable.service import get_timetable
from features.transcript.service import transcript
from features.workload.service import context_for_ai, load_context

SUBJECT_CODE = r"^[A-Za-z0-9]{3,10}$"
SESSION = r"^(Autumn|Spring) 20[0-9]{2}$"
MAJOR_OR_SUB = r"^(MAJ|SMJ)[0-9]{5}$"
LANGUAGE = r"^CBK[0-9]{5}$"
MAX_QUERY = 60


class ToolError(Exception):
    """The call was refused. The message is safe to show (and to give back to the model)."""


def _param(kind, description, pattern=None, enum=None, required=True, max_length=None):
    spec = {"type": kind, "description": description}
    if pattern:
        spec["pattern"] = pattern
    if enum:
        spec["enum"] = list(enum)
    if max_length:
        spec["maxLength"] = max_length
    return {"spec": spec, "required": required}


def _validate(params, args):
    if not isinstance(args, dict):
        raise ToolError("Arguments must be an object.")
    unknown = set(args) - set(params)
    if unknown:
        raise ToolError("Unknown argument: " + ", ".join(sorted(unknown)))  # includes any attempt to name a student
    clean = {}
    for name, p in params.items():
        spec = p["spec"]
        if name not in args or args[name] is None:
            if p["required"]:
                raise ToolError(f"Missing required argument: {name}")
            continue
        value = args[name]
        if not isinstance(value, str):
            raise ToolError(f"{name} must be text.")
        if len(value) > spec.get("maxLength", 40):
            raise ToolError(f"{name} is too long.")
        if "pattern" in spec and not re.match(spec["pattern"], value):
            raise ToolError(f"{name} is not in the expected format.")
        if "enum" in spec and value not in spec["enum"]:
            raise ToolError(f"{name} must be one of: " + ", ".join(spec["enum"]))
        clean[name] = value
    return clean


# --- the tools --------------------------------------------------------------------------------------------------------------

def search_subjects(conn, user_id, query):
    """Find subject codes from part of a name or code (at most 10)."""
    q = query.strip()
    if not q:
        raise ToolError("query must not be empty.")
    like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    rows = conn.execute(
        "SELECT code, name, credit_points FROM subjects WHERE name LIKE ? ESCAPE '\\' OR code LIKE ? ESCAPE '\\'"
        " ORDER BY code LIMIT 10", (like, like),
    ).fetchall()
    return {"matches": [dict(r) for r in rows]}


def get_subject_info(conn, user_id, code):
    """Everything known about one subject, and where this student stands with it."""
    subject = get_subject(conn, code)
    if subject is None:
        raise ToolError(f"There is no subject {code}.")
    mine = evaluate_subjects(conn, user_id)["subjects"].get(code, {})
    context = ai_context(conn, code)
    return {
        "code": subject["code"], "name": subject["name"], "credit_points": subject["credit_points"],
        "sessions_offered": subject["sessions_offered"], "description": subject["summary"] or None,
        "assessment_load": subject["assessment_load"]["score"],
        "assessment_load_note": "The app's own estimate of how heavy the assessment is, not a UTS rating.",
        "assessments_known": context["assessments_known"], "assessment_summary": context["text"],
        "prerequisites": prerequisite_lines(conn, code),
        "prerequisites_how_to_read": "Every line must be met; inside a line, 'or' means any one of the alternatives will do.",
        "prerequisite_note": subject["prerequisite_note"],
        "my_status": mine.get("status"), "my_note": mine.get("note"), "needs_retake": bool(mine.get("retake")),
    }


def check_prerequisites(conn, user_id, code):
    """Can this student enrol in the subject, and if not, why not?"""
    mine = evaluate_subjects(conn, user_id)["subjects"].get(code)
    if mine is None:
        raise ToolError(f"There is no subject {code}.")
    return {"code": code, "status": mine["status"], "reasons": mine["reasons"], "note": mine["note"],
            "needs_retake": bool(mine["retake"])}


def list_offerings(conn, user_id, code):
    """The sessions a subject runs in, and which of them this student can enrol in right now."""
    subject = get_subject(conn, code)
    if subject is None:
        raise ToolError(f"There is no subject {code}.")
    current = current_session_of(conn, user_id)
    open_now = open_sessions(current)
    offered = subject["sessions_offered"]
    return {"code": code, "sessions_offered": offered, "current_session": current,
            "open_for_enrolment": [s for s in open_now if offered == "Both" or s.startswith(offered)]}


def check_plan_placement(conn, user_id, code, session):
    """Would the planner accept this subject in this session? Nothing is added."""
    return {"code": code, "session": session, **check_placement(conn, user_id, code, session)}


def get_my_plan(conn, user_id):
    """A summary of this student's degree plan: period, counts, each session with its workload, retakes and notes."""
    plan = get_plan(conn, user_id)
    return {
        "period": plan["period"], "counts": plan["counts"], "remaining_cp": plan["remaining_cp"],
        "complete": plan["complete"], "needs_major": plan["needs_major"], "needs_submajor": plan["needs_submajor"],
        "notes": plan["notes"],
        "sessions": [
            {"label": s["label"], "load_cp": s["load_cp"],
             "enrolled": [f"{i['code']} {i['name']}" for i in s["enrolled"]],
             "planned": [f"{i['code']} {i['name']}" + (f" (problem: {i['problem']})" if i.get("problem") else "") for i in s["planned"]],
             "workload": {"verdict": s["workload"]["label"], "warnings": s["workload"]["warnings"], "positives": s["workload"]["positives"]},
             "suggested_moves": [m["reason"] + f" (move {m['code']} to {m['to']})" for m in s["suggestions"]]}
            for s in plan["sessions"] if s["enrolled"] or s["planned"]
        ],
        "failed_to_retake": [f"{r['code']} {r['name']} ({r['stage']})" for r in plan["retakes"]],
        "needs_rescheduling": [f"{p['code']} {p['name']}: {p['problem']}" for p in plan["past_plans"]],
    }


def get_session_workload(conn, user_id, session):
    """The workload verdict for one session, with its caveats."""
    plan = get_plan(conn, user_id)
    for s in plan["sessions"]:
        if s["label"] == session:
            codes = [i["code"] for i in s["enrolled"] + s["planned"]]
            return {"session": session, "text": context_for_ai(load_context(conn), session, codes)}
    raise ToolError(f"{session} is not in your planning window.")


def find_clash_free_classes(conn, user_id, code, session):
    """The tutorial and workshop times for an enrolled subject that do not clash with the classes already chosen."""
    if session not in open_sessions(current_session_of(conn, user_id)):
        raise ToolError(f"{session} is not a session you can have a timetable for right now.")
    card = next((c for c in get_timetable(conn, user_id, session)["subjects"] if c["code"] == code), None)
    if card is None:
        raise ToolError(f"You are not enrolled in {code} in {session}.")
    return {"code": code, "session": session, "components": [
        {"component": c["label"], "chosen": c["chosen"]["when"] if c["chosen"] else None,
         "clash_free": [{"id": o["id"], "when": o["when"]} for o in c["options"] if not o["clash"]]}
        for c in card["components"]
    ]}


def get_my_results(conn, user_id):
    """This student's results, newest session first (simulated data)."""
    result = transcript(conn, user_id, newest_first=True)
    return {
        "data_note": "Simulated demonstration data, not genuine UTS academic records.",
        "passed_credit_points": result["passed_cp"], "failed_attempts": result["failed_attempts"],
        "in_progress": result["in_progress"], "needs_retake": result["retakes"],
        "sessions": [{"session": g["label"], "results": [
            f"{r['code']} {r['name']}: {r['outcome']}" + (f" ({r['mark']}, {r['grade']})" if r["mark"] is not None else "")
            + f", attempt {r['attempt']}" for r in g["rows"]]} for g in result["groups"]],
    }


def get_swap_advice(conn, user_id, kind, code=None, language=None):
    """Advice on changing major, sub-major or electives: what carries over, the delay and a verdict. Changes nothing."""
    if kind != "electives" and not code:
        raise ToolError("code is required for a major or sub-major.")
    if kind == "major" and not str(code).startswith("MAJ") or kind == "submajor" and not str(code).startswith("SMJ"):
        raise ToolError("That code does not match the kind.")
    advice = assess(conn, user_id, kind, code, language)
    if advice is None:
        raise ToolError("That major or sub-major does not exist.")
    out = {k: advice[k] for k in ("target", "label", "first_choice", "why", "reasons", "progress", "carried_cp", "carry_percent", "lost_cp",
                                   "extra_subjects", "extra_sessions", "graduate_before", "graduate_after",
                                   "notes", "tuition_note", "needs_ack", "electives_offer")}
    if advice["first_choice"]:
        out["note"] = "This would be the student's first choice, so there is nothing to swap from and nothing to lose."
    return out


# --- the registry ------------------------------------------------------------------------------------------------------------

TOOLS = {
    "search_subjects": {
        "description": "Find subject codes from part of a subject name or code.",
        "params": {"query": _param("string", "Part of a subject name or code, for example 'Programming 2'.", required=True, max_length=MAX_QUERY)},
        "func": search_subjects},
    "get_subject_info": {
        "description": "Details of one subject (description, credit points, sessions, assessment load, assessments, prerequisites) and where this student stands with it.",
        "params": {"code": _param("string", "Subject code, for example 41039.", SUBJECT_CODE)}, "func": get_subject_info},
    "check_prerequisites": {
        "description": "Whether this student can enrol in a subject, and the reasons if not (including failed prerequisites).",
        "params": {"code": _param("string", "Subject code.", SUBJECT_CODE)}, "func": check_prerequisites},
    "list_offerings": {
        "description": "Which sessions a subject runs in and which are open for this student to enrol in now.",
        "params": {"code": _param("string", "Subject code.", SUBJECT_CODE)}, "func": list_offerings},
    "check_plan_placement": {
        "description": "Whether the degree planner would accept a subject in a given session. Adds nothing.",
        "params": {"code": _param("string", "Subject code.", SUBJECT_CODE),
                   "session": _param("string", "Session, for example 'Autumn 2028'.", SESSION)}, "func": check_plan_placement},
    "get_my_plan": {
        "description": "A summary of this student's degree plan: current period, counts, remaining credit points, each session with its workload, subjects to retake and plans needing rescheduling.",
        "params": {}, "func": get_my_plan},
    "get_session_workload": {
        "description": "The workload verdict (light, balanced, heavy, too heavy) for one session with its concerns and caveats.",
        "params": {"session": _param("string", "Session, for example 'Autumn 2027'.", SESSION)}, "func": get_session_workload},
    "find_clash_free_classes": {
        "description": "Tutorial and workshop times for a subject the student is enrolled in that do not clash with their chosen classes.",
        "params": {"code": _param("string", "Subject code.", SUBJECT_CODE), "session": _param("string", "Session, for example 'Autumn 2027'.", SESSION)},
        "func": find_clash_free_classes},
    "get_my_results": {
        "description": "This student's results (simulated): passed credit points, each attempt with mark and grade, subjects needing a retake.",
        "params": {}, "func": get_my_results},
    "get_swap_advice": {
        "description": "Advice on changing major, sub-major or electives: progress, what carries over, extra credit points and sessions, projected graduation and a verdict. Changes nothing; the student confirms any swap themselves.",
        "params": {"kind": _param("string", "What to change.", enum=KINDS),
                   "code": _param("string", "Major (MAJ...) or sub-major (SMJ...) code. Not needed for electives.", MAJOR_OR_SUB, required=False),
                   "language": _param("string", "Language program code (CBK...) for the language sub-major.", LANGUAGE, required=False)},
        "func": get_swap_advice},
}


def tool_specs():
    """The tools as plain descriptions with JSON schemas, for the AI mode and the MCP server."""
    specs = []
    for name, tool in TOOLS.items():
        props = {n: dict(p["spec"]) for n, p in tool["params"].items()}
        specs.append({
            "name": name, "description": tool["description"],
            "input_schema": {"type": "object", "properties": props,
                             "required": [n for n, p in tool["params"].items() if p["required"]],
                             "additionalProperties": False},
        })
    return specs


def call_tool(conn, user_id, name, args=None):
    """Run one tool for one student. Never raises for a bad call: returns {"ok": False, "error": ...} instead."""
    tool = TOOLS.get(name)
    if tool is None:
        return {"ok": False, "error": f"Unknown tool: {name}"}
    try:
        clean = _validate(tool["params"], {} if args is None else args)
        return {"ok": True, "data": tool["func"](conn, user_id, **clean)}
    except ToolError as exc:
        return {"ok": False, "error": str(exc)}
