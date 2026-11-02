"""Load the supplied handbook-derived data into SQLite (idempotent)."""
from subject_catalogue.assessment_data import ASSESSMENTS, DESCRIPTIONS
from subject_catalogue.assessments import explain
from subject_catalogue.seed_data import (
    CATEGORIES,
    COURSE,
    CREDIT_REQUIREMENTS,
    MAJOR_ONLY_SUBJECTS,
    HANDBOOK_PREREQUISITES,
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
        [(subject, prereq, 0, 0) for subject, prereq in PREREQUISITES] + HANDBOOK_PREREQUISITES,
    )

    conn.executemany("INSERT OR IGNORE INTO majors (code, name, core_cp, options_cp) VALUES (?, ?, ?, ?)", MAJORS)
    conn.executemany(
        "INSERT OR IGNORE INTO major_subjects (major_code, subject_code, role) VALUES (?, ?, ?)",
        MAJOR_SUBJECTS,
    )
    for subject, major, minimum in CREDIT_REQUIREMENTS:
        conn.execute(
            "INSERT INTO credit_requirements (subject_code, major_code, min_cp) SELECT ?, ?, ?"
            " WHERE NOT EXISTS (SELECT 1 FROM credit_requirements WHERE subject_code = ? AND major_code IS ?)",
            (subject, major, minimum, subject, major),
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
    seed_assessments(conn)


def seed_assessments(conn):
    """Descriptions, and one assessment structure per subject. Safe to run twice."""
    for code, (text, tags) in DESCRIPTIONS.items():
        verification = ASSESSMENTS[code]["verification"]
        source = {
            "indicative": "Summarised for this app from the UTS Handbook",
            "synthetic": "Invented for this prototype",
        }.get(verification, "Supplied description")
        conn.execute(
            "INSERT OR IGNORE INTO subject_descriptions (subject_code, description, style_tags, source)"
            " VALUES (?, ?, ?, ?)",
            (code, text, ",".join(tags), source),
        )
    for code, s in ASSESSMENTS.items():
        if conn.execute(
            "SELECT 1 FROM assessment_structures WHERE subject_code = ? AND source = ?", (code, s["source"])
        ).fetchone():
            continue
        cur = conn.execute(
            "INSERT INTO assessment_structures (subject_code, academic_year, session, source, retrieved_on,"
            " verification, note) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (code, s["year"], s["session"], s["source"], s["retrieved_on"], s["verification"], s["note"]),
        )
        for position, (name, type_, groupwork, weight) in enumerate(s["tasks"], 1):
            conn.execute(
                "INSERT INTO assessments (structure_id, position, name, description, type, weight, groupwork)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (cur.lastrowid, position, name, explain(type_, groupwork), type_, weight, groupwork),
            )
