"""Load the supplied handbook-derived data into SQLite (idempotent)."""
from subject_catalogue.seed_data import (
    CATEGORIES,
    COURSE,
    CREDIT_REQUIREMENTS,
    MAJOR_ONLY_SUBJECTS,
    MAJOR_PREREQUISITES,
    MAJOR_SUBJECTS,
    MAJORS,
    PREREQUISITE_NOTES,
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
        SUBJECTS + MAJOR_ONLY_SUBJECTS,
    )
    conn.executemany(
        "INSERT OR IGNORE INTO prerequisites (subject_code, prereq_code, alt_group, concurrent) VALUES (?, ?, ?, ?)",
        [(subject, prereq, 0, 0) for subject, prereq in PREREQUISITES] + MAJOR_PREREQUISITES,
    )

    conn.executemany("INSERT OR IGNORE INTO majors (code, name, core_cp, options_cp) VALUES (?, ?, ?, ?)", MAJORS)
    conn.executemany(
        "INSERT OR IGNORE INTO major_subjects (major_code, subject_code, role) VALUES (?, ?, ?)",
        MAJOR_SUBJECTS,
    )
    conn.executemany(
        "INSERT OR IGNORE INTO credit_requirements (subject_code, major_code, min_cp) VALUES (?, ?, ?)",
        CREDIT_REQUIREMENTS,
    )
    conn.executemany(
        "INSERT OR IGNORE INTO prerequisite_notes (subject_code, note) VALUES (?, ?)",
        list(PREREQUISITE_NOTES.items()),
    )
    # The supplied lists are treated as complete: a subject with any rule requires prerequisites and every
    # other subject has none.
    conn.execute(
        "UPDATE subjects SET prereq_status = 'required' WHERE code IN"
        " (SELECT subject_code FROM prerequisites UNION SELECT subject_code FROM credit_requirements)"
    )