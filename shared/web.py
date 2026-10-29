"""Shared templates and static files (layout, CSS, vendored HTMX)."""
from flask import Blueprint

shared_bp = Blueprint(
    "shared",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/static",
)