"""Choose or swap a major. A student can only ever change their own major."""
from flask import Blueprint, abort, flash, g, make_response, redirect, render_template, request, url_for

from features.advisor.service import ElectiveChoiceError, assess, validate_electives
from features.majors import service
from shared import security
from shared.db import get_db
from features.subject_catalogue.service import is_valid_major_code, list_majors, user_major

bp = Blueprint("majors", __name__, template_folder="templates", url_prefix="/major")


def _private(html):
    response = make_response(html)
    response.headers["Cache-Control"] = "no-store"  # personal data must not be cached
    return response


@bp.get("")
@security.login_required
def index():
    conn = get_db()
    return _private(render_template(
        "majors/index.html", majors=list_majors(conn), current=user_major(conn, g.user["id"]),
    ))


@bp.get("/<code>")
@security.login_required
def show(code):
    if not is_valid_major_code(code):
        abort(400)
    conn = get_db()
    major = service.preview(conn, g.user["id"], code)
    if major is None:
        abort(404)
    advice = None if major["is_current"] else assess(conn, g.user["id"], "major", code)
    if advice and advice["first_choice"]:
        advice = None  # choosing a first major: there is nothing to swap from
    return _private(render_template("majors/show.html", major=major, advice=advice))


@bp.post("/<code>/choose")
@security.login_required
def choose(code):
    security.require_csrf()
    if not is_valid_major_code(code):
        abort(400)
    conn = get_db()
    try:  # subjects the student chose to count as general electives instead of losing them
        counted = validate_electives(conn, g.user["id"], "major", code, None, request.form.getlist("count_as_electives"))
    except ElectiveChoiceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("majors.show", code=code), code=303)
    advice = assess(conn, g.user["id"], "major", code, elective_codes=counted)
    if advice and advice["needs_ack"] and request.form.get("acknowledge") != "1":  # the student's own yes is required
        flash("Please tick the box to confirm you understand what this swap costs.", "error")
        return redirect(url_for("majors.show", code=code), code=303)
    try:
        result = service.choose_major(get_db(), g.user["id"], code, withdraw=request.form.get("withdraw_in_progress") == "1",
                                      count_as_electives=counted)
    except service.MajorError as exc:
        flash(str(exc), "error")
        return redirect(url_for("majors.show", code=code), code=303)
    verb = "Swapped to" if result["swapped"] else "Confirmed"
    flash(f"{verb} {result['major']} as your major.", "success")
    if result["counted_as_electives"]:
        flash(f"Counted {result['counted_as_electives']} subject(s) as general electives.", "success")
    if result["withdrawn"]:
        flash(f"Withdrew you from {result['withdrawn']} in-progress subject(s) that are not in this major.", "success")
    if result["no_longer_counted"]:
        flash(f"{result['no_longer_counted']} subject(s) you have done no longer count towards your degree.", "warning")
    if result["plan_removed"]:
        flash(f"Removed {result['plan_removed']} planned subject(s) that are not in this major.", "warning")
    return redirect(url_for("catalogue.list_page"), code=303)
