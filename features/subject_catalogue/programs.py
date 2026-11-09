"""Majors and sub-majors in one shape, so they can be described and compared the same way."""
from features.subject_catalogue.program_text import handbook_url, has_no_overview, note_of, summary_of
from features.subject_catalogue.service import get_major, get_submajor, list_majors, list_submajors
from features.subject_catalogue.themes import focus_areas

KINDS = ("major", "submajor")


def _entry(subject, role):
    return {"code": subject["code"], "name": subject["name"], "credit_points": subject["credit_points"], "role": role, "handbook_url": subject.get("handbook_url")}


def _finish(kind, code, name, total_cp, subjects, structure, uses_language=False):
    seen, unique = set(), []
    for s in sorted(subjects, key=lambda s: (s["role"] != "core", s["name"])):  # core first; a subject in two groups keeps its core role
        if s["code"] not in seen:
            seen.add(s["code"])
            unique.append(s)
    return {
        "kind": kind, "code": code, "name": name, "total_cp": total_cp, "subjects": unique, "listed_cp": sum(s["credit_points"] for s in unique),
        "structure": structure, "uses_language": uses_language, "focus": focus_areas([s["name"] for s in unique]),
        "handbook_url": handbook_url(code), "summary": summary_of(code), "no_overview": has_no_overview(code), "note": note_of(code),
    }


def major_program(conn, code):
    major = get_major(conn, code)
    if major is None:
        return None
    subjects = [_entry(s, "core") for s in major["core"]] + [_entry(s, "option") for s in major["options"]]
    structure = f"{major['core_cp']} cp core" + (f", plus choose {major['choose']} of {len(major['options'])} options ({major['options_cp']} cp)" if major["options"] else "")
    return _finish("major", major["code"], major["name"], 48, subjects, structure)


def submajor_program(conn, code):
    sub = get_submajor(conn, code)
    if sub is None:
        return None
    subjects, parts = [], []
    for group in sub["groups"]:
        core = group["kind"] == "core"
        subjects += [_entry(s, "core" if core else "option") for s in group["subjects"]]
        parts.append(f"{group['required_cp']} cp core" if core else f"choose {group['required_cp']} cp from {len(group['subjects'])} subjects")
    structure = " · ".join(parts) if parts else "The subjects depend on the language you choose"
    return _finish("submajor", sub["code"], sub["name"], sub["total_cp"], subjects, structure, uses_language=sub["is_language"])


def load_program(conn, kind, code):
    return (major_program if kind == "major" else submajor_program)(conn, code)


def options_of(conn, kind):
    """The choices for a 'pick one' menu: [{'code', 'name'}]."""
    items = list_majors(conn) if kind == "major" else list_submajors(conn)
    return [{"code": i["code"], "name": i["name"]} for i in items]
