"""Assessment information: what a student is shown, and what the AI features are allowed to use.

Three rules run through this module:
  * descriptions and assessment records are separate, and a subject may have several assessment
    structures over time (only the one marked current is shown);
  * nothing is invented for a real subject: with no confirmed breakdown there are no tasks, and the
    student is told they will find out when they enrol;
  * anything that is not confirmed is labelled, and the AI helpers say "not enough context" rather than guess.
"""
TYPES = (
    "quiz", "exam", "exercises", "project", "report", "presentation", "practical",
    "journal", "reflection", "portfolio", "design", "essay", "case_study", "demonstration",
)
GROUPWORK = ("individual", "group", "group_individual")

TYPE_LABELS = {
    "quiz": "Quiz/test", "exam": "Exam", "exercises": "Exercises", "project": "Project", "report": "Report",
    "presentation": "Presentation", "practical": "Lab/practical", "journal": "Journal", "reflection": "Reflection",
    "portfolio": "Portfolio", "design": "Design task", "essay": "Essay", "case_study": "Case study",
    "demonstration": "Demonstration",
}
TYPE_EXPLANATIONS = {
    "quiz": "A short test of recent content.",
    "exam": "A timed exam covering the subject.",
    "exercises": "Regular practice tasks that build skills week by week.",
    "project": "A larger piece of practical work built over several weeks.",
    "report": "A written report on analysis or findings.",
    "presentation": "A presentation of your work, usually with questions.",
    "practical": "Hands-on lab or skills work.",
    "journal": "A running record of your work and what you learned.",
    "reflection": "A written reflection on your learning.",
    "portfolio": "A collection of your work gathered across the session.",
    "design": "A design task where you document your decisions.",
    "essay": "A written argument on a set question.",
    "case_study": "An analysis of a real or example situation.",
    "demonstration": "Showing a skill or a working solution.",
}
GROUP_LABELS = {
    "individual": "Individual", "group": "Group", "group_individual": "Group work, marked individually",
}
GROUP_EXPLANATIONS = {
    "individual": "", "group": " Done as a team.", "group_individual": " Done as a team, with individual marks.",
}
TAG_LABELS = {
    "code": "Code-based", "theory": "Theory", "practical": "Practical", "group": "Group work",
    "quiz-heavy": "Quiz-heavy", "exam": "Exam", "report": "Report writing", "project-heavy": "Project-based",
    "independent": "Independent work", "presentation": "Presentations", "assignment-heavy": "Assignment-heavy",
    "essay": "Essay writing",
}

NO_BREAKDOWN = "No assessment breakdown has been published yet. You'll find out when you enrol and receive the subject outline."
NOT_ENOUGH = "Not enough context"


def explain(type_, groupwork):
    """A short plain-language explanation of one assessment. It describes the kind of task, not the exact brief."""
    return TYPE_EXPLANATIONS[type_] + GROUP_EXPLANATIONS[groupwork]


def _date_text(iso):
    year, month, day = (int(p) for p in iso.split("-"))
    return f"{day} {('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')[month - 1]} {year}"


def _banner(status, source, year, retrieved_on):
    if status == "indicative":
        when = f", retrieved {_date_text(retrieved_on)}" if retrieved_on else ""
        return f"Source: {source} (indicative){when}. Check your subject outline for the exact tasks and due dates."
    if status == "verified_current":
        return f"Source: {source}{f', {year}' if year else ''} (verified against the official outline)."
    if status == "historical":
        return (f"Historical information from {year}: it may have changed. "
                "Check the current subject outline before relying on it.")
    if status == "synthetic":
        return "Sample data invented for this prototype. This is not a real UTS subject."
    return NO_BREAKDOWN


def _weight_text(weight):
    return "Mandatory, no marks" if weight is None else f"{weight}%"


def load_assessment_info(conn):
    """{code: info} for every subject: the description, tags and the CURRENT assessment structure."""
    descriptions = {
        r["subject_code"]: r
        for r in conn.execute("SELECT subject_code, description, style_tags FROM subject_descriptions")
    }
    structures = {}
    for r in conn.execute(
        "SELECT * FROM assessment_structures WHERE is_current = 1 ORDER BY id"
    ):
        structures[r["subject_code"]] = dict(r)  # the newest current structure wins
    tasks = {}
    for r in conn.execute("SELECT * FROM assessments ORDER BY structure_id, position"):
        tasks.setdefault(r["structure_id"], []).append(dict(r))

    info = {}
    codes = set(descriptions) | set(structures)
    for code in codes:
        d = descriptions.get(code)
        s = structures.get(code)
        status = "none"
        rows = []
        if s and s["verification"] != "unverified":
            rows = tasks.get(s["id"], [])
            status = s["verification"] if rows else "none"
        task_list = [
            {
                "name": t["name"], "type": t["type"], "type_label": TYPE_LABELS[t["type"]],
                "weight": t["weight"], "weight_text": _weight_text(t["weight"]),
                "groupwork": t["groupwork"], "group_label": GROUP_LABELS[t["groupwork"]],
                "description": t["description"], "due_week": t["due_week"], "due_week_source": t["due_week_source"],
            }
            for t in rows
        ]
        marks = [t for t in task_list if t["weight"] is not None]
        info[code] = {
            "summary": d["description"] if d else "",
            "tags": [TAG_LABELS.get(t, t) for t in d["style_tags"].split(",") if t] if d else [],
            "status": status,
            "tasks": task_list,
            "total_weight": sum(t["weight"] for t in marks),
            "group_weight": sum(t["weight"] for t in marks if t["groupwork"] != "individual"),
            "exam_weight": sum(t["weight"] for t in marks if t["type"] == "exam"),
            "source": s["source"] if s and status != "none" else "",
            "year": s["academic_year"] if s else None,
            "retrieved_on": s["retrieved_on"] if s else None,
            "banner": _banner(status, s["source"] if s else "", s["academic_year"] if s else None,
                              s["retrieved_on"] if s else None),
            # Kept for staff and for later verification work. Never shown to students or given to the AI.
            "internal_note": s["note"] if s else "",
        }
    return info


def assessment_info(conn, code):
    return load_assessment_info(conn).get(code)


def ai_context(conn, code):
    """What the AI features may say about one subject. Unconfirmed assessment details are never included.

    Returns {"assessments_known": bool, "status": str, "text": str}. When the breakdown is not known the text
    starts with "Not enough context" so the AI answers that instead of guessing.
    """
    subject = conn.execute("SELECT code, name FROM subjects WHERE code = ?", (code,)).fetchone()
    if subject is None:
        return {"assessments_known": False, "status": "none", "text": f"{NOT_ENOUGH}: that subject is not in the catalogue."}
    info = assessment_info(conn, code)
    label = f"{subject['code']} {subject['name']}"
    if info is None or info["status"] == "none":
        summary = f" What is known: {info['summary']}" if info and info["summary"] else ""
        return {
            "assessments_known": False, "status": "none",
            "text": f"{NOT_ENOUGH}: there is no confirmed assessment breakdown for {label}.{summary}",
        }
    parts = [f"{t['name']} ({t['weight_text']}, {t['group_label'].lower()}, {t['type_label'].lower()})" for t in info["tasks"]]
    caveat = {
        "indicative": "Indicative information from the UTS Handbook; the subject outline is authoritative.",
        "verified_current": "Verified against the official subject outline.",
        "historical": f"Historical information from {info['year']}; it may have changed, so say that it is unconfirmed for the current year.",
        "synthetic": "Sample data invented for this prototype; not a real UTS subject.",
    }[info["status"]]
    text = f"{label}: {info['summary']} Assessments: " + "; ".join(parts) + f". {caveat}"
    return {"assessments_known": True, "status": info["status"], "text": text}


def replace_structure(conn, code, tasks, *, source, verification="verified_current", year=None, session=None,
                      retrieved_on=None, note=""):
    """Add a newer assessment structure (for example from a new official outline) and make it current.

    tasks = [(name, type, groupwork, weight)]. The older structure is kept as history, no longer current.
    """
    if verification not in ("verified_current", "indicative", "historical", "unverified", "synthetic"):
        raise ValueError("Unknown verification status.")
    for name, type_, groupwork, weight in tasks:
        if type_ not in TYPES:
            raise ValueError(f"Unknown assessment type: {type_}.")
        if groupwork not in GROUPWORK:
            raise ValueError(f"Unknown groupwork value: {groupwork}.")
    if tasks and sum(w for *_, w in tasks if w is not None) != 100:
        raise ValueError("Assessment weights must add up to 100.")
    conn.execute("UPDATE assessment_structures SET is_current = 0 WHERE subject_code = ?", (code,))
    cur = conn.execute(
        "INSERT INTO assessment_structures (subject_code, academic_year, session, source, retrieved_on,"
        " verification, note, is_current) VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
        (code, year, session, source, retrieved_on, verification, note),
    )
    for position, (name, type_, groupwork, weight) in enumerate(tasks, 1):
        conn.execute(
            "INSERT INTO assessments (structure_id, position, name, description, type, weight, groupwork)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (cur.lastrowid, position, name, explain(type_, groupwork), type_, weight, groupwork),
        )
    conn.commit()
    return cur.lastrowid
