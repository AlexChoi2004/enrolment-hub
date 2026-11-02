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

-- One row per FINISHED attempt at a subject: a pass or a fail. Earlier attempts are never overwritten, so a retake
-- adds a new row. `enrolments` holds the current state per subject (completed or in progress): a pass makes it
-- 'completed', a fail removes the in-progress row. All results are written through enrolment/results.py in one
-- transaction, so the two can never disagree. All data here is simulated, not genuine UTS academic records.
CREATE TABLE IF NOT EXISTS subject_attempts (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject_code   TEXT NOT NULL REFERENCES subjects(code),
    session_label  TEXT NOT NULL,
    attempt_number INTEGER NOT NULL CHECK (attempt_number >= 1),
    outcome        TEXT NOT NULL CHECK (outcome IN ('passed', 'failed')),
    mark           INTEGER CHECK (mark IS NULL OR (mark BETWEEN 0 AND 100)),
    grade          TEXT NOT NULL CHECK (grade IN ('HD', 'D', 'C', 'P', 'FL')),
    source         TEXT NOT NULL DEFAULT 'simulated' CHECK (source IN ('seed', 'simulated')),
    UNIQUE (user_id, subject_code, attempt_number),
    CHECK ((outcome = 'passed' AND grade <> 'FL' AND (mark IS NULL OR mark >= 50))
        OR (outcome = 'failed' AND grade = 'FL' AND (mark IS NULL OR mark < 50)))
);
