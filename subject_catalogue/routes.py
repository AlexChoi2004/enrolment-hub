"""Subject catalogue pages. Business rules live in service.py."""
from flask import Blueprint, abort, g, make_response, render_template, request

from enrolment import service as enrolment_service
from shared import security
from shared.db import get_db
from subject_catalogue import service

bp = Blueprint("catalogue", __name__, template_folder="templates", url_prefix="/subjects")


def _is_htmx():
    return request.headers.get("HX-Request") == "true"


def _respond(template, status=200, **context):
    response = make_response(render_template(template, **context), status)
    # The same URL returns a full page or a fragment, so caches must not mix them.
    response.headers["Vary"] = "HX-Request"
    return response


@bp.get("")
@security.login_required
def list_page():
    conn = get_db()
    categories = service.list_categories(conn)
    valid = {c["category"] for c in categories}
    try:
        filters = service.parse_filters(request.args, valid)
    except service.FilterError as exc:
        return _respond("catalogue/error.html", status=400, message=str(exc))

    template = "catalogue/_results.html" if _is_htmx() else "catalogue/index.html"
    progress = enrolment_service.evaluate_subjects(conn, g.user["id"])
    subjects = service.list_subjects(conn, filters)
    subjects = service.filter_by_status(service.attach_status(subjects, progress), filters.status)
    return _respond(
        template,
        subjects=subjects,
        groups=service.group_by_category(subjects, categories, progress),
        categories=categories,
        filters=filters,
        sessions=service.SESSIONS,
        session_loads=progress["session_loads"],
        max_cp=enrolment_service.MAX_CP_PER_SESSION,
        next_url=request.full_path.rstrip("?"),
    )


@bp.get("/<code>")
@security.login_required
def detail_page(code):
    if not service.is_valid_code(code):
        abort(400)
    conn = get_db()
    subject = service.get_subject(conn, code)
    if subject is None:
        abort(404)
    service.attach_status([subject], enrolment_service.evaluate_subjects(conn, g.user["id"]))
    return _respond("catalogue/detail.html", subject=subject, next_url=request.path)