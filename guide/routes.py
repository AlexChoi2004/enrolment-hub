"""The Help page: how the demonstration works and step-by-step scenarios to try. Public, no personal data."""
from flask import Blueprint, render_template

bp = Blueprint("guide", __name__, template_folder="templates", url_prefix="/help")


@bp.get("")
def page():
    return render_template("guide/index.html")
