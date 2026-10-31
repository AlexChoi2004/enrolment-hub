"""Timetable pages. A student can only ever change their own class choices."""
from flask import Blueprint, abort, flash, g, make_response, redirect, render_template, request, url_for

from enrolment.service import open_sessions
from shared import security
from shared.db import get_db
from subject_catalogue.service import is_valid_code
from timetable import service

bp = Blueprint("timetable", __name__, template_folder="templates", url_prefix="/timetable")


@bp.get("")
@security.login_required
def page():
    session_label = service.valid_session(request.args.get("session", ""))
    response = make_response(
        render_template(
            "timetable/index.html",
            timetable=service.get_timetable(get_db(), g.user["id"], session_label),
            sessions=open_sessions(),
            current=session_label,
        )
    )
    response.headers["Cache-Control"] = "no-store"  # personal data must not be cached
    return response


# --- changes: POST only, CSRF protected, always on the signed-in student's own choices --------------

def _back(session_label):
    return redirect(url_for("timetable.page", session=service.valid_session(session_label)), code=303)


@bp.post("/choose")
@security.login_required
def choose():
    security.require_csrf()
    code = request.form.get("subject_code", "")
    if not is_valid_code(code):
        abort(400)
    try:
        class_id = int(request.form.get("class_id", ""))
    except ValueError:
        abort(400)
    session_label = request.form.get("session_label", "")
    try:
        result = service.choose_class(get_db(), g.user["id"], code, class_id)
    except service.TimetableError as exc:
        flash(str(exc), "error")
    else:
        verb = "Changed" if result["updated"] else "Chose"
        flash(f"{verb} the class for {result['label']}: {result['class']}.", "success")
        if result["clashes"]:
            flash("Warning: it clashes with " + "; ".join(result["clashes"]) + ". Both are shown in red.", "warning")
        session_label = result["session"]
    return _back(session_label)


@bp.post("/drop/<code>/<component>")
@security.login_required
def drop(code, component):
    security.require_csrf()
    if not is_valid_code(code) or component not in service.COMPONENTS:
        abort(400)
    session_label = request.form.get("session_label", "")
    try:
        result = service.drop_class(get_db(), g.user["id"], code, component)
    except service.TimetableError as exc:
        flash(str(exc), "error")
    else:
        flash(f"Dropped the {result['class'].lower()} for {result['label']}.", "success")
        session_label = result["session"]
    return _back(session_label)