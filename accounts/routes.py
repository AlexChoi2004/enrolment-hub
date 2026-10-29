"""Login and logout pages. Business rules live in service.py."""
from flask import (
    Blueprint,
    current_app,
    g,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from accounts import service
from accounts.seed import DEMO_PASSWORD, DEMO_STUDENT_NUMBER
from shared import security
from shared.db import get_db

bp = Blueprint("accounts", __name__, template_folder="templates")

# One message for every kind of failure, so it never reveals whether an account exists.
GENERIC_FAILURE = (
    "Incorrect student number or password. "
    "After 5 failed attempts an account is locked for 5 minutes."
)


@bp.before_app_request
def load_current_user():
    g.user = None
    user_id = session.get("user_id")
    if user_id is not None:
        g.user = service.get_user(get_db(), user_id)
        if g.user is None:  # account no longer exists: drop the stale session
            session.pop("user_id", None)


@bp.app_context_processor
def inject_template_globals():
    return {"current_user": g.get("user"), "csrf_token": security.csrf_token}


def _clean_next():
    target = request.values.get("next", "")
    return target if security.is_safe_next(target) else ""


def _render_login(status=200, message=None, student_number=""):
    response = make_response(
        render_template(
            "accounts/login.html",
            message=message,
            student_number=student_number,
            next_url=_clean_next(),
            show_demo=current_app.config.get("SHOW_DEMO_CREDENTIALS", True),
            demo_student_number=DEMO_STUDENT_NUMBER,
            demo_password=DEMO_PASSWORD,
        ),
        status,
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return _render_login()

    security.require_csrf()
    try:
        student_number, password = service.validate_login(request.form)
    except service.ValidationError as exc:
        return _render_login(400, str(exc))

    user = service.authenticate(get_db(), student_number, password)
    if user is None:
        # Log who failed, never what they typed as a password.
        current_app.logger.warning("Failed login for student number %s", student_number)
        return _render_login(401, GENERIC_FAILURE, student_number)

    session.clear()  # new session on login, so a pre-login session can't be reused
    session["user_id"] = user["id"]
    session.permanent = True
    return redirect(security.safe_next(request.values.get("next"), url_for("catalogue.list_page")))


@bp.post("/logout")
def logout():
    security.require_csrf()
    session.clear()
    return redirect(url_for("accounts.login"))