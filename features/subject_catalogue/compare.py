"""Compare two majors, or two sub-majors, side by side: what they share, what only one has, and how their focus differs.

Pure functions on the shape from programs.py: no database and no Flask. Nothing is guessed. Similarity is counted from the subjects each program
lists, measured against the SMALLER program (so a short sub-major that sits wholly inside a long one counts as closely related), and every focus
area lists the subjects behind it. The verdict's cut-offs are constants here, and the page shows them.
"""
CLOSE = 0.5  # at least this share of the smaller program's credit points is also in the other: closely related
PARTLY = 0.25  # at least this share: partly similar; any less but not zero: little in common
VERDICTS = {
    "close": "Closely related", "partly": "Partly similar", "little": "Little in common", "none": "Nothing in common", "unknown": "Cannot compare subject by subject",
}
MAX_HIGHLIGHTS = 4


def verdict_of(closeness):
    if closeness is None:
        return "unknown"
    if closeness == 0:
        return "none"
    return "close" if closeness >= CLOSE else "partly" if closeness >= PARTLY else "little"


def _ordered(subjects):
    return sorted(subjects, key=lambda s: (s["role"] != "core", s["name"]))


def _focus(a, b):
    """Which focus areas both programs have, and which only one has. None when a program has none to compare."""
    if not a["focus"] or not b["focus"]:
        return None
    labels_a, labels_b = {f["label"]: f for f in a["focus"]}, {f["label"]: f for f in b["focus"]}
    both = [{"label": label, "a": labels_a[label]["subjects"], "b": labels_b[label]["subjects"]} for label in labels_a if label in labels_b]
    return {"both": both, "only_a": [f for label, f in labels_a.items() if label not in labels_b], "only_b": [f for label, f in labels_b.items() if label not in labels_a]}


def _sentence(a, b, verdict, shared, shared_cp, percent, core_both):
    if verdict == "unknown":
        who = " and ".join(p["name"] for p in (a, b) if not p["subjects"]) or a["name"]
        return f"The subjects for {who} depend on the language you choose, so these two cannot be compared subject by subject yet."
    if verdict == "none":
        return f"{a['name']} and {b['name']} share no subjects."
    count = f"{len(shared)} subject{'' if len(shared) == 1 else 's'} ({shared_cp} cp)"
    lead = {"close": "are closely related", "partly": "are partly similar", "little": "have little in common"}[verdict]
    text = f"{a['name']} and {b['name']} {lead}: they share {count}, which is {percent}% of the smaller program."
    if core_both:
        text += f" {core_both} of them {'is' if core_both == 1 else 'are'} core in both."
    return text


def compare_programs(a, b):
    """The comparison of two programs of the same kind. Returns plain data for the page."""
    by_a, by_b = {s["code"]: s for s in a["subjects"]}, {s["code"]: s for s in b["subjects"]}
    comparable = bool(by_a) and bool(by_b) and not a["uses_language"] and not b["uses_language"]
    shared = _ordered([{**by_a[c], "role_a": by_a[c]["role"], "role_b": by_b[c]["role"], "role": "core" if by_a[c]["role"] == by_b[c]["role"] == "core" else "option"}
                       for c in by_a if c in by_b]) if comparable else []
    only_a = _ordered([s for c, s in by_a.items() if c not in by_b]) if comparable else []
    only_b = _ordered([s for c, s in by_b.items() if c not in by_a]) if comparable else []
    shared_cp = sum(s["credit_points"] for s in shared)
    smaller = min(a["listed_cp"], b["listed_cp"])
    closeness = (shared_cp / smaller) if comparable and smaller else None
    percent = round(closeness * 100) if closeness is not None else None
    verdict = verdict_of(closeness)
    core_both = sum(1 for s in shared if s["role"] == "core")
    return {
        "a": a, "b": b, "comparable": comparable, "verdict": verdict, "verdict_label": VERDICTS[verdict], "closeness_percent": percent,
        "shared": shared, "shared_cp": shared_cp, "only_a": only_a, "only_b": only_b, "core_in_both": core_both,
        "share_of_a": round(100 * shared_cp / a["listed_cp"]) if comparable and a["listed_cp"] else None,
        "share_of_b": round(100 * shared_cp / b["listed_cp"]) if comparable and b["listed_cp"] else None,
        "sentence": _sentence(a, b, verdict, shared, shared_cp, percent, core_both),
        "focus": _focus(a, b), "highlights_a": [s["name"] for s in only_a[:MAX_HIGHLIGHTS]], "highlights_b": [s["name"] for s in only_b[:MAX_HIGHLIGHTS]],
    }
