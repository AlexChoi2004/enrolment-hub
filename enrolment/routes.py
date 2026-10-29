"""Student record pages and enrolment changes. A student can only ever change their own record."""
from flask import (
    Blueprint,
    abort,
    flash,
    g,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)

from accounts.service import STUDENT_NUMBER_PATTERN
from enrolment import service
from shared import security
from shared.db import get_db
from subject_catalogue.service import is_valid_code

bp = Blueprint("enrolment", __name__, template_folder="templates", url_prefix="/students")


@bp.get("/me")
@security.login_required
def me():
    return redirect(url_for("enrolment.record", student_number=g.user["student_number"]))


@bp.get("/<student_number>/record")
@security.login_required
def record(student_number):
    if not STUDENT_NUMBER_PATTERN.fullmatch(student_number):
        abort(400)
    # Ownership check on the server: the URL is never trusted. Another student's record,
    # and a student number that does not exist, both get the same 403.
    if student_number.upper() != g.user["student_number"]:
        abort(403)

    conn = get_db()
    progress = service.evaluate_subjects(conn, g.user["id"])
    record_data = service.get_record(conn, g.user["id"])
    for subject in record_data["enrolled"]:
        subject["move_sessions"] = progress["subjects"][subject["code"]]["move_sessions"]
    response = make_response(
        render_template(
            "enrolment/record.html",
            student=g.user,
            course=service.get_course(conn, g.user["course_code"]),
            record=record_data,
            year=service.study_year(g.user["commencement_session"]),
            current_session=service.CURRENT_SESSION,
            session_loads=progress["session_loads"],
            max_cp=service.MAX_CP_PER_SESSION,
            next_url=request.path,
        )
    )
    response.headers["Cache-Control"] = "no-store"  # personal data must not be cached
    return response


# --- enrolment changes ------------------------------------------------------------------------
# These always act on the signed-in student (there is no student id in the URL or the form),
# only accept POST with a CSRF token, and answer with a redirect plus a flash message.

def _back():
    return redirect(
        security.safe_next(request.form.get("next"), url_for("catalogue.list_page")), code=303
    )


def _code_from_form():
    code = request.form.get("subject_code", "")
    if not is_valid_code(code):
        abort(400)
    return code


def _run(action, success_message):
    try:
        label = action()
    except service.EnrolmentError as exc:
        flash(str(exc), "error")
    else:
        flash(success_message.format(label=label), "success")
    return _back()


@bp.post("/me/enrol")
@security.login_required
def enrol():
    security.require_csrf()
    code = _code_from_form()
    session_label = request.form.get("session_label", "")
    return _run(
        lambda: service.enrol(get_db(), g.user["id"], code, session_label),
        "Enrolled in {label} for " + session_label + ".",
    )


@bp.post("/me/withdraw/<code>")
@security.login_required
def withdraw(code):
    security.require_csrf()
    if not is_valid_code(code):
        abort(400)
    return _run(
        lambda: service.withdraw(get_db(), g.user["id"], code),
        "Withdrew from {label}.",
    )


@bp.post("/me/move/<code>")
@security.login_required
def move(code):
    security.require_csrf()
    if not is_valid_code(code):
        abort(400)
    new_session = request.form.get("session_label", "")
    return _run(
        lambda: service.move_session(get_db(), g.user["id"], code, new_session),
        "Moved {label} to " + new_session + ".",
    )