"""Timetable pages. A student can only ever change their own class choices."""
from flask import Blueprint, Response, abort, flash, g, make_response, redirect, render_template, request, url_for

from features.enrolment.service import current_session_of, open_sessions
from shared import security
from shared.db import get_db
from features.subject_catalogue.service import is_valid_code
from features.timetable import ical, service
from features.workload.service import load_context, session_workload

bp = Blueprint("timetable", __name__, template_folder="templates", url_prefix="/timetable")


@bp.get("")
@security.login_required
def page():
    current = current_session_of(get_db(), g.user["id"])
    session_label = service.valid_session(request.args.get("session", ""), current)
    timetable = service.get_timetable(get_db(), g.user["id"], session_label)
    workload = session_workload(load_context(get_db()), [c["code"] for c in timetable["subjects"]])
    response = make_response(
        render_template(
            "timetable/index.html",
            timetable=timetable,
            workload=workload,
            sessions=open_sessions(current),
            current=session_label,
            has_classes=any(column["items"] for column in timetable["columns"]),
        )
    )
    response.headers["Cache-Control"] = "no-store"  # personal data must not be cached
    return response


@bp.get("/export.ics")
@security.login_required
def export():
    """The signed-in student's timetable for one session as a calendar file. Read-only: it changes nothing."""
    conn = get_db()
    session_label = service.valid_session(request.args.get("session", ""), current_session_of(conn, g.user["id"]))
    timetable = service.get_timetable(conn, g.user["id"], session_label)
    items = [item for column in timetable["columns"] for item in column["items"]]
    if not items:
        flash(f"You have no classes in {session_label} to add to a calendar yet. Enrol in a subject and choose its classes first.", "warning")
        return redirect(url_for("timetable.page", session=session_label), code=303)
    due = service.due_tasks(conn, timetable["subjects"]) if request.args.get("due") == "1" else []
    response = Response(ical.build_calendar(session_label, items, due), mimetype="text/calendar")
    response.headers["Content-Type"] = "text/calendar; charset=utf-8"
    response.headers["Content-Disposition"] = f'attachment; filename="enrolment-hub-timetable-{ical.slug(session_label)}.ics"'
    response.headers["Cache-Control"] = "no-store"  # personal data must not be cached
    return response


# --- changes: POST only, CSRF protected, always on the signed-in student's own choices --------------

def _back(session_label):
    current = current_session_of(get_db(), g.user["id"])
    return redirect(url_for("timetable.page", session=service.valid_session(session_label, current)), code=303)


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
