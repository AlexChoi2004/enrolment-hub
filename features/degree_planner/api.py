"""The planner board's data and its one write: JSON for the React page. Signed-in student only, CSRF protected, never cached."""
import re

from flask import Blueprint, g, jsonify, make_response, render_template, request

from features.degree_planner.board import PlanError, build_board, move_card
from features.subject_catalogue.service import is_valid_code
from shared import security
from shared.db import get_db

bp = Blueprint("planner_api", __name__, template_folder="templates")
SESSION_LABEL = re.compile(r"^(Autumn|Spring) 20\d\d$")


def _json(body, status=200):
    response = make_response(jsonify(body), status)
    response.headers["Cache-Control"] = "no-store"
    return response


def _bad(message, status=400):
    return _json({"ok": False, "error": message}, status)


@bp.get("/planner/board")
@security.login_required
def page():
    board = build_board(get_db(), g.user["id"])
    response = make_response(render_template("planner/board.html", board=board))
    response.headers["Cache-Control"] = "no-store"  # personal data
    return response


@bp.get("/api/planner/board")
@security.login_required
def board():
    return _json(build_board(get_db(), g.user["id"]))


@bp.post("/api/planner/move")
@security.login_required
def move():
    """Move one subject: {"code": "48024", "to": "Autumn 2028"} places or moves it; "to": null removes it from the plan."""
    if not security.csrf_valid():
        return _bad("Your session has expired. Reload the page and try again.")
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or set(body) != {"code", "to"}:
        return _bad('Send JSON like {"code": "48024", "to": "Autumn 2028"}.')
    code, to = body["code"], body["to"]
    if not isinstance(code, str) or not is_valid_code(code):
        return _bad("That is not a subject code.")
    if to is not None and (not isinstance(to, str) or not SESSION_LABEL.match(to)):
        return _bad("That is not a session, for example Autumn 2028.")
    conn = get_db()
    try:
        message = move_card(conn, g.user["id"], code, to)
    except PlanError as exc:  # the planner's own reason, unchanged
        return _json({"ok": False, "error": str(exc)}, 422)
    return _json({"ok": True, "message": message, "board": build_board(conn, g.user["id"])})
