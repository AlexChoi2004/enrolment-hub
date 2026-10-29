CREATE TABLE IF NOT EXISTS users (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    student_number TEXT NOT NULL UNIQUE CHECK (length(student_number) BETWEEN 4 AND 20),
    display_name   TEXT NOT NULL,
    -- Only a salted hash is ever stored, never the password itself.
    password_hash  TEXT NOT NULL,
    course_code    TEXT NOT NULL REFERENCES courses(code),
    failed_logins  INTEGER NOT NULL DEFAULT 0,
    -- Unix time until which logins are refused after too many failures (0 = not locked).
    locked_until   INTEGER NOT NULL DEFAULT 0
);