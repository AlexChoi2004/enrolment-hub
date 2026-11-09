"""Subject catalogue business logic: search, filters and prerequisite lookups.

No Flask objects in here, so the rules can be unit tested and reused by the
enrolment, planner and (later) AI features. All SQL uses bound parameters.
"""
import re
from dataclasses import dataclass

from features.subject_catalogue.program_text import HANDBOOK_YEAR, aos_url
from features.subject_catalogue.assessments import load_assessment_info
from features.subject_catalogue.assessment_load import assessment_load_map

SESSIONS = ("Autumn", "Spring")
PREREQ_FILTERS = ("required", "none")
STATUS_FILTERS = ("completed", "enrolled", "available", "blocked", "retake")
MAX_QUERY_LENGTH = 50
ELECTIVE_CREDIT_POINTS = 6  # every major option in the supplied data is 6 cp
CODE_PATTERN = re.compile(r"^[A-Za-z0-9]{3,10}$")
MAJOR_CODE_PATTERN = re.compile(r"^MAJ[0-9]{5}$")
NON_MAJOR_CATEGORIES = ("core", "honours_core", "general_elective")  # never tied to one major
SUBMAJOR_CODE_PATTERN = re.compile(r"^SMJ[0-9]{5}$")
LANGUAGE_CODE_PATTERN = re.compile(r"^CBK[0-9]{5}$")
SUBMAJOR_CREDIT_POINTS = 24
MAJOR_CREDIT_POINTS = 48  # every major is worth 48 cp
DEGREE_CREDIT_POINTS = 192


class FilterError(ValueError):
    """A search or filter value was malformed."""


@dataclass(frozen=True)
class Filters:
    q: str = ""
    category: str = ""
    session: str = ""
    prereqs: str = ""
    status: str = ""


def is_valid_code(code):
    return bool(CODE_PATTERN.match(code or ""))


def is_valid_major_code(code):
    return bool(MAJOR_CODE_PATTERN.match(code or ""))


def is_valid_submajor_code(code):
    return bool(SUBMAJOR_CODE_PATTERN.match(code or ""))


def is_valid_language_code(code):
    return bool(LANGUAGE_CODE_PATTERN.match(code or ""))


def is_choose_category(category):
    """Categories where the student selects some credit points from a list (rather than taking every subject)."""
    return category in ("major_elective", "td_elective", "general_elective") or (category or "").startswith("sub_choose_")


# --- majors --------------------------------------------------------------------------------------

def _major_row(conn, code):
    row = conn.execute("SELECT code, name, core_cp, options_cp, handbook_url FROM majors WHERE code = ?", (code,)).fetchone()
    return dict(row) if row else None


def list_majors(conn):
    """Every major with a short summary of its structure (no subject lists)."""
    majors = []
    for r in conn.execute("SELECT code, name, core_cp, options_cp, handbook_url FROM majors ORDER BY name COLLATE NOCASE"):
        m = dict(r)
        counts = conn.execute(
            "SELECT SUM(role = 'core') AS core, SUM(role = 'option') AS options FROM major_subjects WHERE major_code = ?",
            (m["code"],),
        ).fetchone()
        m.update(core_count=counts["core"] or 0, option_count=counts["options"] or 0,
                 choose=m["options_cp"] // ELECTIVE_CREDIT_POINTS)
        majors.append(m)
    return majors


def get_major(conn, code):
    """One major with its compulsory (core) and optional subjects listed."""
    major = _major_row(conn, code) if code else None
    if major is None:
        return None
    for role, key in (("core", "core"), ("option", "options")):
        major[key] = [
            dict(r) for r in conn.execute(
                "SELECT s.code, s.name, s.credit_points, s.sessions_offered, s.handbook_url FROM major_subjects ms"
                " JOIN subjects s ON s.code = ms.subject_code WHERE ms.major_code = ? AND ms.role = ?"
                " ORDER BY s.name COLLATE NOCASE",
                (code, role),
            )
        ]
    major["choose"] = major["options_cp"] // ELECTIVE_CREDIT_POINTS
    return major


def user_major(conn, user_id):
    """The student's confirmed major (with its subject lists), or None."""
    row = conn.execute("SELECT major_code FROM users WHERE id = ?", (user_id,)).fetchone()
    return get_major(conn, row["major_code"]) if row and row["major_code"] else None


def _load_submajor(conn, row, language=None):
    """One sub-major with its groups. `language` picks the language group of the LOTE sub-major (None = none picked)."""
    sub = dict(row)
    groups = []
    for g in conn.execute("SELECT * FROM submajor_groups WHERE submajor_code = ? ORDER BY position", (sub["code"],)):
        group = dict(g)
        group["category"] = "sub_core" if g["kind"] == "core" else f"sub_choose_{g['id']}"
        group["subjects"] = [
            dict(r) for r in conn.execute(
                "SELECT s.code, s.name, s.credit_points, s.sessions_offered, s.handbook_url FROM subjects s WHERE s.code IN"
                " (SELECT subject_code FROM submajor_group_subjects WHERE group_id = ?"
                "  UNION SELECT subject_code FROM stream_subjects WHERE stream_code = ?)"
                " ORDER BY s.name COLLATE NOCASE",
                (g["id"], g["stream_code"] or ""),
            )
        ]
        group["stream"] = None
        if g["stream_code"]:
            stream = conn.execute("SELECT code, name, note FROM streams WHERE code = ?", (g["stream_code"],)).fetchone()
            group["stream"] = dict(stream) if stream else None
            if group["stream"]:  # the stream is linked at the year of the page it is listed on (Humanitarian Engineering is the 2026 page)
                group["stream"]["handbook_url"] = aos_url(g["stream_code"], HANDBOOK_YEAR.get(sub["code"]))
        groups.append(group)
    sub["all_groups"] = groups
    sub["is_language"] = any(g["language_program"] for g in groups)
    sub["languages"] = [
        {"code": g["language_program"], "name": g["language_name"], "subjects": g["subjects"]}
        for g in groups if g["language_program"]
    ]
    sub["language"] = language
    sub["language_name"] = next((l["name"] for l in sub["languages"] if l["code"] == language), None)
    # The groups that apply to this student: every group, except that only the chosen language's group counts.
    sub["groups"] = [g for g in groups if not g["language_program"] or g["language_program"] == language]
    sub["needs_language"] = sub["is_language"] and language is None
    return sub


def list_submajors(conn):
    """Every sub-major with a one-line summary of its structure."""
    out = []
    for row in conn.execute("SELECT * FROM submajors ORDER BY name COLLATE NOCASE"):
        sub = _load_submajor(conn, row)
        sub["core_cp"] = sum(g["required_cp"] for g in sub["all_groups"] if g["kind"] == "core")
        sub["choose_cp"] = 24 - sub["core_cp"] if not sub["is_language"] else 24
        out.append(sub)
    return out


def get_submajor(conn, code, language=None):
    row = conn.execute("SELECT * FROM submajors WHERE code = ?", (code,)).fetchone() if code else None
    return _load_submajor(conn, row, language) if row else None


def user_submajor(conn, user_id):
    """The student's confirmed sub-major (with the groups that apply to them), or None."""
    row = conn.execute("SELECT submajor_code, submajor_language FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row or not row["submajor_code"]:
        return None
    return get_submajor(conn, row["submajor_code"], row["submajor_language"])


def uses_general_electives(conn, user_id):
    """True when the student took 24 cp of general electives instead of a sub-major (the two are alternatives)."""
    row = conn.execute("SELECT general_electives FROM users WHERE id = ?", (user_id,)).fetchone()
    return bool(row and row["general_electives"])


def submajor_subject_codes(conn, user_id):
    """Every subject that counts towards the student's sub-major (only their chosen language for LOTE)."""
    sub = user_submajor(conn, user_id)
    return {s["code"] for g in sub["groups"] for s in g["subjects"]} if sub else set()


def degree_subjects(conn, user_id):
    """Every subject, with the category it counts as FOR THIS STUDENT.

    Core, honours core and general electives are the same for everyone. A major subject counts as
    major core or a major elective only if it belongs to the student's chosen major; otherwise
    it is not part of their degree (category None).
    """
    row = conn.execute("SELECT major_code, general_electives FROM users WHERE id = ?", (user_id,)).fetchone()
    major_code = row["major_code"] if row else None
    uses_electives = bool(row and row["general_electives"])
    roles = {}
    if major_code:
        roles = {r["subject_code"]: r["role"] for r in conn.execute(
            "SELECT subject_code, role FROM major_subjects WHERE major_code = ?", (major_code,))}
    sub = user_submajor(conn, user_id)
    sub_roles = {}  # subject -> the sub-major category it would count in
    for g in (sub["groups"] if sub else []):
        for s in g["subjects"]:
            sub_roles.setdefault(s["code"], g["category"])
    chosen_electives = set()
    if uses_electives:  # subjects the student chose to count as general electives instead of losing them
        chosen_electives = {r[0] for r in conn.execute("SELECT subject_code FROM elective_credits WHERE user_id = ?", (user_id,))}
    subjects = []
    for r in conn.execute("SELECT * FROM subjects"):
        subject = dict(r)
        stored = subject["category"]
        if stored == "general_elective":  # counts only if the student chose electives instead of a sub-major
            effective = "general_elective" if uses_electives else None
        elif stored == "td_elective":  # a transdisciplinary subject: the electives' 6 cp stream slot, or the stream of a sub-major that lists it (Humanitarian Engineering)
            effective = "td_elective" if uses_electives else sub_roles.get(subject["code"])
        elif stored in NON_MAJOR_CATEGORIES:
            effective = stored
        elif subject["code"] in roles:
            effective = "major_core" if roles[subject["code"]] == "core" else "major_elective"
        elif subject["code"] in sub_roles:
            effective = sub_roles[subject["code"]]
        elif subject["code"] in chosen_electives:
            effective = "general_elective"
        else:
            effective = None
        # A subject that is in both the major and the sub-major counts once, in the major: it is flagged, not doubled.
        subject["overlaps_major"] = subject["code"] in roles and subject["code"] in sub_roles
        subject["stored_category"] = stored
        subject["category"] = effective
        subject["in_degree"] = effective is not None
        subjects.append(subject)
    return subjects


def degree_categories(conn, user_id):
    """The requirement sections that apply to this student, in order, with their credit points."""
    base = {r["category"]: dict(r) for r in conn.execute(
        "SELECT category, label, required_credit_points, sort_order FROM requirement_categories")}
    major = user_major(conn, user_id)
    categories = [base["core"], base["honours_core"]]
    if major:
        categories.append({"category": "major_core", "label": "Major core",
                           "required_credit_points": major["core_cp"], "sort_order": 3})
        if major["options_cp"]:
            categories.append({"category": "major_elective", "label": "Major electives",
                               "required_credit_points": major["options_cp"], "sort_order": 4})
    sub = user_submajor(conn, user_id)
    if sub:
        core_cp = sum(g["required_cp"] for g in sub["groups"] if g["kind"] == "core")
        if core_cp:
            categories.append({"category": "sub_core", "label": "Sub-major core",
                               "required_credit_points": core_cp, "sort_order": 5})
        for g in sub["groups"]:
            if g["kind"] == "choose":
                label = (f"Sub-major language: {g['language_name']}" if g["language_program"]
                         else "Sub-major " + g["label"][0].lower() + g["label"][1:])
                categories.append({"category": g["category"], "label": label,
                                   "required_credit_points": g["required_cp"], "sort_order": 5 + g["position"]})
    if uses_general_electives(conn, user_id):  # the 24 cp choice is 6 cp from the Transdisciplinary Electives stream plus 18 cp of free electives
        categories.append(base["td_elective"])
        categories.append(base["general_elective"])
    counts = {}
    for subject in degree_subjects(conn, user_id):
        if subject["in_degree"]:
            counts[subject["category"]] = counts.get(subject["category"], 0) + 1
    for c in categories:
        c["subject_count"] = counts.get(c["category"], 0)
    return categories


def list_categories(conn, user_id=None):
    """The requirement sections. With a student, only the sections that apply to them."""
    if user_id is not None:
        return degree_categories(conn, user_id)
    rows = conn.execute(
        "SELECT c.category, c.label, c.required_credit_points,"
        " COUNT(s.code) AS subject_count"
        " FROM requirement_categories c"
        " LEFT JOIN subjects s ON s.category = c.category"
        " WHERE c.category <> 'major_other'"
        " GROUP BY c.category ORDER BY c.sort_order"
    ).fetchall()
    return [dict(r) for r in rows]


def load_prerequisites(conn):
    """{subject: [group, ...]}. A subject needs EVERY group; a group is satisfied by ANY of its codes.

    group = {"codes": [prerequisite codes (alternatives)], "concurrent": True if it may be taken at the same time}
    """
    groups = {}
    for r in conn.execute(
        "SELECT subject_code, prereq_code, alt_group, concurrent FROM prerequisites"
        " ORDER BY subject_code, alt_group, prereq_code"
    ):
        by_group = groups.setdefault(r["subject_code"], {})
        group = by_group.setdefault(r["alt_group"], {"codes": [], "concurrent": bool(r["concurrent"])})
        group["codes"].append(r["prereq_code"])
    return {code: [by_group[g] for g in sorted(by_group)] for code, by_group in groups.items()}


def prerequisite_lines(conn, code):
    """One line per requirement: all lines must be met, and 'or' inside a line means any one will do."""
    names = {r["code"]: r["name"] for r in conn.execute("SELECT code, name FROM subjects")}
    lines = [group_text(names, g) for g in load_prerequisites(conn).get(code, [])]
    for need in load_credit_requirements(conn).get(code, []):
        where = need["major_name"] if need["major_code"] else "your degree"
        lines.append(f"{need['min_cp']} credit points completed in {where}")
    return lines


def load_credit_requirements(conn):
    """{subject: [{"major_code", "major_name", "min_cp"}]}: completed credit points needed within a major,
    or within the whole degree (major_code None, shown as "your degree")."""
    requirements = {}
    for r in conn.execute(
        "SELECT c.subject_code, c.major_code, m.name AS major_name, c.min_cp FROM credit_requirements c"
        " LEFT JOIN majors m ON m.code = c.major_code ORDER BY c.subject_code, c.major_code, c.id"
    ):
        requirements.setdefault(r["subject_code"], []).append(
            {"major_code": r["major_code"], "major_name": r["major_name"] or "your degree", "min_cp": r["min_cp"]}
        )
    return requirements


def group_text(names, group):
    """'31250 Introduction to Data Analytics' or '(48024 Programming 2 or 41040 Introduction to AI)'."""
    parts = [f"{c} {names[c]}" for c in group["codes"]]
    return parts[0] if len(parts) == 1 else "(" + " or ".join(parts) + ")"


ELECTIVE_CATEGORIES_SIMPLE = {"major_elective", "td_elective", "general_elective"}


def category_rule(category, subject_count, required_credit_points):
    """Plain-English requirement shown under each category heading."""
    if category.startswith("sub_choose_"):
        return f"Choose {required_credit_points} cp from {subject_count} subjects"
    if category in ELECTIVE_CATEGORIES_SIMPLE:
        choose = required_credit_points // ELECTIVE_CREDIT_POINTS
        return f"Choose {choose} of {subject_count} \u00b7 {required_credit_points} cp required"
    return f"All {subject_count} required \u00b7 {required_credit_points} cp"


def attach_status(subjects, progress):
    """Add the student's status, a one-line note and met/not-met flags to each subject."""
    records = progress["records"]
    for subject in subjects:
        info = progress["subjects"][subject["code"]]
        subject["status"] = info["status"]
        subject["note"] = info["note"]
        subject["reasons"] = info["reasons"]
        subject["retake"] = info["retake"]
        subject["attempts"] = info["attempts"]
        subject["last_failed"] = info["last_failed"]
        subject["enrol_sessions"] = info["sessions"]
        subject["move_sessions"] = info["move_sessions"]
        for prereq in subject["prerequisites"]:
            prereq["state"] = records.get(prereq["code"], "none")  # completed, enrolled or none
        for requirement in subject["requirements"]:
            for alt in requirement["alternatives"]:
                alt["state"] = records.get(alt["code"], "none")
            requirement["met"] = any(
                a["state"] == "completed" or (requirement["concurrent"] and a["state"] == "enrolled")
                for a in requirement["alternatives"]
            )
        for credit in subject["credit_requirements"]:
            credit["have"] = progress["major_credit"].get(credit["major_code"], 0)
            credit["met"] = credit["have"] >= credit["min_cp"]
    return subjects


def filter_by_status(subjects, status):
    if status == "retake":  # failed and not yet passed
        return [s for s in subjects if s.get("retake")]
    return [s for s in subjects if s["status"] == status] if status else subjects


def group_by_category(subjects, categories, progress=None):
    """Group already-sorted subjects under their category, in degree order.

    With a student's progress, each heading also reports how far they are through the
    requirement, and a finished requirement is marked complete (the page greys it out).
    """
    groups = []
    for c in categories:
        items = [s for s in subjects if s["category"] == c["category"]]
        if not items:
            continue
        rule = category_rule(c["category"], c["subject_count"], c["required_credit_points"])
        complete, note = False, ""
        if progress is not None:
            p = progress["categories"][c["category"]]
            if c["category"].startswith("sub_choose_"):
                rule = (f"Choose {c['required_credit_points']} cp from {c['subject_count']} subjects \u00b7 "
                        f"{p['counted_cp']} of {c['required_credit_points']} cp chosen")
                complete = p["counted_cp"] >= c["required_credit_points"]
                if complete:
                    note = "Requirement complete: you can't enrol in any more subjects for this group."
            elif c["category"] in ELECTIVE_CATEGORIES_SIMPLE:
                choose = c["required_credit_points"] // ELECTIVE_CREDIT_POINTS
                chosen = p["completed"] + p["enrolled"]
                rule = f"Choose {choose} of {c['subject_count']} \u00b7 {chosen} of {choose} chosen"
                complete = chosen >= choose
                if complete:
                    note = f"Requirement complete: you can't enrol in any more {c['label'].lower()}."
            else:
                rule = (
                    f"All {c['subject_count']} required \u00b7 "
                    f"{p['completed']} completed, {p['enrolled']} in progress"
                )
                complete = p["completed"] >= c["subject_count"]
                if complete:
                    note = "Everything in this section is completed."
        groups.append(
            {
                "category": c["category"],
                "label": c["label"],
                "rule": rule,
                "complete": complete,
                "note": note,
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
    status = (args.get("status") or "").strip()

    if len(q) > MAX_QUERY_LENGTH:
        raise FilterError(f"Search text must be {MAX_QUERY_LENGTH} characters or fewer.")
    if category and category not in valid_categories:
        raise FilterError("Unknown category.")
    if session and session not in SESSIONS:
        raise FilterError("Unknown session.")
    if prereqs and prereqs not in PREREQ_FILTERS:
        raise FilterError("Unknown prerequisite filter.")
    if status and status not in STATUS_FILTERS:
        raise FilterError("Unknown status filter.")
    return Filters(q=q, category=category, session=session, prereqs=prereqs, status=status)


def _escape_like(text):
    """Stop % and _ typed by a user from acting as wildcards."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _relations(conn):
    names = {r["code"]: r["name"] for r in conn.execute("SELECT code, name FROM subjects")}
    rules = load_prerequisites(conn)
    prereqs, requirements, unlocks = {}, {}, {}
    for subject, groups in rules.items():
        requirements[subject] = [
            {"alternatives": [{"code": c, "name": names[c]} for c in g["codes"]], "concurrent": g["concurrent"]}
            for g in groups
        ]
        prereqs[subject] = [
            {"code": c, "name": names[c], "concurrent": g["concurrent"]} for g in groups for c in g["codes"]
        ]
        for g in groups:
            for c in g["codes"]:
                unlocks.setdefault(c, []).append({"code": subject, "name": names[subject]})
    for lst in unlocks.values():
        lst.sort(key=lambda u: u["code"])
    return prereqs, requirements, unlocks


def _attach_relations(conn, rows):
    prereqs, requirements, unlocks = _relations(conn)
    credit = load_credit_requirements(conn)
    notes = {r["subject_code"]: r["note"] for r in conn.execute("SELECT subject_code, note FROM prerequisite_notes")}
    assessments = load_assessment_info(conn)
    assessment_load = assessment_load_map(load_prerequisites(conn), assessments, [dict(r) for r in rows])
    submajors = {}
    for r in conn.execute(
        "SELECT gs.subject_code, sm.code, sm.name, g.kind, g.language_name FROM submajor_group_subjects gs"
        " JOIN submajor_groups g ON g.id = gs.group_id JOIN submajors sm ON sm.code = g.submajor_code"
        " ORDER BY sm.name COLLATE NOCASE"
    ):
        submajors.setdefault(r["subject_code"], []).append(
            {"code": r["code"], "name": r["name"], "role": "core" if r["kind"] == "core" else "option",
             "language": r["language_name"]}
        )
    majors = {}
    for r in conn.execute(
        "SELECT ms.subject_code, m.code, m.name, ms.role FROM major_subjects ms JOIN majors m ON m.code = ms.major_code"
        " ORDER BY m.name COLLATE NOCASE"
    ):
        majors.setdefault(r["subject_code"], []).append({"code": r["code"], "name": r["name"], "role": r["role"]})
    out = []
    for row in rows:
        subject = dict(row)
        code = subject["code"]
        subject["majors"] = majors.get(code, [])
        subject["submajors"] = submajors.get(code, [])
        subject["prerequisites"] = [dict(p) for p in prereqs.get(code, [])]  # every alternative, flat
        subject["requirements"] = [
            {"alternatives": [dict(a) for a in r["alternatives"]], "concurrent": r["concurrent"]}
            for r in requirements.get(code, [])
        ]
        subject["credit_requirements"] = [dict(c) for c in credit.get(code, [])]
        subject["unlocks"] = unlocks.get(code, [])
        subject["prerequisite_note"] = notes.get(code)  # a lead the app cannot enforce
        info = assessments.get(code)
        subject["summary"] = info["summary"] if info else ""
        subject["style_tags"] = info["tags"] if info else []
        subject["assessment"] = info
        subject["assessment_load"] = assessment_load.get(code, {"score": None, "reasons": []})  # the app's estimate, not UTS's
        out.append(subject)
    return out


BASE_SELECT = (
    "SELECT s.*, c.label AS category_label"
    " FROM subjects s JOIN requirement_categories c ON c.category = s.category"
)


def list_subjects(conn, filters=None, user_id=None):
    """Search the catalogue. With a student, only subjects in their degree are returned, each
    carrying the category it counts as for them (so a major's subjects appear as major core or
    major electives)."""
    filters = filters or Filters()
    sql = BASE_SELECT + " WHERE 1=1"
    params = []
    if user_id is None:
        sql += " AND s.category <> 'major_other'"  # without a student, the original (ESD) subjects
    if filters.q:
        like = f"%{_escape_like(filters.q)}%"
        sql += " AND (s.code LIKE ? ESCAPE '\\' OR s.name LIKE ? ESCAPE '\\')"
        params += [like, like]
    if filters.category and user_id is None:
        sql += " AND s.category = ?"
        params.append(filters.category)
    if filters.session:
        sql += " AND s.sessions_offered IN (?, 'Both')"
        params.append(filters.session)
    if filters.prereqs:
        sql += " AND s.prereq_status = ?"
        params.append(filters.prereqs)
    sql += " ORDER BY c.sort_order, s.name COLLATE NOCASE, s.code"
    subjects = _attach_relations(conn, conn.execute(sql, params).fetchall())
    if user_id is None:
        return subjects

    labels = {c["category"]: (c["label"], c["sort_order"]) for c in degree_categories(conn, user_id)}
    effective = {s["code"]: s["category"] for s in degree_subjects(conn, user_id)}
    visible = []
    for subject in subjects:
        category = effective.get(subject["code"])
        if category is None or (filters.category and category != filters.category):
            continue
        subject["category"] = category
        subject["category_label"] = labels[category][0]
        subject["_order"] = labels[category][1]
        subject["unlocks"] = [u for u in subject["unlocks"] if effective.get(u["code"])]  # only what they could take
        visible.append(subject)
    visible.sort(key=lambda s: (s["_order"], s["name"].lower(), s["code"]))
    return visible


def get_subject(conn, code, user_id=None):
    row = conn.execute(BASE_SELECT + " WHERE s.code = ?", (code,)).fetchone()
    if row is None:
        return None
    subject = _attach_relations(conn, [row])[0]
    if user_id is not None:
        everything = {s["code"]: s for s in degree_subjects(conn, user_id)}
        subject["unlocks"] = [u for u in subject["unlocks"] if everything[u["code"]]["in_degree"]]
        current = everything[code]
        labels = {c["category"]: c["label"] for c in degree_categories(conn, user_id)}
        if current["in_degree"]:
            subject["category"] = current["category"]
            subject["category_label"] = labels[current["category"]]
        else:
            subject["category_label"] = "Not in your degree"
    return subject
