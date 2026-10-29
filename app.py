"""Enrolment Hub: one Flask app, one module per feature."""
import os
from pathlib import Path

from flask import Flask, jsonify

from shared import db

ROOT = Path(__file__).resolve().parent


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        DATABASE=os.getenv("DATABASE_PATH", str(ROOT / "enrolment_hub.db")),
        # Placeholder for development only. Chunk 3 (login) refuses to run
        # with this value outside of tests.
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-only-change-me"),
    )
    if test_config:
        app.config.update(test_config)

    if not os.path.exists(app.config["DATABASE"]):
        db.build_database(app.config["DATABASE"])

    app.teardown_appcontext(db.close_db)

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")))