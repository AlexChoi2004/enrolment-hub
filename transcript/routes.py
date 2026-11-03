"""The Results (transcript) page. A student only ever sees their own."""
from flask import Blueprint, g, make_response, render_template, request

from shared import security
from shared.db import get_db
from transcript import service

bp = Blueprint("transcript", __name__, template_folder="templates", url_prefix="/transcript")


@bp.get("")
@security.login_required
def page():
    newest_first = request.args.get("order") != "oldest"  # the latest session is at the top unless asked otherwise
    response = make_response(render_template(
        "transcript/index.html", result=service.transcript(get_db(), g.user["id"], newest_first=newest_first)))
    response.headers["Cache-Control"] = "no-store"  # personal data must not be cached
    return response
