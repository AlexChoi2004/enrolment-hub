CREATE TABLE IF NOT EXISTS courses (
    code          TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    major_code    TEXT NOT NULL,
    major_name    TEXT NOT NULL,
    handbook_year INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS requirement_categories (
    category                TEXT PRIMARY KEY,
    label                   TEXT NOT NULL,
    required_credit_points  INTEGER NOT NULL CHECK (required_credit_points >= 0),
    sort_order              INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS subjects (
    code             TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    credit_points    INTEGER NOT NULL CHECK (credit_points > 0),
    category         TEXT NOT NULL REFERENCES requirement_categories(category),
    -- Offerings are illustrative for every subject (not verified handbook data).
    sessions_offered TEXT NOT NULL CHECK (sessions_offered IN ('Autumn', 'Spring', 'Both')),
    description      TEXT NOT NULL DEFAULT '',
    -- 1 = invented for this prototype (generated general electives).
    is_synthetic     INTEGER NOT NULL DEFAULT 0 CHECK (is_synthetic IN (0, 1)),
    -- 'required' = the supplied data lists prerequisites for this subject.
    -- 'none'     = the supplied data lists no prerequisites for this subject.
    -- 'unknown'  = prerequisites genuinely not known (keeps "unknown" distinct from "none").
    prereq_status    TEXT NOT NULL DEFAULT 'none'
                     CHECK (prereq_status IN ('required', 'none', 'unknown'))
);

CREATE TABLE IF NOT EXISTS prerequisites (
    subject_code TEXT NOT NULL REFERENCES subjects(code) ON DELETE CASCADE,
    prereq_code  TEXT NOT NULL REFERENCES subjects(code) ON DELETE CASCADE,
    PRIMARY KEY (subject_code, prereq_code),
    CHECK (subject_code <> prereq_code)
);