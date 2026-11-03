CREATE TABLE IF NOT EXISTS users (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    -- Login identifier: firstname.lastname@student.uni.edu.au (lower case).
    email                TEXT NOT NULL UNIQUE,
    -- Generated, never typed by the user. Used in URLs instead of the email.
    student_number       TEXT NOT NULL UNIQUE CHECK (length(student_number) BETWEEN 4 AND 20),
    display_name         TEXT NOT NULL,
    -- Only a salted hash is ever stored, never the password itself.
    password_hash        TEXT NOT NULL,
    course_code          TEXT NOT NULL REFERENCES courses(code),
    -- The session the student started in, for example 'Autumn 2027' (their first session).
    commencement_session TEXT NOT NULL,
    -- The major the student has confirmed. NULL until they choose one.
    major_code           TEXT REFERENCES majors(code),
    -- The 24 cp sub-major the student has confirmed (NULL until they choose one), and, for the language
    -- sub-major only, the one language program they picked.
    submajor_code        TEXT REFERENCES submajors(code),
    submajor_language    TEXT,
    -- 1 = the student took 24 cp of general electives INSTEAD of a sub-major (the two are alternatives).
    general_electives    INTEGER NOT NULL DEFAULT 0 CHECK (general_electives IN (0, 1)),
    -- The session this student is "in" right now. The semester simulator moves it forward; everything else
    -- (which sessions are open to enrol in, the planning window, the timetable) follows it.
    current_session      TEXT NOT NULL DEFAULT 'Autumn 2027',
    -- AI mode is off until the student turns it on; nothing is sent to any model while it is off.
    ai_mode              INTEGER NOT NULL DEFAULT 0 CHECK (ai_mode IN (0, 1)),
    failed_logins        INTEGER NOT NULL DEFAULT 0,
    -- Unix time until which logins are refused after too many failures (0 = not locked).
    locked_until         INTEGER NOT NULL DEFAULT 0
);
