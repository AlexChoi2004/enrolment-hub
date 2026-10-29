"""Request-level security helpers: CSRF protection, safe redirects, security headers."""
import hmac
import secrets
from functools import wraps
from urllib.parse import urlparse

from flask import abort, g, make_response, redirect, request, session, url_for

CSRF_SESSION_KEY = "csrf_token"

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
)


def csrf_token():
    """Return this session's CSRF token, creating one if needed."""
    token = session.get(CSRF_SESSION_KEY)
    if token is None:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
    return token


def require_csrf():
    """Abort with 400 unless the request carries this session's CSRF token."""
    expected = session.get(CSRF_SESSION_KEY, "")
    supplied = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token") or ""
    if not expected or not hmac.compare_digest(expected.encode(), supplied.encode()):
        abort(400, description="Invalid or missing CSRF token.")


def is_safe_next(target):
    """True only for a plain same-site path like /subjects?q=web."""
    if not target or not isinstance(target, str):
        return False
    if any(ord(ch) < 32 for ch in target):
        return False
    if not target.startswith("/") or target.startswith("//") or "\\" in target:
        return False
    parsed = urlparse(target)
    return not parsed.scheme and not parsed.netloc


def safe_next(target, default):
    return target if is_safe_next(target) else default


def apply_security_headers(response):
    response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    return response


def login_required(view):
    """Send anonymous visitors to the login page (HTMX requests get a 401 and a redirect hint)."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.get("user") is None:
            if request.headers.get("HX-Request") == "true":
                response = make_response("", 401)
                response.headers["HX-Redirect"] = url_for("accounts.login")
                return response
            return redirect(url_for("accounts.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped