"""The Help page: how the demonstration works, the demo starting points and what to try with each. Public, no personal data."""
from flask import Blueprint, render_template

from enrolment.presets import PRESETS

bp = Blueprint("guide", __name__, template_folder="templates", url_prefix="/help")


@bp.get("")
def page():
    return render_template("guide/index.html", presets=PRESETS)
