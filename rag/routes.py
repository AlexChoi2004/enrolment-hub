"""AI mode: the on/off switch and the question box. Everything here is for the signed-in student only."""
from flask import Blueprint, abort, current_app, flash, g, make_response, redirect, render_template, request, url_for

from rag import llm
from rag.answer import ask
from rag.retrieve import MAX_QUESTION
from shared import security
from shared.db import get_db

bp = Blueprint("ai", __name__, template_folder="templates", url_prefix="/ai")


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
        return _private(render_template("rag/_message.html", message="Type a question first."), 400)
    if len(question) > MAX_QUESTION:
        return _private(render_template("rag/_message.html", message=f"Please keep your question under {MAX_QUESTION} characters."), 400)
    conn = get_db()
    if not _within_limit(conn, g.user["id"]):
        return _private(render_template("rag/_message.html", message="You have asked a lot of questions in the last hour. Please try again later."), 429)
    conn.execute("INSERT INTO ai_usage (user_id) VALUES (?)", (g.user["id"],))
    conn.commit()
    try:
        model = llm.get_llm(current_app.config)
    except llm.LLMError:
        model = None
    result = ask(conn, question, model)
    template = "rag/_answer.html" if request.headers.get("HX-Request") else "rag/answer.html"
    return _private(render_template(template, result=result, question=question.strip()))
