"""The dashboard page and the read-only data it loads. Both are for the signed-in student only."""
from flask import Blueprint, g, jsonify, make_response, render_template

from features.dashboard.service import build_dashboard
from shared import security
from shared.db import get_db

bp = Blueprint("dashboard", __name__, template_folder="templates")


def _private(response):
    response.headers["Cache-Control"] = "no-store"  # personal data: never kept by a browser or a proxy
    return response


@bp.get("/dashboard")
@security.login_required
def page():
    data = build_dashboard(get_db(), g.user["id"])
    return _private(make_response(render_template("dashboard/index.html", data=data)))


@bp.get("/api/dashboard")
@security.login_required
def data():
    """The same data as JSON for the React page. GET only, nothing is changed, and only the signed-in student's own data is returned."""
    return _private(jsonify(build_dashboard(get_db(), g.user["id"])))
