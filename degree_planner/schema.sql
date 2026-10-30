CREATE TABLE IF NOT EXISTS planned_subjects (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject_code  TEXT NOT NULL REFERENCES subjects(code),
    -- A plan is not an enrolment: nothing here counts as completed or enrolled.
    session_label TEXT NOT NULL,
    -- One planned slot per subject per student.
    UNIQUE (user_id, subject_code)
);