"""Load the supplied handbook-derived data into SQLite (idempotent)."""
from features.subject_catalogue.assessment_data import ASSESSMENTS, DESCRIPTIONS
from features.subject_catalogue.assessments import explain, illustrative_due_weeks
from features.subject_catalogue.program_text import CODES, STREAM_CODES, aos_url, subject_handbook_url
from features.subject_catalogue.submajor_data import SOURCE_NOTE, STREAM_SUBJECTS, STREAMS, SUBJECTS as SUBMAJOR_SUBJECTS, SUBMAJORS
from features.subject_catalogue.seed_data import (
    CATEGORIES,
    COURSE,
    CREDIT_REQUIREMENTS,
    MAJOR_ONLY_SUBJECTS,
    HANDBOOK_PREREQUISITES,
    MAJOR_SUBJECTS,
    MAJORS,
    PREREQUISITE_NOTES,
    PREREQUISITES,
    RENAMED,
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
    # A database built earlier keeps its rows, so bring the requirement sections up to date too (this never touches a student's data).
    conn.executemany(
        "UPDATE requirement_categories SET label = ?, required_credit_points = ?, sort_order = ? WHERE category = ?",
        [(label, cp, order, category) for category, label, cp, order in CATEGORIES],
    )
    conn.executemany(
        "INSERT OR IGNORE INTO subjects"
        " (code, name, credit_points, category, sessions_offered, description, is_synthetic)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        SUBJECTS + MAJOR_ONLY_SUBJECTS + SUBMAJOR_SUBJECTS,
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
    # other subject has none. The subjects that exist only in a sub-major have not been researched, so theirs is unknown.
    conn.execute(
        "UPDATE subjects SET prereq_status = 'required' WHERE code IN"
        " (SELECT subject_code FROM prerequisites UNION SELECT subject_code FROM credit_requirements)"
    )
    conn.executemany(
        "UPDATE subjects SET prereq_status = 'unknown' WHERE code = ? AND prereq_status = 'none'",
        [(row[0],) for row in SUBMAJOR_SUBJECTS],
    )
    conn.executemany("UPDATE subjects SET name = ? WHERE code = ? AND name != ?", [(name, code, name) for code, name in RENAMED.items()])
    seed_submajors(conn)
    seed_handbook_links(conn)
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
    for subject in SUBMAJOR_SUBJECTS:  # not researched yet: no tasks, and the student is told so
        ASSESSMENTS.setdefault(subject[0], dict(
            verification="unverified", year=None, session=None, source="No confirmed source", retrieved_on=None,
            note="Not researched yet: exact assessment tasks and weightings are not verified.", tasks=[]))
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
        weeks = illustrative_due_weeks(code, s["tasks"])
        for position, ((name, type_, groupwork, weight), week) in enumerate(zip(s["tasks"], weeks), 1):
            conn.execute(
                "INSERT INTO assessments (structure_id, position, name, description, type, weight, groupwork,"
                " due_week, due_week_source) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'illustrative')",
                (cur.lastrowid, position, name, explain(type_, groupwork), type_, weight, groupwork, week),
            )


def seed_submajors(conn):
    """The sub-majors, their groups and the streams. Safe to run twice."""
    for code, name, cp, note in STREAMS:
        conn.execute("INSERT OR IGNORE INTO streams (code, name, cp, note) VALUES (?, ?, ?, ?)", (code, name, cp, note))
        conn.execute("UPDATE streams SET note = ? WHERE code = ?", (note, code))  # a database built earlier gets the current note
    for stream, subjects in STREAM_SUBJECTS.items():
        conn.executemany("INSERT OR IGNORE INTO stream_subjects (stream_code, subject_code) VALUES (?, ?)", [(stream, s) for s in subjects])
    for code, name, note, groups in SUBMAJORS:
        conn.execute(
            "INSERT OR IGNORE INTO submajors (code, name, total_cp, note, source, academic_year, verification)"
            " VALUES (?, ?, 24, ?, ?, 2027, 'verified')",
            (code, name, note, SOURCE_NOTE),
        )
        conn.execute("UPDATE submajors SET note = ?, source = ?, verification = 'verified' WHERE code = ?", (note, SOURCE_NOTE, code))
        for position, (kind, label, required_cp, subjects, stream, language) in enumerate(groups, 1):
            language_name = label.split(" (")[0] if language else None
            conn.execute(
                "INSERT OR IGNORE INTO submajor_groups (submajor_code, position, kind, label, required_cp, stream_code,"
                " language_program, language_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (code, position, kind, label, required_cp, stream, language, language_name),
            )
            group_id = conn.execute(
                "SELECT id FROM submajor_groups WHERE submajor_code = ? AND position = ?", (code, position)
            ).fetchone()[0]
            conn.executemany(
                "INSERT OR IGNORE INTO submajor_group_subjects (group_id, subject_code) VALUES (?, ?)",
                [(group_id, s) for s in subjects],
            )


def seed_handbook_links(conn):
    """Store the official Handbook page on every subject, major, sub-major and stream that has one. Safe to run twice."""
    conn.executemany("UPDATE subjects SET handbook_url = ? WHERE code = ?", [(subject_handbook_url(r[0]), r[0]) for r in conn.execute("SELECT code FROM subjects").fetchall()])
    conn.executemany("UPDATE majors SET handbook_url = ? WHERE code = ?", [(aos_url(c), c) for c in CODES if c.startswith("MAJ")])
    conn.executemany("UPDATE submajors SET handbook_url = ? WHERE code = ?", [(aos_url(c), c) for c in CODES if c.startswith("SMJ")])
    conn.executemany("UPDATE streams SET handbook_url = ? WHERE code = ?", [(aos_url(c), c) for c in STREAM_CODES])
