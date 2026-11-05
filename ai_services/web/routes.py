"""AI mode: the on/off switch, the question box and the swap advisor. Everything here is for the signed-in student only."""
import re

from flask import Blueprint, abort, current_app, flash, g, make_response, redirect, render_template, request, url_for

from ai_services import llm
from ai_services.web.format import answer_blocks, tool_label
from ai_services.ai_mode.agent import is_personal, run_agent
from ai_services.rag.answer import ask
from ai_services.multi_agent.swap_agents import advise as run_advisor
from ai_services.rag.retrieve import MAX_QUESTION
from features.advisor.service import KINDS
from shared import security
from ai_services.tools.registry import LANGUAGE, MAJOR_OR_SUB
from shared.db import get_db

bp = Blueprint("ai", __name__, template_folder="templates", url_prefix="/ai")
bp.add_app_template_filter(answer_blocks, "answer_blocks")
bp.add_app_template_filter(tool_label, "tool_label")


def _private(html, status=200):
    response = make_response(html, status)
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.post("/mode")
@security.login_required
def mode():
    """Switch AI mode on or off for the signed-in student only. It is off until they turn it on."""
    security.require_csrf()
    conn = get_db()
    conn.execute("UPDATE users SET ai_mode = 1 - ai_mode WHERE id = ?", (g.user["id"],))
    conn.commit()
    now_on = conn.execute("SELECT ai_mode FROM users WHERE id = ?", (g.user["id"],)).fetchone()[0]
    flash("AI mode is on." if now_on else "AI mode is off.", "success")
    return redirect(security.safe_next(request.form.get("next"), url_for("planner.page")), code=303)


def _within_limit(conn, user_id):
    limit = current_app.config.get("AI_QUESTIONS_PER_HOUR", 30)
    used = conn.execute(
        "SELECT COUNT(*) FROM ai_usage WHERE user_id = ? AND asked_at > strftime('%Y-%m-%dT%H:%M:%S', 'now', '-1 hour')",
        (user_id,),
    ).fetchone()[0]
    return used < limit


@bp.post("/ask")
@security.login_required
def ask_question():
    security.require_csrf()
    if not g.user["ai_mode"]:
        abort(403)  # AI mode is off: nothing is sent to any model
    question = request.form.get("question", "")
    if not isinstance(question, str) or not question.strip():
        return _private(render_template("ai/_message.html", message="Type a question first."), 400)
    if len(question) > MAX_QUESTION:
        return _private(render_template("ai/_message.html", message=f"Please keep your question under {MAX_QUESTION} characters."), 400)
    conn = get_db()
    if not _within_limit(conn, g.user["id"]):
        return _private(render_template("ai/_message.html", message="You have asked a lot of questions in the last hour. Please try again later."), 429)
    conn.execute("INSERT INTO ai_usage (user_id) VALUES (?)", (g.user["id"],))
    conn.commit()
    try:
        model = llm.get_llm(current_app.config)
    except llm.LLMError:
        model = None
    result = None
    if is_personal(question):  # about the student themselves: let the model look things up with the read-only tools
        result = run_agent(conn, g.user["id"], question, model)
        if result["status"] == "no_tool":
            result = None  # it could not use a tool: fall back to the written sources
    if result is None:
        result = ask(conn, question, model)
    template = "ai/_result.html" if request.headers.get("HX-Request") else "ai/answer.html"
    return _private(render_template(template, result=result, question=question.strip()))


@bp.post("/advise")
@security.login_required
def advise():
    """Explain one possible swap with the three roles (Analyst, Advisor, Checker). It never makes the swap."""
    security.require_csrf()
    if not g.user["ai_mode"]:
        abort(403)
    kind = request.form.get("kind", "")
    code = (request.form.get("code") or "").strip() or None
    language = (request.form.get("language") or "").strip() or None
    if kind not in KINDS or (code and not re.match(MAJOR_OR_SUB, code)) or (language and not re.match(LANGUAGE, language)):
        abort(400)
    conn = get_db()
    if not _within_limit(conn, g.user["id"]):
        return _private(render_template("ai/_message.html", message="You have asked a lot of questions in the last hour. Please try again later."), 429)
    conn.execute("INSERT INTO ai_usage (user_id) VALUES (?)", (g.user["id"],))
    conn.commit()
    try:
        model = llm.get_llm(current_app.config)
    except llm.LLMError:
        model = None
    result = run_advisor(conn, g.user["id"], kind, code, language, model)
    return _private(render_template("ai/_advisor.html", result=result))
