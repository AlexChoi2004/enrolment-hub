"""An assessment load estimate (1 to 5) for each subject, worked out from the handbook data with a visible formula.

It measures how heavy the ASSESSMENT is, not how hard the content is, and it is the app's own estimate, NOT a UTS
rating. It uses only what is known about the subject:
  * how far into the degree it sits (the length of its prerequisite chain),
  * how much of the marks come from an exam and how many assessments there are,
  * whether it has a hurdle, one task worth most of the marks, or more than 6 credit points.
A subject with no confirmed assessment breakdown gets no score at all: it is "not enough information", not an average.
"""

HURDLE_WORDS = ("hurdle",)


def prerequisite_depths(rules):
    """{subject: how many subjects deep its prerequisite chain goes}. Alternatives count by their shortest route."""
    memo = {}

    def depth(code, trail=()):
        if code in memo:
            return memo[code]
        if code in trail:  # defensive: the data has no cycles, but never loop
            return 0
        groups = rules.get(code, [])
        if not groups:
            memo[code] = 0
            return 0
        value = 1 + max(min(depth(c, trail + (code,)) for c in g["codes"]) for g in groups)
        memo[code] = value
        return value

    return {code: depth(code) for code in set(rules) | {c for g in rules.values() for grp in g for c in grp["codes"]}}


def estimate(info, depth, credit_points, category, hurdle_note=""):
    """(score or None, [reasons]) for one subject. `info` is the subject's assessment info."""
    if info is None or info["status"] == "none" or not info["tasks"]:
        return None, ["Not enough information: there is no confirmed assessment breakdown."]
    points, reasons = 0.0, []
    if depth:
        points += min(depth, 3) * 0.8
        reasons.append(f"sits {depth} subject{'s' if depth != 1 else ''} deep in a prerequisite chain")
    exam = info["exam_weight"]
    if exam >= 50:
        points += 1.8
        reasons.append(f"the exam is {exam}% of the marks")
    elif exam >= 30:
        points += 1.2
        reasons.append(f"the exam is {exam}% of the marks")
    elif exam > 0:
        points += 0.6
        reasons.append(f"it has an exam ({exam}%)")
    count = sum(1 for t in info["tasks"] if t["weight"] is not None)
    if count >= 6:
        points += 1.2
        reasons.append(f"{count} separate assessments")
    elif count >= 4:
        points += 0.7
        reasons.append(f"{count} separate assessments")
    elif count == 3:
        points += 0.3
        reasons.append("3 assessments")
    biggest = max((t["weight"] for t in info["tasks"] if t["weight"] is not None), default=0)
    if biggest >= 60:
        points += 0.7
        reasons.append(f"one task is worth {biggest}% of the marks")
    if any(w in (info.get("internal_note") or "").lower() for w in HURDLE_WORDS):
        points += 0.7
        reasons.append("it has a hurdle (a minimum mark you must reach)")
    if credit_points >= 12 or category == "honours_core":
        points += 0.8
        reasons.append("it is an honours or 12 credit point subject")
    return max(1, min(5, round(1 + points * 0.95))), reasons


def assessment_load_map(rules, infos, subjects):
    """{code: {"score": 1-5 or None, "reasons": [...]}} for every subject row (dicts with code, credit_points, category)."""
    depths = prerequisite_depths(rules)
    out = {}
    for s in subjects:
        score, reasons = estimate(infos.get(s["code"]), depths.get(s["code"], 0), s["credit_points"], s["category"])
        out[s["code"]] = {"score": score, "reasons": reasons}
    return out
