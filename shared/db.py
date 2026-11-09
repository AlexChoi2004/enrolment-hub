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
    ROOT / "features" / "subject_catalogue" / "schema.sql",
    ROOT / "features" / "accounts" / "schema.sql",
    ROOT / "features" / "enrolment" / "schema.sql",
    ROOT / "features" / "timetable" / "schema.sql",
    ROOT / "features" / "degree_planner" / "schema.sql",
    ROOT / "ai_services" / "rag" / "schema.sql",
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


# Columns added after a table was first created. CREATE TABLE IF NOT EXISTS never changes a table that exists, so these are added here.
HANDBOOK_URL_COLUMN = "TEXT CHECK (handbook_url IS NULL OR handbook_url LIKE 'https://coursehandbook.uts.edu.au/%')"
ADDED_COLUMNS = {
    ("subjects", "handbook_url"): HANDBOOK_URL_COLUMN, ("majors", "handbook_url"): HANDBOOK_URL_COLUMN,
    ("submajors", "handbook_url"): HANDBOOK_URL_COLUMN, ("streams", "handbook_url"): HANDBOOK_URL_COLUMN,
    ("subjects", "sessions_source"): "TEXT NOT NULL DEFAULT 'illustrative' CHECK (sessions_source IN ('illustrative', 'handbook'))",
    ("subjects", "sessions_note"): "TEXT",
}


def add_missing_columns(conn):
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    for (table, column), definition in ADDED_COLUMNS.items():
        if table in tables and column not in {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}:  # noqa: S608 (fixed names above)
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")  # noqa: S608


def init_schema(conn):
    for schema_file in SCHEMA_FILES:
        if schema_file.exists():
            conn.executescript(schema_file.read_text(encoding="utf-8"))
    add_missing_columns(conn)
    conn.commit()


def seed_db(conn, demo_profile="fresh"):
    # Imported here so each feature can add its own seeder in later chunks.
    from features.accounts.seed import seed_accounts
    from features.enrolment.seed import seed_enrolment
    from ai_services.rag.index import build_index
    from features.subject_catalogue.seed import seed_catalogue
    from features.timetable.seed import seed_timetable

    seed_catalogue(conn)
    seed_accounts(conn, demo_profile)
    seed_enrolment(conn, demo_profile)
    seed_timetable(conn)
    conn.commit()
    build_index(conn)  # the AI's sources, built from the data seeded above


def build_database(path, demo_profile="fresh"):
    """Create a fresh, seeded database file. The demo student starts as a first-year ("fresh") or two years in ("sample")."""
    conn = connect(path)
    init_schema(conn)
    seed_db(conn, demo_profile)
    conn.close()
