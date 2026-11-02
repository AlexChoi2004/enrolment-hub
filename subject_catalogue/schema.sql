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
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_code TEXT NOT NULL REFERENCES subjects(code) ON DELETE CASCADE,
    -- NULL = credit points completed anywhere in the student's degree.
    major_code   TEXT REFERENCES majors(code) ON DELETE CASCADE,
    min_cp       INTEGER NOT NULL CHECK (min_cp > 0)
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

-- Sub-majors: a separate 24 cp block of the degree (not part of the 48 cp major).
-- Each sub-major is made of groups: a "core" group (complete every subject) or a "choose" group (select
-- required_cp credit points from the listed subjects, from a stream, or from one language program).
CREATE TABLE IF NOT EXISTS submajors (
    code           TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    total_cp       INTEGER NOT NULL CHECK (total_cp = 24),
    note           TEXT NOT NULL DEFAULT '',
    source         TEXT NOT NULL,
    academic_year  INTEGER,
    verification   TEXT NOT NULL CHECK (verification IN ('verified', 'supplied', 'unverified'))
);

CREATE TABLE IF NOT EXISTS submajor_groups (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    submajor_code    TEXT NOT NULL REFERENCES submajors(code) ON DELETE CASCADE,
    position         INTEGER NOT NULL,
    kind             TEXT NOT NULL CHECK (kind IN ('core', 'choose')),
    label            TEXT NOT NULL,
    required_cp      INTEGER NOT NULL CHECK (required_cp > 0),
    stream_code      TEXT,
    -- For the language sub-major: the program (for example CBK90494) a group belongs to.
    language_program TEXT,
    language_name    TEXT,
    UNIQUE (submajor_code, position)
);

CREATE TABLE IF NOT EXISTS submajor_group_subjects (
    group_id     INTEGER NOT NULL REFERENCES submajor_groups(id) ON DELETE CASCADE,
    subject_code TEXT NOT NULL REFERENCES subjects(code) ON DELETE CASCADE,
    PRIMARY KEY (group_id, subject_code)
);

-- A stream is a named list of subjects to choose from. It is not a subject itself.
CREATE TABLE IF NOT EXISTS streams (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    cp   INTEGER NOT NULL CHECK (cp > 0),
    note TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS stream_subjects (
    stream_code  TEXT NOT NULL REFERENCES streams(code) ON DELETE CASCADE,
    subject_code TEXT NOT NULL REFERENCES subjects(code) ON DELETE CASCADE,
    PRIMARY KEY (stream_code, subject_code)
);

-- Notes about a prerequisite the app can NOT enforce (for example a subject that is not in this data),
-- shown on the subject but never blocking anything.
CREATE TABLE IF NOT EXISTS prerequisite_notes (
    subject_code TEXT PRIMARY KEY REFERENCES subjects(code) ON DELETE CASCADE,
    note         TEXT NOT NULL
);

-- Short subject descriptions, stored apart from any assessment record.
CREATE TABLE IF NOT EXISTS subject_descriptions (
    subject_code TEXT PRIMARY KEY REFERENCES subjects(code) ON DELETE CASCADE,
    description  TEXT NOT NULL,
    -- Comma-separated style tags (code, theory, group...). My summary of the subject, not a UTS statement.
    style_tags   TEXT NOT NULL DEFAULT '',
    source       TEXT NOT NULL
);

-- One assessment structure = how a subject was assessed according to one source, in one academic year
-- (and session, where known). A subject can have several over time; the one marked current is shown.
-- verification: indicative = read from the UTS Handbook (which itself says "indicative");
--               verified_current = checked against the official subject outline;
--               historical = an older year's information; unverified = nothing confirmed (no tasks);
--               synthetic = invented sample data for the made-up electives.
CREATE TABLE IF NOT EXISTS assessment_structures (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_code  TEXT NOT NULL REFERENCES subjects(code) ON DELETE CASCADE,
    academic_year INTEGER,
    session       TEXT CHECK (session IN ('Autumn', 'Spring')),
    source        TEXT NOT NULL,
    retrieved_on  TEXT,
    verification  TEXT NOT NULL
                  CHECK (verification IN ('verified_current', 'indicative', 'historical', 'unverified', 'synthetic')),
    note          TEXT NOT NULL DEFAULT '',
    is_current    INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1))
);

CREATE TABLE IF NOT EXISTS assessments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    structure_id    INTEGER NOT NULL REFERENCES assessment_structures(id) ON DELETE CASCADE,
    position        INTEGER NOT NULL,
    name            TEXT NOT NULL,
    description     TEXT NOT NULL,
    type            TEXT NOT NULL CHECK (type IN (
                        'quiz', 'exam', 'exercises', 'project', 'report', 'presentation', 'practical',
                        'journal', 'reflection', 'portfolio', 'design', 'essay', 'case_study', 'demonstration')),
    -- NULL = a mandatory task that carries no marks.
    weight          INTEGER CHECK (weight IS NULL OR (weight > 0 AND weight <= 100)),
    groupwork       TEXT NOT NULL CHECK (groupwork IN ('individual', 'group', 'group_individual')),
    -- Weeks are only ever filled in as 'illustrative' until an official outline provides real ones.
    due_week        INTEGER CHECK (due_week IS NULL OR (due_week BETWEEN 1 AND 14)),
    due_week_source TEXT CHECK (due_week_source IS NULL OR due_week_source IN ('illustrative', 'outline')),
    UNIQUE (structure_id, position)
);
