"""The planner board: the plan as columns (one per session) of cards, plus a "to place" column, for dragging subjects around.

Nothing here decides anything. The board data is the planner's own plan reshaped, and every change goes through the planner's own
add, move and remove, so the board can never allow what the planner refuses. The server tells the page which sessions are valid for
each card (so it can highlight them); the page can still ask for any move, and the planner answers with the reason if it is refused.
The shape of the data is a contract with frontend/src/board/contract.ts, checked from both sides.
"""
from features.degree_planner import service
from features.degree_planner.service import PlanError
from features.subject_catalogue.service import degree_categories

CAPACITY = service.MAX_CP_PER_SESSION


def _card(item, state, valid, problem=None, retake=False, category=None, key=None):
    return {"code": item["code"], "name": item["name"], "credit_points": item["credit_points"], "category": category, "category_key": key,
            "state": state, "problem": problem, "retake": retake, "valid_sessions": list(valid)}


def build_board(conn, user_id):
    """The whole board as plain data, for one student."""
    plan = service.get_plan(conn, user_id)
    categories = degree_categories(conn, user_id)  # in the degree's own order
    key_of = {c["label"]: c["category"] for c in categories}
    sections = {s["label"]: s for s in plan["elective_sections"]}

    columns = []
    for s in plan["sessions"]:
        cards = [_card(e, "enrolled", [], category=e["category_label"], key=key_of.get(e["category_label"])) for e in s["enrolled"]]
        cards += [_card(p, "planned", p["move_sessions"], p["problem"], category=p["category_label"], key=key_of.get(p["category_label"])) for p in s["planned"]]
        columns.append({"label": s["label"], "current": s["label"] == plan["period"]["label"], "capacity_cp": CAPACITY, "load_cp": s["load_cp"],
                        "workload": s["workload"]["status"], "workload_label": s["workload"]["label"], "cards": cards})

    to_place = [_card(p, "stranded", p["move_sessions"], p["problem"]) for p in plan["past_plans"]]
    groups = []
    for c in categories:  # one group per requirement that still has something to place, in the degree's order
        label, key = c["label"], c["category"]
        section = sections.get(label)
        cards = [_card(o, "todo", o["sessions"], None, o["retake"], label, key) for o in plan["outstanding"] if o["category_label"] == label]
        if section:  # a choose-some-of-these requirement: the subjects to choose from, each with the sessions the planner would accept
            cards += [_card(x, "todo", x["sessions"], None, False, label, key) for x in section["candidates"]]
        if not cards and not (section and section["need"]):
            continue
        to_place += cards
        groups.append({"key": key, "label": label, "kind": "choose" if section else "required", "count": len(cards),
                       "choose": section["choose"] if section else None, "chosen": section["chosen"] if section else None,
                       "need": section["need"] if section else None})

    choose_first = []
    if plan["needs_major"]:
        choose_first.append({"label": "Choose your major to see its subjects here.", "href": "/major"})
    if plan["needs_submajor"]:
        choose_first.append({"label": "Choose a sub-major or general electives to see their subjects here.", "href": "/submajor"})
    return {"period": plan["period"], "capacity_cp": CAPACITY, "columns": columns, "to_place": to_place, "groups": groups, "choose_first": choose_first}


def move_card(conn, user_id, code, to):
    """Place, move or remove one subject (to=None removes it from the plan). Returns the planner's own confirmation text.

    Raises PlanError with the planner's own reason if the planner refuses."""
    planned_in = conn.execute("SELECT session_label FROM planned_subjects WHERE user_id = ? AND subject_code = ?", (user_id, code)).fetchone()
    if to is None:
        label = service.remove_from_plan(conn, user_id, code)
        return f"Removed {label} from your plan."
    if planned_in is not None:
        label = service.move_in_plan(conn, user_id, code, to)
        return f"Moved {label} to {to}."
    label = service.add_to_plan(conn, user_id, code, to)
    return f"Added {label} to your plan for {to}."


__all__ = ["CAPACITY", "PlanError", "build_board", "move_card"]
