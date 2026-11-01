"""Choose or swap a major. A student can only ever change their own major."""
from flask import Blueprint, abort, flash, g, make_response, redirect, render_template, url_for

from majors import service
from shared import security
from shared.db import get_db
from subject_catalogue.service import is_valid_major_code, list_majors, user_major

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
    major = service.preview(get_db(), g.user["id"], code)
    if major is None:
        abort(404)
    return _private(render_template("majors/show.html", major=major))


@bp.post("/<code>/choose")
@security.login_required
def choose(code):
    security.require_csrf()
    if not is_valid_major_code(code):
        abort(400)
    try:
        result = service.choose_major(get_db(), g.user["id"], code)
    except service.MajorError as exc:
        flash(str(exc), "error")
        return redirect(url_for("majors.show", code=code), code=303)
    verb = "Swapped to" if result["swapped"] else "Confirmed"
    flash(f"{verb} {result['major']} as your major.", "success")
    if result["plan_removed"]:
        flash(f"Removed {result['plan_removed']} planned subject(s) that are not in this major.", "warning")
    return redirect(url_for("catalogue.list_page"), code=303)