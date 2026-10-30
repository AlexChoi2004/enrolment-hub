CREATE TABLE IF NOT EXISTS classes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_code TEXT NOT NULL REFERENCES subjects(code),
    -- The same weekly pattern runs every year, so classes belong to a season, not one session.
    season       TEXT NOT NULL CHECK (season IN ('Autumn', 'Spring')),
    kind         TEXT NOT NULL CHECK (kind IN ('lecture', 'tutorial')),
    name         TEXT NOT NULL,
    day          TEXT NOT NULL CHECK (day IN ('Mon', 'Tue', 'Wed', 'Thu', 'Fri')),
    start_hour   INTEGER NOT NULL CHECK (start_hour BETWEEN 8 AND 18),
    duration     INTEGER NOT NULL CHECK (duration BETWEEN 1 AND 3),
    room         TEXT NOT NULL,
    CHECK (start_hour + duration <= 19)
);

CREATE INDEX IF NOT EXISTS idx_classes_subject_season ON classes (subject_code, season);

-- The tutorial a student picked for a subject they are enrolled in. Lectures are automatic.
CREATE TABLE IF NOT EXISTS class_choices (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject_code TEXT NOT NULL REFERENCES subjects(code),
    class_id     INTEGER NOT NULL REFERENCES classes(id),
    UNIQUE (user_id, subject_code)
);