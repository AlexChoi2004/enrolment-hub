"""Choose or swap a sub-major. A student can only ever change their own."""
from flask import Blueprint, abort, flash, g, make_response, redirect, render_template, request, url_for

from advisor.service import ElectiveChoiceError, assess, validate_electives
from shared import security
from shared.db import get_db
from subject_catalogue.service import (
    is_valid_language_code,
    is_valid_submajor_code,
    list_submajors,
    uses_general_electives,
    user_submajor,
)
from submajors import service

bp = Blueprint("submajors", __name__, template_folder="templates", url_prefix="/submajor")


def _private(html):
    response = make_response(html)
    response.headers["Cache-Control"] = "no-store"  # personal data must not be cached
    return response


@bp.get("")
@security.login_required
def index():
    conn = get_db()
    return _private(render_template(
        "submajors/index.html", submajors=list_submajors(conn), current=user_submajor(conn, g.user["id"]),
        electives=uses_general_electives(conn, g.user["id"]),
    ))


@bp.get("/electives")
@security.login_required
def electives():
    conn = get_db()
    options = service.electives_preview(conn, g.user["id"])
    advice = None if options["is_current"] else assess(conn, g.user["id"], "electives")
    if advice and advice["first_choice"]:
        advice = None
    return _private(render_template("submajors/electives.html", options=options, advice=advice))


@bp.post("/electives/choose")
@security.login_required
def choose_electives():
    security.require_csrf()
    conn = get_db()
    try:  # subjects the student chose to count as general electives instead of losing them
        counted = validate_electives(conn, g.user["id"], "electives", None, None, request.form.getlist("count_as_electives"))
    except ElectiveChoiceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("submajors.electives"), code=303)
    advice = assess(conn, g.user["id"], "electives", elective_codes=counted)
    if advice["needs_ack"] and request.form.get("acknowledge") != "1":  # the student's own yes is required
        flash("Please tick the box to confirm you understand what this swap costs.", "error")
        return redirect(url_for("submajors.electives"), code=303)
    try:
        result = service.choose_electives(get_db(), g.user["id"], withdraw=request.form.get("withdraw_in_progress") == "1",
                                          count_as_electives=counted)
    except service.SubmajorError as exc:
        flash(str(exc), "error")
        return redirect(url_for("submajors.electives"), code=303)
    verb = "Swapped to" if result["swapped"] else "Confirmed"
    flash(f"{verb} 24 cp of general electives instead of a sub-major.", "success")
    if result["withdrawn"]:
        flash(f"Withdrew you from {result['withdrawn']} in-progress subject(s) that no longer count.", "success")
    if result["counted_as_electives"]:
        flash(f"Counted {result['counted_as_electives']} subject(s) as general electives.", "success")
    if result["no_longer_counted"]:
        flash(f"{result['no_longer_counted']} subject(s) you have done no longer count towards your degree.", "warning")
    if result["plan_removed"]:
        flash(f"Removed {result['plan_removed']} planned subject(s) that are not general electives.", "warning")
    return redirect(url_for("catalogue.list_page"), code=303)


@bp.get("/<code>")
@security.login_required
def show(code):
    if not is_valid_submajor_code(code):
        abort(400)
    language = request.args.get("language") or None
    if language is not None and not is_valid_language_code(language):
        abort(400)
    conn = get_db()
    sub = service.preview(conn, g.user["id"], code, language)
    if sub is None:
        abort(404)
    ready = not sub["is_current"] and not (sub["is_language"] and language is None)
    advice = assess(conn, g.user["id"], "submajor", code, language if sub["is_language"] else None) if ready else None
    if advice and advice["first_choice"]:
        advice = None
    return _private(render_template("submajors/show.html", sub=sub, picked=language, advice=advice))


@bp.post("/<code>/choose")
@security.login_required
def choose(code):
    security.require_csrf()
    if not is_valid_submajor_code(code):
        abort(400)
    language = (request.form.get("language") or "").strip() or None
    if language is not None and not is_valid_language_code(language):
        abort(400)
    advice = assess(get_db(), g.user["id"], "submajor", code, language)
    if advice and advice["needs_ack"] and request.form.get("acknowledge") != "1":  # the student's own yes is required
        flash("Please tick the box to confirm you understand what this swap costs.", "error")
        return redirect(url_for("submajors.show", code=code, language=language), code=303)
    try:
        result = service.choose_submajor(get_db(), g.user["id"], code, language,
                                         withdraw=request.form.get("withdraw_in_progress") == "1")
    except service.SubmajorError as exc:
        flash(str(exc), "error")
        return redirect(url_for("submajors.show", code=code), code=303)
    verb = "Swapped to" if result["swapped"] else "Confirmed"
    where = f" ({result['language']})" if result["language"] else ""
    flash(f"{verb} {result['submajor']}{where} as your sub-major.", "success")
    if result["withdrawn"]:
        flash(f"Withdrew you from {result['withdrawn']} in-progress subject(s) that no longer count.", "success")
    if result["no_longer_counted"]:
        flash(f"{result['no_longer_counted']} subject(s) you have done no longer count towards your degree.", "warning")
    if result["plan_removed"]:
        flash(f"Removed {result['plan_removed']} planned subject(s) that are not in this sub-major.", "warning")
    return redirect(url_for("catalogue.list_page"), code=303)
