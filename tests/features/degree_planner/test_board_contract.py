"""The contract between the planner board's server side (features/degree_planner/board.py and api.py) and the React board
(frontend/src/board/contract.ts): fixtures made from the real server, checked from both sides. See the dashboard's contract test.
To accept a deliberate change:  UPDATE_CONTRACT=1 python -m pytest tests/features/degree_planner/test_board_contract.py  then  npm test."""
import json
import os
import re
from pathlib import Path

import pytest

from app import create_app
from features.degree_planner.board import build_board
from features.enrolment.presets import PRESETS
from shared import db

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "frontend" / "src" / "test" / "fixtures"
CONTRACT = (ROOT / "frontend" / "src" / "board" / "contract.ts").read_text(encoding="utf-8")
KEYS = list(PRESETS)
TOKEN = re.compile(r'name="csrf_token" value="([^"]+)"')


def check_fixture(name, data):
    path = FIXTURES / name
    if os.environ.get("UPDATE_CONTRACT") == "1":
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    assert json.loads(path.read_text(encoding="utf-8")) == data, (
        f"{name} no longer matches what the server sends: run UPDATE_CONTRACT=1 python -m pytest "
        "tests/features/degree_planner/test_board_contract.py, then npm test in frontend/")


@pytest.mark.parametrize("key", KEYS)
def test_the_board_fixture_is_exactly_what_the_server_sends(tmp_path, key):
    path = tmp_path / f"{key}.db"
    db.build_database(str(path), demo_profile=key)
    conn = db.connect(str(path))
    try:
        check_fixture(f"board.{key}.json", build_board(conn, 1))
    finally:
        conn.close()


@pytest.fixture()
def failed_client(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_PROFILE", "failed")
    app = create_app({"DATABASE": str(tmp_path / "failed.db"), "TESTING": True, "SECRET_KEY": "k"})
    client = app.test_client()
    csrf = TOKEN.search(client.get("/login").get_data(as_text=True)).group(1)
    client.post("/login", data={"email": "john.doe@student.uni.edu.au", "password": "Johndoe#1", "csrf_token": csrf})
    return client, TOKEN.search(client.get("/profile").get_data(as_text=True)).group(1)


def post(client, token, body):
    return client.post("/api/planner/move", json=body, headers={"X-CSRF-Token": token})


def test_the_move_answers_are_exactly_what_the_server_sends(failed_client):
    client, token = failed_client
    ok = post(client, token, {"code": "48024", "to": "Spring 2027"})
    assert ok.status_code == 200
    check_fixture("move.ok.json", ok.get_json())
    refused = post(client, token, {"code": "48024", "to": "Autumn 2029"})  # Data Structures needs it first
    assert refused.status_code == 422 and "31251 Data Structures and Algorithms is planned for Spring 2027" in refused.get_json()["error"]
    check_fixture("move.refused.json", refused.get_json())
    bad = post(client, token, {"code": "48024", "to": "Winter 2029"})
    assert bad.status_code == 400
    check_fixture("move.bad.json", bad.get_json())


def test_there_are_exactly_the_fixtures_the_board_uses():
    names = sorted(p.name for p in FIXTURES.glob("*.json"))
    assert [n for n in names if n.startswith(("board.", "move."))] == sorted(
        [f"board.{k}.json" for k in KEYS] + ["move.bad.json", "move.ok.json", "move.refused.json"])


def keys_of(value, found=None):
    found = set() if found is None else found
    if isinstance(value, dict):
        for k, v in value.items():
            found.add(k)
            keys_of(v, found)
    elif isinstance(value, list):
        for item in value:
            keys_of(item, found)
    return found


def test_every_key_the_server_sends_is_in_the_typescript_contract(failed_client, tmp_path):
    client, token = failed_client
    sent = keys_of(post(client, token, {"code": "48024", "to": "Spring 2027"}).get_json())
    for key in KEYS:
        path = tmp_path / f"k{key}.db"
        db.build_database(str(path), demo_profile=key)
        sent |= keys_of(build_board(db.connect(str(path)), 1))
    assert sent and [k for k in sorted(sent) if not re.search(rf"\b{re.escape(k)}\b", CONTRACT)] == []


def test_every_card_state_the_server_can_send_is_in_the_contract(tmp_path):
    states = set()
    for key in KEYS:
        path = tmp_path / f"s{key}.db"
        db.build_database(str(path), demo_profile=key)
        board = build_board(db.connect(str(path)), 1)
        states |= {c["state"] for c in board["to_place"]} | {c["state"] for col in board["columns"] for c in col["cards"]}
    assert {"enrolled", "planned", "todo"} <= states and all(f'"{s}"' in CONTRACT for s in states | {"stranded"})
