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

-- A subject's prerequisites are ANDed together, group by group. Rows of one subject that share an
-- alt_group are alternatives (OR): completing any one of them satisfies that group.
-- concurrent = 1 marks a corequisite: it may also be satisfied by being enrolled at the same time.
CREATE TABLE IF NOT EXISTS prerequisites (
    subject_code TEXT NOT NULL REFERENCES subjects(code) ON DELETE CASCADE,
    prereq_code  TEXT NOT NULL REFERENCES subjects(code) ON DELETE CASCADE,
    alt_group    INTEGER NOT NULL DEFAULT 0,
    concurrent   INTEGER NOT NULL DEFAULT 0 CHECK (concurrent IN (0, 1)),
    PRIMARY KEY (subject_code, prereq_code),
    CHECK (subject_code <> prereq_code)
);

-- A minimum number of completed credit points within a major. Separate from subject prerequisites,
-- so reaching the threshold can never stand in for a required subject.
CREATE TABLE IF NOT EXISTS credit_requirements (
    subject_code TEXT NOT NULL REFERENCES subjects(code) ON DELETE CASCADE,
    major_code   TEXT NOT NULL REFERENCES majors(code) ON DELETE CASCADE,
    min_cp       INTEGER NOT NULL CHECK (min_cp > 0),
    PRIMARY KEY (subject_code, major_code)
);

-- The majors a student can choose from. Every major is worth 48 cp: core + options.
CREATE TABLE IF NOT EXISTS majors (
    code        TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    core_cp     INTEGER NOT NULL CHECK (core_cp >= 0),
    options_cp  INTEGER NOT NULL CHECK (options_cp >= 0),
    CHECK (core_cp + options_cp = 48)
);

-- Which subjects belong to which major, and whether they are compulsory (core) or chosen from
-- a list (option) in that major. A subject is stored once even if several majors use it.
CREATE TABLE IF NOT EXISTS major_subjects (
    major_code   TEXT NOT NULL REFERENCES majors(code) ON DELETE CASCADE,
    subject_code TEXT NOT NULL REFERENCES subjects(code) ON DELETE CASCADE,
    role         TEXT NOT NULL CHECK (role IN ('core', 'option')),
    PRIMARY KEY (major_code, subject_code)
);

-- Notes about a prerequisite the app can NOT enforce (for example a subject that is not in this data),
-- shown on the subject but never blocking anything.
CREATE TABLE IF NOT EXISTS prerequisite_notes (
    subject_code TEXT PRIMARY KEY REFERENCES subjects(code) ON DELETE CASCADE,
    note         TEXT NOT NULL
);