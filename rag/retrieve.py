"""Find the sources that can answer a question, and decide whether there is enough to answer at all.

The question is cleaned into plain words (so no search operator a user types can do anything), the sources are ranked with
SQLite full-text search, and a source only counts if it actually contains most of the question's content words. When nothing
does, the answer is "Not enough context" and the model is never asked, so it has no chance to guess.
"""
import re

STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "am", "do", "does", "did", "of", "to", "in", "on", "for", "with",
    "and", "or", "if", "it", "its", "this", "that", "these", "those", "i", "me", "my", "we", "you", "your", "can", "could", "should",
    "would", "will", "what", "which", "who", "whom", "how", "why", "when", "where", "there", "any", "about", "as", "at", "by", "from",
    "have", "has", "had", "so", "than", "then", "also", "tell", "please", "explain", "get", "much", "many", "not", "no", "yes",
}
SYNONYMS = {  # words a student might use for what the sources call something else
    "require": "prerequisite", "requires": "prerequisite", "required": "prerequisite", "requirement": "prerequisite",
    "requirements": "prerequisite", "need": "prerequisite", "needs": "prerequisite", "needed": "prerequisite", "before": "prerequisite",
    "fail": "failed", "failing": "failed", "flunk": "failed", "retake": "retake", "repeat": "retake",
    "switch": "swap", "change": "swap", "changing": "swap", "swapping": "swap", "switching": "swap",
    "graduate": "graduation", "graduating": "graduation", "cost": "tuition", "costs": "tuition", "money": "tuition", "pay": "tuition",
    "register": "registration", "registering": "registration", "signup": "sign", "login": "account",
    "hard": "load", "difficulty": "load", "difficult": "load", "easy": "load", "workload": "workload", "busy": "workload",
}
MAX_QUESTION = 500
MAX_TOKENS = 12
MIN_COVERAGE = 0.5  # a source must contain at least this share of the question's content words
LIMIT = 4


def stem(word):
    """A very small stemmer, used only to compare words (the search itself uses the database's)."""
    w = word.lower()
    for suffix in ("ing", "ed", "es", "s"):
        if w.endswith(suffix) and len(w) - len(suffix) >= 4:
            w = w[: -len(suffix)]
            break
    return w[:-1] if w.endswith("e") and len(w) > 4 else w  # so require, requires and required all meet at "requir"


def tokens(question):
    """The content words of a question: letters and digits only, no stopwords, no repeats, at most MAX_TOKENS."""
    seen, out = set(), []
    for word in re.findall(r"[a-z0-9]+", question.lower()[:MAX_QUESTION]):
        if word in STOPWORDS or word in seen or (len(word) < 2 and not word.isdigit()):  # a lone digit matters: Programming 2
            continue
        seen.add(word)
        out.append(word)
    return out[:MAX_TOKENS]


def _expand(words):
    """Each word plus the word the sources use for it. Quoted, so nothing typed can act as a search operator."""
    terms = []
    for w in words:
        for t in (w, SYNONYMS.get(w)):
            if t and t not in terms:
                terms.append(t)
    return terms


def _coverage(words, text):
    have = {stem(w) for w in re.findall(r"[a-z0-9]+", text.lower())}
    matched = sum(1 for w in words if stem(w) in have or (w in SYNONYMS and stem(SYNONYMS[w]) in have))
    return matched / len(words) if words else 0.0


def search(conn, question, limit=LIMIT):
    """{"tokens": [...], "hits": [source, ...], "sufficient": bool}. A hit is a dict with ref, title, source, body, coverage."""
    words = tokens(question)
    if not words:
        return {"tokens": [], "hits": [], "sufficient": False}
    match = " OR ".join('"' + t + '"' for t in _expand(words))
    rows = conn.execute(
        "SELECT c.ref, c.title, c.source, c.body, c.kind FROM rag_fts f JOIN rag_chunks c ON c.id = f.rowid"
        " WHERE rag_fts MATCH ? ORDER BY bm25(rag_fts, 8.0, 1.0) LIMIT 30", (match,)
    ).fetchall()
    hits = []
    for r in rows:
        cov = _coverage(words, r["title"] + " " + r["body"])
        if cov >= MIN_COVERAGE:
            hits.append({"ref": r["ref"], "title": r["title"], "source": r["source"], "body": r["body"], "kind": r["kind"],
                         "coverage": cov, "title_coverage": _coverage(words, r["title"])})
    asked_sub, asked_major = {"sub", "major"} <= set(words), "major" in words

    def kind_fit(h):  # asking about a (sub-)major should put that major's own structure first
        return 1 if (h["kind"] == "submajor" and asked_sub) or (h["kind"] == "major" and asked_major and not asked_sub) else 0

    # A source whose TITLE matches the question is the one being asked about; the title counts for extra.
    hits.sort(key=lambda h: -(h["coverage"] + 0.5 * h["title_coverage"] + 0.3 * kind_fit(h)))  # stable on ties
    hits = hits[:limit]
    return {"tokens": words, "hits": hits, "sufficient": bool(hits)}
