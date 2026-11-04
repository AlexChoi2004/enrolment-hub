"""Turn a model's answer into something tidy to read: short paragraphs and bullet lists, without the citation markers.

The markers ([1], [get_my_plan]) are checked by code before anything is shown, then taken out of the text so it reads
cleanly; the sources and what the AI looked at stay one click away. Everything returned is plain text for the template to
escape; no HTML is ever built here.
"""
import re

MARKER = re.compile(r"\s*\[(?:\d{1,2}|[a-z_]+)\]")
BULLET = re.compile(r"^\s*(?:[-*\u2022])\s+(.*)$")
TOOL_LABELS = {
    "search_subjects": "subject search", "get_subject_info": "subject details", "check_prerequisites": "prerequisite check",
    "list_offerings": "when it runs", "check_plan_placement": "plan check", "get_my_plan": "your plan",
    "get_session_workload": "session workload", "find_clash_free_classes": "class times", "get_my_results": "your results",
    "get_swap_advice": "swap advice",
}


def answer_blocks(text):
    """[{"kind": "p", "text": ...} | {"kind": "ul", "items": [...]}] from the model's text, with citation markers removed."""
    blocks, items = [], []

    def flush():
        nonlocal items
        if items:
            blocks.append({"kind": "ul", "items": items})
            items = []

    for raw in (text or "").splitlines():
        line = MARKER.sub("", raw).strip()
        if not line:
            flush()
            continue
        bullet = BULLET.match(line)
        if bullet:
            items.append(bullet.group(1).strip())
        else:
            flush()
            blocks.append({"kind": "p", "text": line})
    flush()
    return blocks


def tool_label(name):
    return TOOL_LABELS.get(name, name.replace("_", " "))
