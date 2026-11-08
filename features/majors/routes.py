"""Choose or swap a major. A student can only ever change their own major."""
from flask import Blueprint, abort, flash, g, make_response, redirect, render_template, request, url_for

from features.advisor.service import (
    GOOD_MAX_EXTRA_CP, THINK_EXTRA_CP, THINK_EXTRA_SESSIONS, ElectiveChoiceError, assess, validate_electives,
)
from features.majors import service
from features.majors.fit import rank_majors
from features.subject_catalogue import compare as program_compare
from features.subject_catalogue.programs import major_program, options_of
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


@bp.get("/fit")
@security.login_required
def fit():
    """Every major judged for this student by the swap advisor's rules. Read-only: it changes nothing."""
    comparison = rank_majors(get_db(), g.user["id"], request.args.get("sort", "fit"))  # an unknown sort falls back to best fit
    for row in comparison["rows"] + ([comparison["current"]] if comparison["current"] else []):
        row["href"] = url_for("majors.show", code=row["code"])
    rules = {"good_cp": GOOD_MAX_EXTRA_CP, "think_sessions": THINK_EXTRA_SESSIONS, "think_cp": THINK_EXTRA_CP}
    return _private(render_template("majors/fit.html", comparison=comparison, rules=rules))


@bp.get("/compare")
@security.login_required
def compare():
    """Two majors side by side: what they share, what only one has, and how their focus differs. Read-only."""
    conn = get_db()
    a, b = request.args.get("a", ""), request.args.get("b", "")
    if any(code and not is_valid_major_code(code) for code in (a, b)):
        abort(400)
    result, message = None, None
    if a and b and a == b:
        message = "Pick two different majors to compare."
    elif a and b:
        first, second = major_program(conn, a), major_program(conn, b)
        if first is None or second is None:
            abort(404)
        result = program_compare.compare_programs(first, second)
    mine = user_major(conn, g.user["id"])
    return _private(render_template(
        "majors/compare.html", options=options_of(conn, "major"), a=a or (mine["code"] if mine and not b else ""), b=b, result=result, message=message,
        rules={"close": program_compare.CLOSE, "partly": program_compare.PARTLY}))


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
    tab = "about" if request.args.get("tab") == "about" else "subjects"
    program = major_program(conn, code) if tab == "about" else None
    return _private(render_template("majors/show.html", major=major, advice=advice, tab=tab, program=program))


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
