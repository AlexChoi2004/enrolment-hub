import json
import re

import pytest

from features.degree_planner import service
from features.degree_planner.board import CAPACITY, build_board, move_card
from features.degree_planner.service import PlanError
from features.enrolment.presets import PRESETS
from shared import db

TOKEN = re.compile(r'name="csrf_token" value="([^"]+)"')
KEYS = list(PRESETS)
BOARD_SHAPE = {"period", "capacity_cp", "columns", "to_place", "groups", "choose_first"}


@pytest.fixture(scope="module")
def boards(tmp_path_factory):
    out = {}
    for key in KEYS:
        path = tmp_path_factory.mktemp(key) / "t.db"
        db.build_database(str(path), demo_profile=key)
        conn = db.connect(str(path))
        out[key] = (build_board(conn, 1), conn)
    yield out
    for _, conn in out.values():
        conn.close()


def token(client, path="/profile"):
    return TOKEN.search(client.get(path).get_data(as_text=True)).group(1)


def reset_to(client, key):
    client.post("/simulator/reset", data={"csrf_token": token(client), "confirm": "yes", "profile": key})


def move(client, code, to, csrf=None, **kwargs):
    return client.post("/api/planner/move", json={"code": code, "to": to}, headers={"X-CSRF-Token": csrf or token(client)}, **kwargs)


def planned(app, user=1):
    conn = db.connect(app.config["DATABASE"])
    try:
        return sorted(tuple(r) for r in conn.execute("SELECT subject_code, session_label FROM planned_subjects WHERE user_id = ? ORDER BY 1", (user,)))
    finally:
        conn.close()


# --- the board data --------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("key", KEYS)
def test_the_board_has_the_agreed_shape_and_is_plain_json(boards, key):
    board, _ = boards[key]
    assert set(board) == BOARD_SHAPE and json.loads(json.dumps(board)) == board
    assert board["capacity_cp"] == CAPACITY == 24 and len(board["columns"]) == service.PLAN_SESSIONS


@pytest.mark.parametrize("key", KEYS)
def test_the_board_is_the_planners_own_plan_reshaped(boards, key):
    board, conn = boards[key]
    plan = service.get_plan(conn, 1)
    for column, session in zip(board["columns"], plan["sessions"]):
        assert column["label"] == session["label"] and column["load_cp"] == session["load_cp"]
        assert [c["code"] for c in column["cards"] if c["state"] == "enrolled"] == [e["code"] for e in session["enrolled"]]
        assert [c["code"] for c in column["cards"] if c["state"] == "planned"] == [p["code"] for p in session["planned"]]
    required = {o["code"] for o in plan["outstanding"]}
    chooseable = {x["code"] for s in plan["elective_sections"] for x in s["candidates"]}
    assert sorted(c["code"] for c in board["to_place"] if c["state"] == "todo") == sorted(required | chooseable)  # required subjects and the ones to choose from
    assert [c["code"] for c in board["to_place"] if c["state"] == "stranded"] == [p["code"] for p in plan["past_plans"]]


@pytest.mark.parametrize("key", KEYS)
def test_the_valid_sessions_come_from_the_planner_not_the_board(boards, key):
    board, conn = boards[key]
    plan = service.get_plan(conn, 1)
    by_code = {o["code"]: o["sessions"] for o in plan["outstanding"]}
    by_code.update({x["code"]: x["sessions"] for s in plan["elective_sections"] for x in s["candidates"]})
    for card in board["to_place"]:
        if card["state"] == "todo":
            assert card["valid_sessions"] == by_code[card["code"]]
    for column, session in zip(board["columns"], plan["sessions"]):
        for card in column["cards"]:
            if card["state"] == "planned":
                assert card["valid_sessions"] == next(p["move_sessions"] for p in session["planned"] if p["code"] == card["code"])
            if card["state"] == "enrolled":
                assert card["valid_sessions"] == []


@pytest.mark.parametrize("key", KEYS)
def test_a_subject_is_on_the_board_once(boards, key):
    board, _ = boards[key]
    codes = [c["code"] for c in board["to_place"]] + [c["code"] for col in board["columns"] for c in col["cards"]]
    assert len(codes) == len(set(codes))


def test_enrolled_subjects_are_locked_and_a_retake_is_marked(boards):
    board, _ = boards["failed"]
    assert {c["state"] for c in board["columns"][0]["cards"]} == {"enrolled"}
    retake = next(c for c in board["to_place"] if c["code"] == "48024")
    assert (retake["retake"], retake["state"], len(retake["valid_sessions"])) == (True, "todo", 10)
    blocked = next(c for c in board["columns"][1]["cards"] if c["code"] == "31251")
    assert blocked["state"] == "planned" and "(failed: retake it first)" in blocked["problem"] and blocked["valid_sessions"] == []


def test_the_subjects_to_choose_from_are_on_the_board_with_their_requirement(boards):
    board, _ = boards["sample"]
    electives = [c for c in board["to_place"] if c["category_key"] == "major_elective"]
    assert len(electives) == 8 and {c["category"] for c in electives} == {"Major electives"} and {c["state"] for c in electives} == {"todo"}
    assert all(c["retake"] is False for c in electives) and any(c["valid_sessions"] for c in electives) and any(not c["valid_sessions"] for c in electives)


def test_groups_follow_the_degrees_own_order_and_say_how_many_to_choose(boards):
    board, _ = boards["sample"]
    assert [g["key"] for g in board["groups"]] == ["core", "honours_core", "major_core", "major_elective"]
    assert board["groups"][3] == {"key": "major_elective", "label": "Major electives", "kind": "choose", "count": 8, "choose": 3, "chosen": 1, "need": 2}
    assert board["groups"][0] == {"key": "core", "label": "Core subjects", "kind": "required", "count": 6, "choose": None, "chosen": None, "need": None}
    failed, _ = boards["failed"]
    assert [g["key"] for g in failed["groups"]] == ["core", "honours_core", "major_core", "major_elective", "sub_core"]
    assert next(g for g in failed["groups"] if g["key"] == "major_elective")["need"] == 3


@pytest.mark.parametrize("key", KEYS)
def test_each_groups_count_is_the_number_of_its_cards(boards, key):
    board, _ = boards[key]
    for group in board["groups"]:
        assert group["count"] == len([c for c in board["to_place"] if c["state"] == "todo" and c["category"] == group["label"]]) > 0 or group["kind"] == "choose"
    assert sum(g["count"] for g in board["groups"]) == len([c for c in board["to_place"] if c["state"] == "todo"])


@pytest.mark.parametrize("key", KEYS)
def test_a_subject_on_the_board_knows_its_requirement(boards, key):
    board, _ = boards[key]
    labels = {g["label"]: g["key"] for g in board["groups"]}
    for card in board["to_place"]:
        if card["state"] == "todo":
            assert labels[card["category"]] == card["category_key"]
    for column in board["columns"]:
        for card in column["cards"]:
            assert (card["category"] is None) == (card["category_key"] is None) or card["category"] == "Doesn't count towards your degree"


def test_a_first_year_is_pointed_to_choosing_a_major_and_a_pathway(boards):
    fresh, _ = boards["fresh"]
    assert [n["href"] for n in fresh["choose_first"]] == ["/major", "/submajor"] and [g["key"] for g in fresh["groups"]] == ["core", "honours_core"]
    assert boards["sample"][0]["choose_first"] == []


def test_choosing_general_electives_adds_their_group(tmp_path):
    from features.submajors.service import choose_electives
    path = tmp_path / "t.db"
    db.build_database(str(path), demo_profile="sample")
    conn = db.connect(str(path))
    choose_electives(conn, 1)
    groups = {g["key"]: g for g in build_board(conn, 1)["groups"]}
    assert groups["general_elective"]["kind"] == "choose" and (groups["general_elective"]["choose"], groups["general_elective"]["need"]) == (4, 4)
    assert "sub_core" not in groups


def test_choosing_electives_on_the_board_uses_the_planners_limit(tmp_path):
    path = tmp_path / "t.db"
    db.build_database(str(path), demo_profile="sample")
    conn = db.connect(str(path))
    cards = [c for c in build_board(conn, 1)["to_place"] if c["category_key"] == "major_elective" and c["valid_sessions"]]
    move_card(conn, 1, cards[0]["code"], cards[0]["valid_sessions"][0])
    group = next(g for g in build_board(conn, 1)["groups"] if g["key"] == "major_elective")
    assert (group["chosen"], group["need"]) == (2, 1)
    move_card(conn, 1, cards[1]["code"], cards[1]["valid_sessions"][0])
    assert "major_elective" not in [g["key"] for g in build_board(conn, 1)["groups"]]  # complete: nothing left to choose
    assert not [c for c in build_board(conn, 1)["to_place"] if c["category_key"] == "major_elective"]
    extra = cards[2]  # a third subject that was offered a session: the requirement is full now, so the planner says no
    with pytest.raises(PlanError, match="Major electives requirement would be exceeded"):
        move_card(conn, 1, extra["code"], extra["valid_sessions"][0])


# --- moving cards: the planner decides ---------------------------------------------------------------------------------------------------------

def test_placing_a_subject_adds_it_to_the_plan(tmp_path):
    path = tmp_path / "t.db"
    db.build_database(str(path), demo_profile="failed")
    conn = db.connect(str(path))
    assert move_card(conn, 1, "48024", "Spring 2027") == "Added 48024 Programming 2 to your plan for Spring 2027."
    assert ("48024", "Spring 2027") in [tuple(r) for r in conn.execute("SELECT subject_code, session_label FROM planned_subjects")]


def test_moving_and_removing_use_the_planners_own_messages(tmp_path):
    path = tmp_path / "t.db"
    db.build_database(str(path), demo_profile="failed")
    conn = db.connect(str(path))
    move_card(conn, 1, "48024", "Spring 2027")
    assert move_card(conn, 1, "31251", "Autumn 2028") == "Moved 31251 Data Structures and Algorithms to Autumn 2028."
    assert move_card(conn, 1, "31251", None) == "Removed 31251 Data Structures and Algorithms from your plan."


@pytest.mark.parametrize("code,to,reason", [
    ("48024", "Winter 2029", "Choose a session from Autumn 2027 to Spring 2031."),   # not a session of the plan (the planner's own check)
    ("48024", "Autumn 2040", "Choose a session from Autumn 2027 to Spring 2031."),   # a real label, but outside the planning window
    ("48024", "Spring 1999", "Choose a session from Autumn 2027 to Spring 2031."),
    ("00000", "Spring 2027", "That subject does not exist."),
    ("31265", "Spring 2027", "enrolled"),                                # already enrolled: locked on the board, and refused here too
    ("31251", "Spring 2027", "is already planned for Spring 2027"),
])
def test_the_planner_refuses_what_it_refuses_with_its_own_reason(tmp_path, code, to, reason):
    path = tmp_path / "t.db"
    db.build_database(str(path), demo_profile="failed")
    conn = db.connect(str(path))
    before = [tuple(r) for r in conn.execute("SELECT * FROM planned_subjects ORDER BY 1, 2")]
    with pytest.raises(PlanError) as error:
        move_card(conn, 1, code, to)
    assert reason in str(error.value)
    assert [tuple(r) for r in conn.execute("SELECT * FROM planned_subjects ORDER BY 1, 2")] == before  # a refusal changes nothing


def test_a_board_move_gives_exactly_the_result_of_the_classic_planners_action(tmp_path):
    a, b = tmp_path / "a.db", tmp_path / "b.db"
    for path in (a, b):
        db.build_database(str(path), demo_profile="failed")
    ca, cb = db.connect(str(a)), db.connect(str(b))
    move_card(ca, 1, "48024", "Spring 2027")
    service.add_to_plan(cb, 1, "48024", "Spring 2027")
    assert [tuple(r) for r in ca.execute("SELECT subject_code, session_label FROM planned_subjects ORDER BY 1")] == \
           [tuple(r) for r in cb.execute("SELECT subject_code, session_label FROM planned_subjects ORDER BY 1")]


# --- the pages and the JSON API ---------------------------------------------------------------------------------------------------------------

def test_everything_needs_a_login(client):
    assert client.get("/planner/board").status_code == 302 and client.get("/api/planner/board").status_code == 302
    assert client.post("/api/planner/move", json={"code": "48024", "to": "Spring 2027"}).status_code == 302


def test_the_board_data_is_the_students_own_and_never_cached(client, log_in):
    log_in()
    res = client.get("/api/planner/board")
    assert res.status_code == 200 and res.headers["Cache-Control"] == "no-store" and set(res.get_json()) == BOARD_SHAPE
    assert client.get("/planner/board").headers["Cache-Control"] == "no-store"


def test_the_page_has_a_plain_version_and_loads_the_built_files_with_no_inline_code(client, log_in):
    log_in()
    page = client.get("/planner/board").get_data(as_text=True)
    assert '<div id="board-root" data-board-endpoint="/api/planner/board" data-move-endpoint="/api/planner/move" data-csrf="' in page
    assert "drag-and-drop board needs JavaScript" in page and 'href="/planner">classic planner' in page
    assert '<script type="module" src="/static/dist/board.js"></script>' in page and '<link rel="stylesheet" href="/static/dist/board.css">' in page
    assert all("src=" in s for s in re.findall(r"<script[^>]*>", page))


def test_the_built_board_files_are_in_the_repository(client):
    for name, marker in (("board.js", b"board-root"), ("board.css", b".board-col")):
        res = client.get(f"/static/dist/{name}")
        assert res.status_code == 200 and marker in res.data and len(res.data) > 1000


def test_the_classic_planner_links_to_the_board_and_back(client, log_in):
    log_in()
    assert 'href="/planner/board"' in client.get("/planner").get_data(as_text=True)
    assert 'href="/planner"' in client.get("/planner/board").get_data(as_text=True)


# --- the move endpoint: validation ---------------------------------------------------------------------------------------------------------------

def test_a_valid_move_changes_the_plan_and_returns_the_new_board(app, client, log_in):
    log_in()
    reset_to(client, "failed")
    res = move(client, "48024", "Spring 2027")
    body = res.get_json()
    assert res.status_code == 200 and body["ok"] is True and body["message"] == "Added 48024 Programming 2 to your plan for Spring 2027."
    assert ("48024", "Spring 2027") in planned(app) and body["board"] == client.get("/api/planner/board").get_json()


def test_a_refusal_is_a_422_with_the_planners_reason_and_changes_nothing(app, client, log_in):
    log_in()
    reset_to(client, "failed")
    move(client, "48024", "Spring 2027")
    before = planned(app)
    res = move(client, "48024", "Autumn 2029")
    assert res.status_code == 422 and res.get_json()["ok"] is False
    assert "31251 Data Structures and Algorithms is planned for Spring 2027 and needs 48024 Programming 2 first" in res.get_json()["error"]
    assert planned(app) == before


def test_taking_a_subject_out_of_the_plan(app, client, log_in):
    log_in()
    reset_to(client, "failed")
    res = move(client, "31251", None)
    assert res.status_code == 200 and "31251" not in [c for c, _ in planned(app)]


def test_the_csrf_token_is_required_and_a_wrong_one_is_refused_with_json(app, client, log_in):
    log_in()
    reset_to(client, "failed")
    before = planned(app)
    for headers in ({}, {"X-CSRF-Token": "forged"}, {"X-CSRF-Token": ""}):
        res = client.post("/api/planner/move", json={"code": "48024", "to": "Spring 2027"}, headers=headers)
        assert res.status_code == 400 and res.get_json() == {"ok": False, "error": "Your session has expired. Reload the page and try again."}
    assert planned(app) == before


def test_the_token_cannot_come_from_the_url(app, client, log_in):
    log_in()
    reset_to(client, "failed")
    res = client.post(f"/api/planner/move?csrf_token={token(client)}", json={"code": "48024", "to": "Spring 2027"})
    assert res.status_code == 400 and ("48024", "Spring 2027") not in planned(app)


@pytest.mark.parametrize("body", [
    {}, {"code": "48024"}, {"to": "Spring 2027"}, {"code": "48024", "to": "Spring 2027", "user_id": 2}, {"code": "48024", "to": "Spring 2027", "extra": 1},
    {"code": 48024, "to": "Spring 2027"}, {"code": ["48024"], "to": "Spring 2027"}, {"code": "", "to": "Spring 2027"},
    {"code": "48024'; DROP TABLE users;--", "to": "Spring 2027"}, {"code": "../../etc", "to": "Spring 2027"},
    {"code": "48024", "to": "Winter 2027"}, {"code": "48024", "to": "spring 2027"}, {"code": "48024", "to": "Spring 27"}, {"code": "48024", "to": 2027},
    {"code": "48024", "to": ["Spring 2027"]}, {"code": "48024", "to": "Spring 2027; DROP TABLE users"}, [], "text", 7, None,
])
def test_a_malformed_move_is_refused_before_anything_runs(app, client, log_in, body):
    log_in()
    reset_to(client, "failed")
    before = planned(app)
    res = client.post("/api/planner/move", json=body, headers={"X-CSRF-Token": token(client)})
    assert res.status_code == 400 and res.get_json()["ok"] is False and planned(app) == before


def test_the_body_must_be_json(app, client, log_in):
    log_in()
    reset_to(client, "failed")
    headers = {"X-CSRF-Token": token(client)}
    assert client.post("/api/planner/move", data="code=48024&to=Spring 2027", headers=headers).status_code == 400
    assert client.post("/api/planner/move", data="not json", content_type="application/json", headers=headers).status_code == 400
    assert ("48024", "Spring 2027") not in planned(app)


def test_only_post_changes_anything(client, log_in):
    log_in()
    for method in (client.get, client.put, client.delete, client.patch):
        assert method("/api/planner/move").status_code == 405
    for method in (client.post, client.put, client.delete, client.patch):
        assert method("/api/planner/board").status_code == 405


# --- the move endpoint: whose plan ----------------------------------------------------------------------------------------------------------------

def test_a_student_only_ever_changes_their_own_plan(app, client, register):
    register()
    res = move(client, "41039", "Autumn 2027")
    assert res.status_code == 200
    conn = db.connect(app.config["DATABASE"])
    assert conn.execute("SELECT COUNT(*) FROM planned_subjects WHERE user_id = 1").fetchone()[0] == 0  # the demo student is untouched
    assert [tuple(r) for r in conn.execute("SELECT subject_code, session_label FROM planned_subjects WHERE user_id = 2")] == [("41039", "Autumn 2027")]
    conn.close()


def test_the_board_of_a_new_student_holds_none_of_the_demo_students_data(client, register):
    register()
    body = client.get("/api/planner/board").get_data(as_text=True)
    assert "John" not in body and "31265" not in json.dumps([c for col in client.get("/api/planner/board").get_json()["columns"] for c in col["cards"]])


def test_asking_for_the_board_changes_nothing(app, client, log_in):
    log_in()
    before = planned(app)
    client.get("/api/planner/board")
    client.get("/planner/board")
    assert planned(app) == before


# --- the layout rules that keep a long list usable (the browser does the drawing; these guard the rules) -------------------------------------

BOARD_CSS = (__import__("pathlib").Path(__file__).resolve().parents[3] / "frontend" / "src" / "board" / "board.css").read_text(encoding="utf-8")


def rule(selector):
    match = re.search(re.escape(selector) + r" \{([^}]*)\}", BOARD_CSS)
    assert match, selector
    return match.group(1)


def test_the_board_has_a_bounded_height_so_every_column_is_on_screen_at_once():
    board = rule(".board-scroll")
    assert "height: clamp(24rem, calc(100dvh - 19rem), 60rem)" in board and "overflow-x: auto" in board and "align-items: stretch" in board


def test_each_column_scrolls_inside_itself_instead_of_the_page_growing():
    column = rule(".board-col")
    assert "display: flex" in column and "flex-direction: column" in column and "max-height: 100%" in column and "min-height: 0" in column
    cards = rule(".board-cards")
    assert "overflow-y: auto" in cards and "flex: 1" in cards and "min-height: 0" in cards
    assert "overscroll-behavior: contain" in cards  # scrolling a list at its end does not scroll the page behind it
    assert "flex: none" in rule(".board-col-head")


def test_the_to_place_list_has_a_filter_and_groups_and_the_built_file_includes_them(client):
    assert ".board-filter" in BOARD_CSS and ".board-group-title" in BOARD_CSS and ".board-waiting" in BOARD_CSS
    built = client.get("/static/dist/board.css").get_data(as_text=True)
    assert ".board-filter" in built and "overflow-y:auto" in built.replace(" ", "")


def test_the_board_script_has_the_filter_the_groups_and_edge_scrolling(client):
    js = client.get("/static/dist/board.js").get_data(as_text=True)
    for marker in ("Filter subjects to place", "Show category", "Waiting on other subjects", "more (", "chosen)", "Needs rescheduling", "scrollLeft", "scrollTop"):
        assert marker in js, marker
