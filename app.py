"""Enrolment Hub: one Flask app, one module per feature."""
import os
import secrets
from datetime import timedelta
from pathlib import Path

from flask import Flask, jsonify, redirect, url_for

from accounts.routes import bp as accounts_bp
from shared import db, security
from shared.web import shared_bp
from subject_catalogue.routes import bp as catalogue_bp

ROOT = Path(__file__).resolve().parent


def create_app(test_config=None):
    # static_folder=None: static files are served by the shared blueprint.
    app = Flask(__name__, static_folder=None)
    app.config.update(
        DATABASE=os.getenv("DATABASE_PATH", str(ROOT / "enrolment_hub.db")),
        # Set SECRET_KEY in the environment for a stable key. Without it a random key is
        # generated at startup: safe, but everyone is logged out whenever the app restarts.
        SECRET_KEY=os.getenv("SECRET_KEY") or secrets.token_hex(32),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        # Set SESSION_COOKIE_SECURE=1 when serving over HTTPS.
        SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE") == "1",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=2),
        SHOW_DEMO_CREDENTIALS=True,
    )
    if test_config:
        app.config.update(test_config)

    if not os.path.exists(app.config["DATABASE"]):
        db.build_database(app.config["DATABASE"])

    app.teardown_appcontext(db.close_db)
    app.after_request(security.apply_security_headers)

    app.register_blueprint(shared_bp)
    app.register_blueprint(accounts_bp)
    app.register_blueprint(catalogue_bp)

    @app.get("/")
    def index():
        return redirect(url_for("catalogue.list_page"))

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")))