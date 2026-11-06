"""The contract between the server (features/dashboard/service.py) and the React page (frontend/src/contract.ts).

The React side validates the checked-in fixtures against its strict schema (npm test). This side checks the fixtures are exactly
what the server sends now. So if either side changes alone, one of the two test suites fails.
To accept a deliberate change:  UPDATE_CONTRACT=1 python -m pytest tests/features/dashboard/test_contract.py  then  npm test  in frontend/.
"""
import json
import os
import re
from pathlib import Path

import pytest

from features.dashboard.service import build_dashboard
from features.enrolment.presets import PRESETS
from shared import db

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "frontend" / "src" / "test" / "fixtures"
CONTRACT = (ROOT / "frontend" / "src" / "contract.ts").read_text(encoding="utf-8")
KEYS = list(PRESETS)


def server_data(tmp_path, key):
    path = tmp_path / f"{key}.db"
    db.build_database(str(path), demo_profile=key)
    conn = db.connect(str(path))
    try:
        return build_dashboard(conn, 1)
    finally:
        conn.close()


@pytest.mark.parametrize("key", KEYS)
def test_the_fixture_is_exactly_what_the_server_sends(tmp_path, key):
    data = server_data(tmp_path, key)
    path = FIXTURES / f"dashboard.{key}.json"
    if os.environ.get("UPDATE_CONTRACT") == "1":
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    assert json.loads(path.read_text(encoding="utf-8")) == data, (
        "the server's dashboard data no longer matches the checked-in fixture: run "
        "UPDATE_CONTRACT=1 python -m pytest tests/features/dashboard/test_contract.py, then npm test in frontend/")


def test_there_is_a_fixture_for_every_starting_point_and_nothing_else():
    assert sorted(p.name for p in FIXTURES.glob("dashboard.*.json")) == sorted(f"dashboard.{k}.json" for k in KEYS)


def all_keys(value, found=None):
    found = set() if found is None else found
    if isinstance(value, dict):
        for k, v in value.items():
            found.add(k)
            all_keys(v, found)
    elif isinstance(value, list):
        for item in value:
            all_keys(item, found)
    return found


def test_every_key_the_server_sends_is_in_the_typescript_contract(tmp_path):
    keys = set()
    for key in KEYS:
        keys |= all_keys(server_data(tmp_path, key))
    assert keys and [k for k in sorted(keys) if not re.search(rf"\b{re.escape(k)}\b", CONTRACT)] == []


def test_every_workload_and_step_kind_the_server_can_send_is_in_the_contract(tmp_path):
    seen_workloads, seen_kinds = set(), set()
    for key in KEYS:
        data = server_data(tmp_path, key)
        seen_workloads |= {s["workload"] for s in data["sessions"] if s["workload"]}
        seen_kinds |= {s["kind"] for s in data["next_steps"]}
    assert all(f'"{w}"' in CONTRACT for w in seen_workloads) and all(f'"{k}"' in CONTRACT for k in seen_kinds)
    assert {"heavy", "light", "too_heavy"} <= seen_workloads and {"setup", "retake", "blocked", "enrol", "workload"} <= seen_kinds


def test_the_contract_only_allows_links_that_stay_on_this_site(tmp_path):
    assert "SAME_SITE_PATH" in CONTRACT
    for key in KEYS:
        for step in server_data(tmp_path, key)["next_steps"]:
            assert re.match(r"^/(?![/\\])", step["href"])


# --- the island's source ---------------------------------------------------------------------------------------------------------------------------

def test_the_dashboard_source_has_no_hard_coded_colours():
    sources = [p for p in (ROOT / "frontend" / "src").rglob("*") if p.suffix in (".css", ".tsx", ".ts") and ".test." not in p.name and "test" not in p.parts]
    assert sources
    for path in sources:
        text = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(", text), path.name


def test_the_frontend_pins_exact_versions_and_a_lock_file():
    package = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    versions = {**package["dependencies"], **package["devDependencies"]}
    assert versions and all(re.fullmatch(r"\d+\.\d+\.\d+", v) for v in versions.values()), versions
    assert (ROOT / "frontend" / "package-lock.json").is_file() and package["private"] is True


def test_node_modules_are_never_committed():
    assert "node_modules/" in (ROOT / ".gitignore").read_text(encoding="utf-8")
