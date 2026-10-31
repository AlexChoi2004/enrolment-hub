"""Enrolment Hub: one Flask app, one module per feature."""
import os
import secrets
from datetime import timedelta
from pathlib import Path

import click
from flask import Flask, g, jsonify, redirect, render_template, url_for

from accounts.routes import bp as accounts_bp
from accounts.seed import DEMO_EMAIL, DEMO_PASSWORD
from degree_planner.routes import bp as planner_bp
from timetable.routes import bp as timetable_bp
from enrolment.routes import bp as enrolment_bp
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
        MAX_ACCOUNTS=200,  # stops anyone filling the database with sign-ups
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
    app.register_blueprint(planner_bp)
    app.register_blueprint(timetable_bp)
    app.register_blueprint(enrolment_bp)

    @app.get("/")
    def index():
        # Students go straight to their record; visitors see a welcome screen.
        if g.get("user"):
            return redirect(url_for("enrolment.me"))
        return render_template(
            "welcome.html",
            show_demo=app.config["SHOW_DEMO_CREDENTIALS"],
            demo_email=DEMO_EMAIL,
            demo_password=DEMO_PASSWORD,
        )

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.cli.command("reset-demo")
    def reset_demo():
        """Delete the database and rebuild it with fresh synthetic demo data."""
        path = app.config["DATABASE"]
        if os.path.exists(path):
            os.remove(path)
        db.build_database(path)
        click.echo("Demo data reset.")

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")))