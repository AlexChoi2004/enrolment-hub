"""Student record pages. A student can only ever see their own record."""
from flask import Blueprint, abort, g, make_response, redirect, render_template, url_for

from accounts.service import STUDENT_NUMBER_PATTERN
from enrolment import service
from shared import security
from shared.db import get_db

bp = Blueprint("enrolment", __name__, template_folder="templates", url_prefix="/students")


@bp.get("/me")
@security.login_required
def me():
    return redirect(url_for("enrolment.record", student_number=g.user["student_number"]))


@bp.get("/<student_number>/record")
@security.login_required
def record(student_number):
    if not STUDENT_NUMBER_PATTERN.match(student_number):
        abort(400)
    # Ownership check on the server: the URL is never trusted. Another student's record,
    # and a student number that does not exist, both get the same 403.
    if student_number.upper() != g.user["student_number"]:
        abort(403)

    conn = get_db()
    response = make_response(
        render_template(
            "enrolment/record.html",
            student=g.user,
            course=service.get_course(conn, g.user["course_code"]),
            record=service.get_record(conn, g.user["id"]),
        )
    )
    response.headers["Cache-Control"] = "no-store"  # personal data must not be cached
    return response