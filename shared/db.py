"""SQLite helpers shared by every feature module.

One SQLite file backs the whole app. Each feature owns its own schema.sql
and tables; all SQL elsewhere uses bound parameters (never string building).
"""
import sqlite3
from pathlib import Path

from flask import current_app, g

ROOT = Path(__file__).resolve().parent.parent

# Order matters: later schemas reference earlier tables.
SCHEMA_FILES = [
    ROOT / "subject_catalogue" / "schema.sql",
    ROOT / "accounts" / "schema.sql",
    ROOT / "enrolment" / "schema.sql",
    ROOT / "degree_planner" / "schema.sql",
]


def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    """One connection per request."""
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_schema(conn):
    for schema_file in SCHEMA_FILES:
        if schema_file.exists():
            conn.executescript(schema_file.read_text(encoding="utf-8"))
    conn.commit()


def seed_db(conn):
    # Imported here so each feature can add its own seeder in later chunks.
    from subject_catalogue.seed import seed_catalogue

    seed_catalogue(conn)
    conn.commit()


def build_database(path):
    """Create a fresh, seeded database file."""
    conn = connect(path)
    init_schema(conn)
    seed_db(conn)
    conn.close()