"""Degree planner pages. A student can only ever change their own plan."""
from flask import Blueprint, abort, flash, g, make_response, redirect, render_template, request, url_for

from degree_planner import service
from shared import security
from shared.db import get_db
from subject_catalogue.service import is_valid_code

bp = Blueprint("planner", __name__, template_folder="templates", url_prefix="/planner")


@bp.get("")
@security.login_required
def page():
    response = make_response(
        render_template(
            "planner/index.html",
            plan=service.get_plan(get_db(), g.user["id"]),
            max_cp=service.MAX_CP_PER_SESSION,
        )
    )
    response.headers["Cache-Control"] = "no-store"  # personal data must not be cached
    return response


# --- plan changes: POST only, CSRF protected, always on the signed-in student's own plan -------------

def _back():
    return redirect(url_for("planner.page"), code=303)


def _run(action, success_message):
    try:
        label = action()
    except service.PlanError as exc:
        flash(str(exc), "error")
    else:
        flash(success_message.format(label=label), "success")
    return _back()


@bp.post("/add")
@security.login_required
def add():
    security.require_csrf()
    code = request.form.get("subject_code", "")
    if not is_valid_code(code):
        abort(400)
    session_label = request.form.get("session_label", "")
    return _run(
        lambda: service.add_to_plan(get_db(), g.user["id"], code, session_label),
        "Added {label} to your plan for " + session_label + ".",
    )


@bp.post("/move/<code>")
@security.login_required
def move(code):
    security.require_csrf()
    if not is_valid_code(code):
        abort(400)
    session_label = request.form.get("session_label", "")
    return _run(
        lambda: service.move_in_plan(get_db(), g.user["id"], code, session_label),
        "Moved {label} to " + session_label + ".",
    )


@bp.post("/remove/<code>")
@security.login_required
def remove(code):
    security.require_csrf()
    if not is_valid_code(code):
        abort(400)
    return _run(
        lambda: service.remove_from_plan(get_db(), g.user["id"], code),
        "Removed {label} from your plan.",
    )


@bp.post("/suggest")
@security.login_required
def suggest():
    security.require_csrf()
    added, unplaced = service.suggest_plan(get_db(), g.user["id"])
    if added:
        flash(f"Added {added} subject{'' if added == 1 else 's'} to your plan.", "success")
    else:
        flash("Nothing to add: your plan already covers what the degree needs.", "success")
    if unplaced:
        flash("Could not place: " + ", ".join(unplaced) + ".", "error")
    return _back()


@bp.post("/clear")
@security.login_required
def clear():
    security.require_csrf()
    removed = service.clear_plan(get_db(), g.user["id"])
    flash(f"Cleared your plan ({removed} planned subject{'' if removed == 1 else 's'}).", "success")
    return _back()