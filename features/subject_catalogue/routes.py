"""Subject catalogue pages. Business rules live in service.py."""
from flask import Blueprint, abort, g, make_response, render_template, request, url_for

from features.enrolment import service as enrolment_service
from shared import security
from shared.db import get_db
from features.subject_catalogue import service

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
    categories = service.list_categories(conn, g.user["id"])  # only the sections of this student's degree
    major = service.user_major(conn, g.user["id"])
    submajor = service.user_submajor(conn, g.user["id"])
    electives = service.uses_general_electives(conn, g.user["id"])
    valid = {c["category"] for c in categories}
    try:
        filters = service.parse_filters(request.args, valid)
    except service.FilterError as exc:
        return _respond("catalogue/error.html", status=400, message=str(exc))

    template = "catalogue/_results.html" if _is_htmx() else "catalogue/index.html"
    progress = enrolment_service.evaluate_subjects(conn, g.user["id"])
    subjects = service.list_subjects(conn, filters, user_id=g.user["id"])
    subjects = service.filter_by_status(service.attach_status(subjects, progress), filters.status)
    groups = service.group_by_category(subjects, categories, progress)
    unfiltered = not (filters.q or filters.category or filters.session or filters.prereqs or filters.status)
    if major is None and unfiltered:
        # No major yet: where the major sections would be, offer to choose one instead of listing them.
        position = next((i + 1 for i, g_ in enumerate(groups) if g_["category"] == "honours_core"), len(groups))
        groups.insert(position, {"category": "major_prompt", "label": "Major", "prompt": True,
                                 "text": "You haven't chosen a major yet.", "button": "Choose major",
                                 "href": url_for("majors.index"), "rule": "", "complete": False, "note": "", "subjects": []})
    if submajor is None and not electives and unfiltered:
        groups.append({"category": "submajor_prompt", "label": "Sub-major or electives", "prompt": True,
                       "text": "You haven't chosen a sub-major or general electives yet.", "button": "Choose sub-major or electives",
                       "href": url_for("submajors.index"), "rule": "", "complete": False, "note": "", "subjects": []})
    return _respond(
        template,
        subjects=subjects,
        groups=groups,
        major=major,
        submajor=submajor,
        electives=electives,
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
    subject = service.get_subject(conn, code, user_id=g.user["id"])
    if subject is None:
        abort(404)
    service.attach_status([subject], enrolment_service.evaluate_subjects(conn, g.user["id"]))
    return _respond("catalogue/detail.html", subject=subject, next_url=request.path)
