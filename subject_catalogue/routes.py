"""Subject catalogue pages. Business rules live in service.py."""
from flask import Blueprint, abort, make_response, render_template, request

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
    subjects = service.list_subjects(conn, filters)
    return _respond(
        template,
        subjects=subjects,
        groups=service.group_by_category(subjects, categories),
        categories=categories,
        filters=filters,
        sessions=service.SESSIONS,
    )


@bp.get("/<code>")
@security.login_required
def detail_page(code):
    if not service.is_valid_code(code):
        abort(400)
    subject = service.get_subject(get_db(), code)
    if subject is None:
        abort(404)
    return _respond("catalogue/detail.html", subject=subject)