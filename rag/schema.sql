-- The knowledge the AI may quote: facts about subjects, majors, sub-majors and how the app works. It holds NO personal
-- data (nothing about any student), only the same public facts the pages show. Rebuilt from the app's own data on seeding.
CREATE TABLE IF NOT EXISTS rag_chunks (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    ref    TEXT NOT NULL UNIQUE,   -- for example subject:41039 or rule:credit-points
    kind   TEXT NOT NULL CHECK (kind IN ('subject', 'major', 'submajor', 'rule')),
    title  TEXT NOT NULL,
    source TEXT NOT NULL,          -- where the facts came from, shown to the student with every citation
    body   TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS rag_fts USING fts5(
    title, body, content = 'rag_chunks', content_rowid = 'id', tokenize = 'porter unicode61'
);

-- How many questions each student has asked recently, so one account cannot flood the model.
CREATE TABLE IF NOT EXISTS ai_usage (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    asked_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
);
