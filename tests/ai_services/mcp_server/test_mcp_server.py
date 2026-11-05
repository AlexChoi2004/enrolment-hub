import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from ai_services.mcp_server.__main__ import main
from ai_services.mcp_server.server import MAX_LINE, SUPPORTED, Server, SetupError, serve, snapshot, student_id
from shared import db
from ai_services.tools.registry import TOOLS

VALID = {
    "search_subjects": {"query": "Programming"}, "get_subject_info": {"code": "41026"}, "check_prerequisites": {"code": "41052"},
    "list_offerings": {"code": "41026"}, "check_plan_placement": {"code": "41052", "session": "Spring 2027"}, "get_my_plan": {},
    "get_session_workload": {"session": "Autumn 2027"}, "find_clash_free_classes": {"code": "41026", "session": "Autumn 2027"},
    "get_my_results": {}, "get_swap_advice": {"kind": "major", "code": "MAJ10053"},
}


@pytest.fixture()
def db_file(tmp_path):
    path = tmp_path / "demo.db"
    db.build_database(str(path), demo_profile="sample")
    return path


@pytest.fixture()
def server(db_file):
    conn = snapshot(str(db_file))
    return Server(conn, student_id(conn, "DEMO0001"))


def rpc(server, method, params=None, request_id=1):
    message = {"jsonrpc": "2.0", "method": method, "id": request_id}
    if params is not None:
        message["params"] = params
    return server.handle(message)


def call(server, name, arguments=None, request_id=1):
    return rpc(server, "tools/call", {"name": name, **({} if arguments is None else {"arguments": arguments})}, request_id)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# --- the handshake -----------------------------------------------------------------------------------------------------------------------

def test_initialize_negotiates_the_protocol_and_offers_only_tools(server):
    response = rpc(server, "initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "x", "version": "1"}})
    result = response["result"]
    assert response["jsonrpc"] == "2.0" and response["id"] == 1
    assert result["protocolVersion"] == "2025-03-26" and result["capabilities"] == {"tools": {"listChanged": False}}
    assert result["serverInfo"] == {"name": "enrolment-hub", "version": "1.0.0"} and "Read-only" in result["instructions"]


def test_an_unknown_protocol_version_gets_the_latest_supported(server):
    assert rpc(server, "initialize", {"protocolVersion": "1999-01-01"})["result"]["protocolVersion"] == SUPPORTED[0]


def test_the_initialized_notification_gets_no_response(server):
    assert server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_ping_answers_with_an_empty_result(server):
    assert rpc(server, "ping") == {"jsonrpc": "2.0", "id": 1, "result": {}}


def test_request_ids_are_echoed_back(server):
    assert rpc(server, "ping", request_id="abc-7")["id"] == "abc-7" and rpc(server, "ping", request_id=0)["id"] == 0


# --- listing the tools ----------------------------------------------------------------------------------------------------------------------

def test_the_ten_tools_are_listed_as_read_only_with_closed_schemas(server):
    tools = rpc(server, "tools/list")["result"]["tools"]
    assert sorted(t["name"] for t in tools) == sorted(TOOLS) and len(tools) == 10
    for t in tools:
        assert t["description"] and t["inputSchema"]["type"] == "object" and t["inputSchema"]["additionalProperties"] is False
        assert t["annotations"] == {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}


def test_no_listed_tool_takes_a_student(server):
    for t in rpc(server, "tools/list")["result"]["tools"]:
        assert not set(t["inputSchema"]["properties"]) & {"user", "user_id", "student", "student_id", "id", "email"}


# --- calling the tools --------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("name", list(VALID))
def test_every_tool_can_be_called(server, name):
    result = call(server, name, VALID[name])["result"]
    assert result["isError"] is False and result["content"][0]["type"] == "text"
    assert json.loads(result["content"][0]["text"])  # the result is JSON text


def test_the_tool_answers_for_the_bound_student(server):
    plan = json.loads(call(server, "get_my_plan", {})["result"]["content"][0]["text"])
    assert plan["period"] == {"label": "Autumn 2027", "year": 3, "semester": 1}


def test_a_bad_argument_is_a_tool_error_not_a_protocol_error(server):
    result = call(server, "get_subject_info", {"code": "41039'; DROP TABLE subjects;--"})["result"]
    assert result["isError"] is True and "not in the expected format" in result["content"][0]["text"]


def test_a_caller_cannot_name_another_student(server):
    result = call(server, "get_my_results", {"user_id": 2})["result"]
    assert result["isError"] is True and "Unknown argument: user_id" in result["content"][0]["text"]


def test_an_unknown_tool_is_an_invalid_params_error(server):
    response = call(server, "delete_everything", {})
    assert response["error"]["code"] == -32602 and "Unknown tool" in response["error"]["message"] and "result" not in response


@pytest.mark.parametrize("params", [{}, {"name": 5}, {"name": ["get_my_plan"]}, {"name": "get_my_plan", "arguments": "x"}, {"name": "get_my_plan", "arguments": [1]}])
def test_malformed_tool_calls_are_invalid_params(server, params):
    assert rpc(server, "tools/call", params)["error"]["code"] == -32602


def test_each_student_binding_is_separate(db_file):
    conn = snapshot(str(db_file))
    from features.accounts.service import create_user

    fresh = create_user(conn, "new.student@student.uni.edu.au", "Str0ng#Pass", "Autumn 2027")["id"]
    a, b = Server(conn, 1), Server(conn, fresh)
    year = lambda s: json.loads(call(s, "get_my_plan", {})["result"]["content"][0]["text"])["period"]["year"]
    assert (year(a), year(b)) == (3, 1)


# --- protocol errors -------------------------------------------------------------------------------------------------------------------------

def test_an_unknown_method_is_method_not_found(server):
    assert rpc(server, "resources/list")["error"]["code"] == -32601


@pytest.mark.parametrize("message", [{"method": "ping", "id": 1}, {"jsonrpc": "1.0", "method": "ping", "id": 1}, {"jsonrpc": "2.0", "id": 1},
                                     {"jsonrpc": "2.0", "method": 7, "id": 1}, [1, 2], "ping", 5, None])
def test_an_invalid_request_is_refused(server, message):
    assert server.handle(message)["error"]["code"] == -32600


def test_params_must_be_an_object(server):
    assert rpc(server, "tools/list", [1, 2])["error"]["code"] == -32602


def test_a_line_that_is_not_json_is_a_parse_error(server):
    assert json.loads(server.handle_line("not json"))["error"] == {"code": -32700, "message": "Parse error."}


def test_a_huge_line_is_refused(server):
    assert json.loads(server.handle_line("x" * (MAX_LINE + 1)))["error"]["code"] == -32600


# --- the loop: only JSON on the output ------------------------------------------------------------------------------------------------------

def test_the_loop_answers_each_request_and_ignores_notifications_and_blank_lines(server):
    lines = "\n".join([
        json.dumps({"jsonrpc": "2.0", "method": "initialize", "id": 1, "params": {}}),
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}), "", "   ",
        json.dumps({"jsonrpc": "2.0", "method": "tools/list", "id": 2}), "garbage",
    ]) + "\n"
    out = io.StringIO()
    serve(server, io.StringIO(lines), out)
    replies = [json.loads(line) for line in out.getvalue().splitlines()]
    assert [r["id"] for r in replies] == [1, 2, None] and replies[2]["error"]["code"] == -32700


# --- it cannot change the real data -----------------------------------------------------------------------------------------------------------

def test_calling_every_tool_leaves_the_database_file_untouched(db_file):
    before = digest(db_file)
    conn = snapshot(str(db_file))
    s = Server(conn, student_id(conn, "DEMO0001"))
    for name, args in VALID.items():
        call(s, name, args)
    call(s, "get_swap_advice", {"kind": "electives"})
    assert digest(db_file) == before


def test_even_a_deliberate_write_to_the_snapshot_never_reaches_the_file(db_file):
    before = digest(db_file)
    conn = snapshot(str(db_file))
    conn.execute("DELETE FROM enrolments")
    conn.execute("DELETE FROM users")
    conn.commit()
    assert digest(db_file) == before
    assert db.connect(str(db_file)).execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1


def test_the_file_is_opened_read_only(db_file, monkeypatch):
    seen = []
    import sqlite3 as sqlite

    real = sqlite.connect
    monkeypatch.setattr("ai_services.mcp_server.server.sqlite3.connect", lambda target, *a, **kw: (seen.append(target), real(target, *a, **kw))[1])
    snapshot(str(db_file))
    assert any(isinstance(t, str) and t.endswith("?mode=ro") and t.startswith("file:") for t in seen)


# --- starting it ---------------------------------------------------------------------------------------------------------------------------------

def test_a_missing_database_is_a_clear_setup_error(tmp_path):
    with pytest.raises(SetupError, match="Could not open the database"):
        snapshot(str(tmp_path / "nope.db"))


def test_a_file_that_is_not_a_database_is_a_clear_setup_error(tmp_path):
    bad = tmp_path / "bad.db"
    bad.write_text("not a database")
    with pytest.raises(SetupError):
        snapshot(str(bad))


def test_an_unknown_student_is_a_clear_setup_error(db_file):
    with pytest.raises(SetupError, match="There is no student with number NOBODY"):
        student_id(snapshot(str(db_file)), "NOBODY")


def test_main_returns_2_and_writes_to_stderr_for_a_setup_problem(tmp_path, capsys):
    assert main(["--db", str(tmp_path / "nope.db")]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and "Could not open the database" in captured.err


def test_main_returns_2_for_an_unknown_student(db_file, capsys):
    assert main(["--db", str(db_file), "--student", "NOBODY"]) == 2
    assert capsys.readouterr().out == ""


# --- run it as a real process, as another application would ------------------------------------------------------------------------------------

def test_the_server_works_as_a_separate_process_and_writes_only_json_to_stdout(db_file):
    root = Path(__file__).resolve().parents[3]
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "get_my_results", "arguments": {}}},
    ]
    done = subprocess.run(
        [sys.executable, "-m", "ai_services.mcp_server", "--db", str(db_file)], input="\n".join(json.dumps(m) for m in messages) + "\n",
        capture_output=True, text=True, cwd=root, timeout=90,
    )
    assert done.returncode == 0 and "serving read-only tools for student DEMO0001" in done.stderr
    replies = [json.loads(line) for line in done.stdout.splitlines()]  # every line of stdout must be JSON
    assert [r["id"] for r in replies] == [1, 2, 3] and len(replies[1]["result"]["tools"]) == 10
    assert json.loads(replies[2]["result"]["content"][0]["text"])["passed_credit_points"] == 96


def test_the_process_exits_with_2_for_a_missing_database(tmp_path):
    root = Path(__file__).resolve().parents[3]
    done = subprocess.run([sys.executable, "-m", "ai_services.mcp_server", "--db", str(tmp_path / "nope.db")], input="", capture_output=True, text=True, cwd=root, timeout=60)
    assert done.returncode == 2 and done.stdout == "" and "Could not open the database" in done.stderr
