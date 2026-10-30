"""Login, registration and logout pages. Business rules live in service.py."""
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
from accounts.seed import DEMO_EMAIL, DEMO_PASSWORD, DEMO_STUDENT_NUMBER
from enrolment import service as enrolment_service
from enrolment.service import CURRENT_SESSION
from shared import security
from shared.db import get_db

bp = Blueprint("accounts", __name__, template_folder="templates")

# One message for every kind of failure, so it never reveals whether an account exists.
GENERIC_FAILURE = (
    "Incorrect email or password. "
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


def _no_store(response):
    response.headers["Cache-Control"] = "no-store"
    return response


def _start_session(user):
    session.clear()  # new session on login, so a pre-login session can't be reused
    session["user_id"] = user["id"]
    session.permanent = True


def _render_login(status=200, message=None, email=""):
    return _no_store(
        make_response(
            render_template(
                "accounts/login.html",
                message=message,
                email=email,
                next_url=_clean_next(),
                show_demo=current_app.config.get("SHOW_DEMO_CREDENTIALS", True),
                demo_email=DEMO_EMAIL,
                demo_password=DEMO_PASSWORD,
            ),
            status,
        )
    )


def _render_register(status=200, errors=None, email=""):
    return _no_store(
        make_response(
            render_template(
                "accounts/register.html",
                errors=errors or [],
                email=email,
                current_session=CURRENT_SESSION,
            ),
            status,
        )
    )


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return _render_login()

    security.require_csrf()
    try:
        email, password = service.validate_login(request.form)
    except service.ValidationError as exc:
        return _render_login(400, str(exc))

    user = service.authenticate(get_db(), email, password)
    if user is None:
        # Log a one-way tag of the email, never the email itself or the password.
        current_app.logger.warning("Failed login for account %s", service.email_fingerprint(email))
        return _render_login(401, GENERIC_FAILURE, email)

    _start_session(user)
    return redirect(security.safe_next(request.values.get("next"), url_for("enrolment.me")))


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return _render_register()

    security.require_csrf()
    conn = get_db()
    if service.account_count(conn) >= current_app.config["MAX_ACCOUNTS"]:
        return _render_register(
            403, ["This prototype has reached its limit of accounts, so new sign-ups are closed."]
        )

    email, errors = service.validate_registration(request.form)
    if errors:
        return _render_register(400, errors, email)

    try:
        user = service.create_user(
            conn, email, request.form["password"], commencement_session=CURRENT_SESSION
        )
    except service.DuplicateEmailError:
        return _render_register(409, ["An account with this email already exists. Try logging in."], email)

    _start_session(user)
    return redirect(url_for("enrolment.me"))


@bp.get("/profile")
@security.login_required
def profile():
    conn = get_db()
    person = service.get_profile(conn, g.user["id"])
    response = make_response(
        render_template(
            "accounts/profile.html",
            person=person,
            course=enrolment_service.get_course(conn, person["course_code"]),
            year=enrolment_service.study_year(person["commencement_session"]),
            current_session=CURRENT_SESSION,
            record=enrolment_service.get_record(conn, g.user["id"]),
            is_demo=person["student_number"] == DEMO_STUDENT_NUMBER,
        )
    )
    response.headers["Cache-Control"] = "no-store"  # personal data must not be cached
    return response


@bp.post("/logout")
def logout():
    security.require_csrf()
    session.clear()
    return redirect(url_for("accounts.login"))