"""Load the supplied handbook-derived data into SQLite (idempotent)."""
from subject_catalogue.seed_data import (
    CATEGORIES,
    COURSE,
    PREREQUISITES,
    SUBJECTS,
)


def seed_catalogue(conn):
    conn.execute(
        "INSERT OR IGNORE INTO courses (code, name, major_code, major_name, handbook_year)"
        " VALUES (:code, :name, :major_code, :major_name, :handbook_year)",
        COURSE,
    )
    conn.executemany(
        "INSERT OR IGNORE INTO requirement_categories"
        " (category, label, required_credit_points, sort_order) VALUES (?, ?, ?, ?)",
        CATEGORIES,
    )
    conn.executemany(
        "INSERT OR IGNORE INTO subjects"
        " (code, name, credit_points, category, sessions_offered, description, is_synthetic)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        SUBJECTS,
    )
    conn.executemany(
        "INSERT OR IGNORE INTO prerequisites (subject_code, prereq_code) VALUES (?, ?)",
        PREREQUISITES,
    )
    # The supplied list is treated as complete: subjects with a rule require
    # prerequisites, every other subject has none (the column default).
    conn.execute(
        "UPDATE subjects SET prereq_status = 'required'"
        " WHERE code IN (SELECT DISTINCT subject_code FROM prerequisites)"
    )