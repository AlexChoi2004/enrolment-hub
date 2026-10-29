CREATE TABLE IF NOT EXISTS enrolments (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject_code  TEXT NOT NULL REFERENCES subjects(code),
    -- 'completed' = finished in an earlier session, 'enrolled' = in progress now.
    status        TEXT NOT NULL CHECK (status IN ('completed', 'enrolled')),
    session_label TEXT NOT NULL,
    -- A student can hold one record per subject, so credit points are never double counted.
    UNIQUE (user_id, subject_code)
);