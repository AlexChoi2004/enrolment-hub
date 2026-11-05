"""Workload for a session: is this combination of subjects light, balanced, heavy or too heavy, and why?

Everything here is worked out by plain rules from the assessment data. The AI features only explain these results;
they never decide them. Two caveats are always carried with the numbers:
  * assessment load is the app's own estimate (see subject_catalogue.assessment_load), not a UTS rating;
  * due weeks are illustrative (the handbook does not publish them), so "crunch weeks" show how bunched deadlines
    COULD be, not when they really fall.
A subject with no confirmed assessment breakdown is left out of the numbers and reported as missing information.
"""
from features.subject_catalogue.assessments import EXAM_WEEK, load_assessment_info
from features.subject_catalogue.assessment_load import assessment_load_map
from features.subject_catalogue.service import load_prerequisites

HIGH_LOAD = 4  # assessment load of 4 or 5
CRUNCH_COUNT = 4  # this many assessments due in one week
CRUNCH_WEIGHT = 70  # or this many percentage points of marks due in one week
LABELS = {"light": "Light", "balanced": "Balanced", "heavy": "Heavy", "too_heavy": "Too heavy"}
ORDER = ["light", "balanced", "heavy", "too_heavy"]


def load_context(conn):
    """Everything workload needs, loaded once: assessment info, assessment load estimates and names."""
    infos = load_assessment_info(conn)
    subjects = [dict(r) for r in conn.execute("SELECT code, name, credit_points, category FROM subjects")]
    return {
        "infos": infos,
        "load": assessment_load_map(load_prerequisites(conn), infos, subjects),
        "names": {s["code"]: s["name"] for s in subjects},
    }


def _status(points):
    return "light" if points <= 3 else "balanced" if points <= 6 else "heavy" if points <= 9 else "too_heavy"


def rank(status):
    return ORDER.index(status)


def session_workload(ctx, codes):
    """The workload of taking these subjects together."""
    names, infos, load = ctx["names"], ctx["infos"], ctx["load"]
    known = [c for c in codes if load[c]["score"] is not None]
    unknown = [c for c in codes if c not in known]
    score = {c: load[c]["score"] for c in known}
    high = [c for c in known if score[c] >= HIGH_LOAD]
    medium = [c for c in known if score[c] == 3]

    weeks = {}
    for c in known:
        for t in infos[c]["tasks"]:
            if t["due_week"] is None or t["due_week"] == EXAM_WEEK or t["weight"] is None:
                continue
            w = weeks.setdefault(t["due_week"], {"count": 0, "weight": 0, "items": []})
            w["count"] += 1
            w["weight"] += t["weight"]
            w["items"].append({"code": c, "name": t["name"], "weight": t["weight"]})
    crunch = sorted(wk for wk, v in weeks.items() if v["count"] >= CRUNCH_COUNT or v["weight"] >= CRUNCH_WEIGHT)
    group_heavy = [c for c in known if infos[c]["group_weight"] >= 30]
    exam_heavy = [c for c in known if infos[c]["exam_weight"] >= 40]

    points = 2 * len(high) + len(medium) + 2 * min(len(crunch), 3)
    points += 1 if len(group_heavy) >= 3 else 0
    points += 1 if len(exam_heavy) >= 3 else 0
    status = _status(points) if known else None

    def label(c):
        return f"{c} {names[c]}"

    warnings, positives = [], []
    if len(high) >= 2:
        warnings.append(f"{len(high)} high-load subjects (assessment load 4 or 5): " + ", ".join(label(c) for c in high))
    for wk in crunch:
        v = weeks[wk]
        warnings.append(f"Crunch week {wk}: {v['count']} deadlines worth {v['weight']}% of marks ("
                        + ", ".join(f"{i['code']} {i['name']}" for i in v["items"]) + ")")
    if len(group_heavy) >= 3:
        warnings.append(f"{len(group_heavy)} subjects have group work worth 30% or more: " + ", ".join(label(c) for c in group_heavy))
    if len(exam_heavy) >= 3:
        warnings.append(f"{len(exam_heavy)} subjects have exams worth 40% or more, all in the exam period")
    if known and len(high) <= 1:
        positives.append("At most one high-load subject" if high else "No high-load subjects")
    if known and not crunch:
        positives.append(f"No crunch weeks: no week has {CRUNCH_COUNT} or more deadlines or {CRUNCH_WEIGHT}% of marks due")
    if known and len(group_heavy) <= 1 and len(exam_heavy) <= 1:
        positives.append("A mix of assessment styles, not all group work or all exams")
    if unknown:
        warnings.append(f"{len(unknown)} subject(s) have no assessment information, so the load may be understated: "
                        + ", ".join(label(c) for c in unknown))
    average = round(sum(score.values()) / len(score), 1) if score else None
    return {
        "status": status, "label": LABELS.get(status, "Not enough information"), "points": points,
        "subject_count": len(codes), "known_count": len(known), "unknown": unknown,
        "high_load": high, "average_load": average, "crunch_weeks": crunch,
        "weeks": {wk: weeks[wk] for wk in sorted(weeks)},
        "warnings": warnings, "positives": positives,
    }


def suggest_moves(ctx, session_codes, session_label, movable, limit=2):
    """Moves that would lighten a heavy session.

    session_codes: {session label: [codes]} for every session in view. movable: [(code, [sessions it may move to])]
    for the PLANNED subjects of this session (enrolled ones are not offered). Each suggestion lightens this session
    without making the target heavier than this one was.
    """
    current = session_workload(ctx, session_codes[session_label])
    if current["status"] not in ("heavy", "too_heavy"):
        return []
    scored = []
    for code, targets in movable:
        for target in targets:
            if target == session_label:
                continue
            source_after = session_workload(ctx, [c for c in session_codes[session_label] if c != code])
            target_after = session_workload(ctx, session_codes.get(target, []) + [code])
            if source_after["status"] is None or target_after["status"] is None:
                continue
            # Accept only if the moved subject lightens this session AND lands somewhere lighter than this one was.
            if rank(source_after["status"]) < rank(current["status"]) and rank(target_after["status"]) < rank(current["status"]):
                worst = max(source_after["points"], target_after["points"])  # prefer the most even split
                scored.append((worst, -(ctx["load"][code]["score"] or 0), code, target, source_after, target_after))
    scored.sort(key=lambda s: (s[0], s[1], s[2], s[3]))
    out, used = [], set()
    for _, _, code, target, source_after, target_after in scored:
        if code in used:
            continue
        used.add(code)
        out.append({
            "code": code, "name": ctx["names"][code], "to": target, "from": session_label,
            "load": ctx["load"][code]["score"],
            "source_status": source_after["label"], "target_status": target_after["label"],
            "reason": (f"{session_label} would go from {current['label']} to {source_after['label']}; "
                       f"{target} would be {target_after['label']}"),
        })
        if len(out) == limit:
            break
    return out


def context_for_ai(ctx, session_label, codes):
    """Plain-text workload facts for the AI features, with the caveats attached."""
    result = session_workload(ctx, codes)
    if result["status"] is None:
        return f"Not enough context: none of the subjects in {session_label} has a confirmed assessment breakdown."
    lines = [f"{session_label}: {result['label']} workload ({result['known_count']} of {result['subject_count']} subjects have assessment information)."]
    lines += [f"Concern: {w}" for w in result["warnings"]] + [f"Positive: {p}" for p in result["positives"]]
    lines.append("Assessment load is an app estimate (how heavy the assessment is), not a UTS rating, and due weeks are illustrative (invented), so say so.")
    return "\n".join(lines)
