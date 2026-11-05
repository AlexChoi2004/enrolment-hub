"""Build the knowledge the AI may quote from the app's own data, as small cited sources with full-text search.

Every source is a public fact the pages already show: nothing about any student is ever put here. A source records where its
facts came from, and the wording keeps the caveats (indicative, illustrative, unverified), so an answer built from it cannot
overclaim. Unconfirmed assessment information comes through subject_catalogue.assessments.ai_context, so it still says
"Not enough context" and the unconfirmed student-reported tasks for one subject can never appear.
"""
from ai_services.rag.rules_text import RULES, SOURCE as RULE_SOURCE
from features.subject_catalogue.assessment_load import assessment_load_map
from features.subject_catalogue.assessments import ai_context, load_assessment_info
from features.subject_catalogue.service import (
    get_major,
    get_submajor,
    list_majors,
    list_submajors,
    load_prerequisites,
    prerequisite_lines,
)

STATUS_SOURCE = {
    "indicative": "UTS Handbook (indicative); sessions offered and due weeks are illustrative",
    "historical": "Historical UTS information (an older year, may have changed); sessions offered are illustrative",
    "synthetic": "Invented sample subject for this prototype (not a real UTS subject)",
    "none": "UTS Handbook (subject details); no confirmed assessment information; sessions offered are illustrative",
}


def _sessions(value):
    return "both Autumn and Spring" if value == "Both" else value


def _subject_chunks(conn):
    infos = load_assessment_info(conn)
    rows = [dict(r) for r in conn.execute("SELECT code, name, credit_points, sessions_offered, category, prereq_status FROM subjects ORDER BY code")]
    loads = assessment_load_map(load_prerequisites(conn), infos, rows)
    notes = {r["subject_code"]: r["note"] for r in conn.execute("SELECT subject_code, note FROM prerequisite_notes")}
    member = {}
    for r in conn.execute("SELECT ms.subject_code, m.name, ms.role FROM major_subjects ms JOIN majors m ON m.code = ms.major_code ORDER BY m.name"):
        member.setdefault(r["subject_code"], []).append(f"{r['name']} major ({r['role']})")
    for r in conn.execute(
        "SELECT gs.subject_code, sm.name, g.kind, g.language_name FROM submajor_group_subjects gs"
        " JOIN submajor_groups g ON g.id = gs.group_id JOIN submajors sm ON sm.code = g.submajor_code ORDER BY sm.name"
    ):
        label = f"{r['name']} sub-major" + (f", {r['language_name']}" if r["language_name"] else "")
        member.setdefault(r["subject_code"], []).append(f"{label} ({'core' if r['kind'] == 'core' else 'option'})")
    for s in rows:
        code = s["code"]
        info = infos.get(code)
        status = info["status"] if info else "none"
        reqs = prerequisite_lines(conn, code)
        parts = [
            f"Subject {code} {s['name']}. {s['credit_points']} credit points. Runs in {_sessions(s['sessions_offered'])} (illustrative).",
            ("Prerequisites (every line must be met; 'or' means any one will do): " + "; ".join(reqs) + ".") if reqs
            else ("Prerequisites have not been verified for this subject." if s["prereq_status"] == "unknown"
                  else "No prerequisites are listed."),
            ai_context(conn, code)["text"],
        ]
        if notes.get(code):
            parts.append(f"Note: {notes[code]}")
        score = loads[code]["score"]
        if score:
            parts.append(f"Assessment load: {score} of 5 (the app's own estimate, not a UTS rating): " + "; ".join(loads[code]["reasons"]) + ".")
        if code in member:
            parts.append("Counts towards: " + "; ".join(member[code]) + ".")
        yield f"subject:{code}", "subject", f"{code} {s['name']}", STATUS_SOURCE.get(status, STATUS_SOURCE["none"]), " ".join(parts)


def _major_chunks(conn):
    for m in list_majors(conn):
        major = get_major(conn, m["code"])
        core = "; ".join(f"{s['code']} {s['name']}" for s in major["core"])
        options = "; ".join(f"{s['code']} {s['name']}" for s in major["options"])
        body = (f"Major {major['name']} ({major['code']}), 48 credit points: {major['core_cp']} credit points of core subjects, all required: "
                f"{core}.")
        if major["options"]:
            body += f" Options, choose {major['options_cp']} credit points from: {options}."
        else:
            body += " This major has no options: every subject is core."
        yield f"major:{major['code']}", "major", f"{major['name']} major", "Major structure supplied from the UTS Handbook", body


def _submajor_chunks(conn):
    for sm in list_submajors(conn):
        parts = [f"Sub-major {sm['name']} ({sm['code']}), 24 credit points."]
        for g in sm["all_groups"]:
            subjects = "; ".join(f"{s['code']} {s['name']} ({s['credit_points']} cp)" for s in g["subjects"])
            if g["language_program"]:
                parts.append(f"Language program {g['language_name']} ({g['language_program']}): choose {g['required_cp']} credit points from: {subjects}.")
            elif g["kind"] == "core":
                parts.append(f"Core, all required ({g['required_cp']} credit points): {subjects}.")
            else:
                where = f" from stream {g['stream_code']}" if g["stream_code"] else ""
                parts.append(f"{g['label']}: choose {g['required_cp']} credit points{where}" + (f" from: {subjects}." if subjects else ". The subjects in this stream have not been loaded."))
        if sm["is_language"]:
            parts.append("Choose exactly one language program and do not combine languages. Language prerequisites, order and the placement assessment are not verified.")
        if sm["note"]:
            parts.append(sm["note"])
        yield (f"submajor:{sm['code']}", "submajor", f"{sm['name']} sub-major",
               "Sub-major structure supplied from the UTS Handbook (not independently verified)", " ".join(parts))


def _rule_chunks():
    for ref, title, body in RULES:
        yield ref, "rule", title, RULE_SOURCE, body


def build_index(conn):
    """Rebuild every source and the search index from the app's current data. Safe to run again."""
    conn.execute("DELETE FROM rag_chunks")
    for generator in (_rule_chunks(), _major_chunks(conn), _submajor_chunks(conn), _subject_chunks(conn)):
        conn.executemany(
            "INSERT INTO rag_chunks (ref, kind, title, source, body) VALUES (?, ?, ?, ?, ?)", list(generator)
        )
    conn.execute("INSERT INTO rag_fts (rag_fts) VALUES ('rebuild')")
    conn.commit()
    return conn.execute("SELECT COUNT(*) FROM rag_chunks").fetchone()[0]
