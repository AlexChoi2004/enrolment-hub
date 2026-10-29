"""Subject catalogue business logic: search, filters and prerequisite lookups.

No Flask objects in here, so the rules can be unit tested and reused by the
enrolment, planner and (later) AI features. All SQL uses bound parameters.
"""
import re
from dataclasses import dataclass

SESSIONS = ("Autumn", "Spring")
PREREQ_FILTERS = ("required", "none")
MAX_QUERY_LENGTH = 50
ELECTIVE_CATEGORIES = {"major_elective", "general_elective"}
ELECTIVE_CREDIT_POINTS = 6  # every elective in the supplied data is 6 cp
CODE_PATTERN = re.compile(r"^[A-Za-z0-9]{3,10}$")


class FilterError(ValueError):
    """A search or filter value was malformed."""


@dataclass(frozen=True)
class Filters:
    q: str = ""
    category: str = ""
    session: str = ""
    prereqs: str = ""


def is_valid_code(code):
    return bool(CODE_PATTERN.match(code or ""))


def list_categories(conn):
    rows = conn.execute(
        "SELECT c.category, c.label, c.required_credit_points,"
        " COUNT(s.code) AS subject_count"
        " FROM requirement_categories c"
        " LEFT JOIN subjects s ON s.category = c.category"
        " GROUP BY c.category ORDER BY c.sort_order"
    ).fetchall()
    return [dict(r) for r in rows]


def category_rule(category, subject_count, required_credit_points):
    """Plain-English requirement shown under each category heading."""
    if category in ELECTIVE_CATEGORIES:
        choose = required_credit_points // ELECTIVE_CREDIT_POINTS
        return f"Choose {choose} of {subject_count} \u00b7 {required_credit_points} cp required"
    return f"All {subject_count} required \u00b7 {required_credit_points} cp"


def group_by_category(subjects, categories):
    """Group already-sorted subjects under their category, in degree order."""
    groups = []
    for c in categories:
        items = [s for s in subjects if s["category"] == c["category"]]
        if items:
            groups.append(
                {
                    "category": c["category"],
                    "label": c["label"],
                    "rule": category_rule(c["category"], c["subject_count"], c["required_credit_points"]),
                    "subjects": items,
                }
            )
    return groups


def parse_filters(args, valid_categories):
    """Validate raw query-string values. Raises FilterError if malformed."""
    q = (args.get("q") or "").strip()
    category = (args.get("category") or "").strip()
    session = (args.get("session") or "").strip()
    prereqs = (args.get("prereqs") or "").strip()

    if len(q) > MAX_QUERY_LENGTH:
        raise FilterError(f"Search text must be {MAX_QUERY_LENGTH} characters or fewer.")
    if category and category not in valid_categories:
        raise FilterError("Unknown category.")
    if session and session not in SESSIONS:
        raise FilterError("Unknown session.")
    if prereqs and prereqs not in PREREQ_FILTERS:
        raise FilterError("Unknown prerequisite filter.")
    return Filters(q=q, category=category, session=session, prereqs=prereqs)


def _escape_like(text):
    """Stop % and _ typed by a user from acting as wildcards."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _relations(conn):
    prereqs, unlocks = {}, {}
    for r in conn.execute(
        "SELECT p.subject_code, p.prereq_code, s.name AS name"
        " FROM prerequisites p JOIN subjects s ON s.code = p.prereq_code"
        " ORDER BY p.prereq_code"
    ):
        prereqs.setdefault(r["subject_code"], []).append(
            {"code": r["prereq_code"], "name": r["name"]}
        )
    for r in conn.execute(
        "SELECT p.prereq_code, p.subject_code, s.name AS name"
        " FROM prerequisites p JOIN subjects s ON s.code = p.subject_code"
        " ORDER BY p.subject_code"
    ):
        unlocks.setdefault(r["prereq_code"], []).append(
            {"code": r["subject_code"], "name": r["name"]}
        )
    return prereqs, unlocks


def _attach_relations(conn, rows):
    prereqs, unlocks = _relations(conn)
    out = []
    for row in rows:
        subject = dict(row)
        subject["prerequisites"] = prereqs.get(subject["code"], [])
        subject["unlocks"] = unlocks.get(subject["code"], [])
        out.append(subject)
    return out


BASE_SELECT = (
    "SELECT s.*, c.label AS category_label"
    " FROM subjects s JOIN requirement_categories c ON c.category = s.category"
)


def list_subjects(conn, filters=None):
    filters = filters or Filters()
    sql = BASE_SELECT + " WHERE 1=1"
    params = []
    if filters.q:
        like = f"%{_escape_like(filters.q)}%"
        sql += " AND (s.code LIKE ? ESCAPE '\\' OR s.name LIKE ? ESCAPE '\\')"
        params += [like, like]
    if filters.category:
        sql += " AND s.category = ?"
        params.append(filters.category)
    if filters.session:
        sql += " AND s.sessions_offered IN (?, 'Both')"
        params.append(filters.session)
    if filters.prereqs:
        sql += " AND s.prereq_status = ?"
        params.append(filters.prereqs)
    sql += " ORDER BY c.sort_order, s.name COLLATE NOCASE, s.code"
    return _attach_relations(conn, conn.execute(sql, params).fetchall())


def get_subject(conn, code):
    row = conn.execute(BASE_SELECT + " WHERE s.code = ?", (code,)).fetchone()
    if row is None:
        return None
    return _attach_relations(conn, [row])[0]