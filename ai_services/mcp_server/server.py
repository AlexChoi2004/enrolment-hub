"""A Model Context Protocol (MCP) server that offers the app's ten read-only tools to another AI application.

Safety, by design:
  * it speaks over stdin/stdout only (the application that starts it talks to it); there is no network port to attack;
  * it works on an in-memory SNAPSHOT of the database, opened read-only from the file, so nothing it does, even a bug, can
    change the real data (restart it to see newer data);
  * it is bound to ONE student when it starts (the simulated demo student by default); the tools never take a student, so a
    caller cannot ask about anyone else;
  * every call goes through the same registry as the AI mode: arguments are checked, and no tool changes anything.
It implements just what is needed: initialize, ping, tools/list and tools/call (newline-delimited JSON-RPC 2.0).
"""
import json
import sqlite3
import sys

from ai_services.tools.registry import TOOLS, call_tool, tool_specs

SUPPORTED = ("2025-06-18", "2025-03-26", "2024-11-05")
MAX_LINE = 100_000
NAME, VERSION = "enrolment-hub", "1.0.0"
INSTRUCTIONS = (
    "Read-only tools about ONE simulated student in a UTS-style enrolment demonstration: their plan, results, workload, prerequisites "
    "and swap advice, and facts about subjects. They cannot change anything. All data is simulated, not genuine UTS academic records."
)
PARSE_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND, INVALID_PARAMS = -32700, -32600, -32601, -32602


class SetupError(Exception):
    """The server could not start (no database, or no such student)."""


def snapshot(path):
    """An in-memory copy of the database. The file is opened read-only, so it is never written to."""
    try:
        source = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise SetupError(f"Could not open the database at {path}: {exc}") from exc
    try:
        memory = sqlite3.connect(":memory:")
        source.backup(memory)
    except sqlite3.Error as exc:
        raise SetupError(f"Could not read the database at {path}: {exc}") from exc
    finally:
        source.close()
    memory.row_factory = sqlite3.Row
    memory.execute("PRAGMA foreign_keys = ON")
    return memory


def student_id(conn, student_number):
    row = conn.execute("SELECT id FROM users WHERE student_number = ?", (student_number,)).fetchone()
    if row is None:
        raise SetupError(f"There is no student with number {student_number}.")
    return row["id"]


def _error(request_id, code, message):
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


class Server:
    def __init__(self, conn, user_id):
        self.conn, self.user_id = conn, user_id

    def handle(self, message):
        """Handle one decoded message. Returns the response dict, or None when no response is due (a notification)."""
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
            return _error(message.get("id") if isinstance(message, dict) else None, INVALID_REQUEST, "Invalid request.")
        method, params, request_id = message["method"], message.get("params") or {}, message.get("id")
        if "id" not in message:  # a notification, for example notifications/initialized
            return None
        if not isinstance(params, dict):
            return _error(request_id, INVALID_PARAMS, "params must be an object.")
        if method == "initialize":
            wanted = params.get("protocolVersion")
            return {"jsonrpc": "2.0", "id": request_id, "result": {
                "protocolVersion": wanted if wanted in SUPPORTED else SUPPORTED[0],
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": NAME, "version": VERSION}, "instructions": INSTRUCTIONS}}
        if method == "ping":
            return {"jsonrpc": "2.0", "id": request_id, "result": {}}
        if method == "tools/list":
            tools = [{"name": s["name"], "description": s["description"], "inputSchema": s["input_schema"],
                      "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}}
                     for s in tool_specs()]
            return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": tools}}
        if method == "tools/call":
            name, arguments = params.get("name"), params.get("arguments", {})
            if not isinstance(name, str) or name not in TOOLS:
                return _error(request_id, INVALID_PARAMS, f"Unknown tool: {name}")
            if not isinstance(arguments, dict):
                return _error(request_id, INVALID_PARAMS, "arguments must be an object.")
            result = call_tool(self.conn, self.user_id, name, arguments)
            text = json.dumps(result["data"], indent=1, default=str) if result["ok"] else result["error"]
            return {"jsonrpc": "2.0", "id": request_id,
                    "result": {"content": [{"type": "text", "text": text}], "isError": not result["ok"]}}
        return _error(request_id, METHOD_NOT_FOUND, f"Method not found: {method}")

    def handle_line(self, line):
        """Decode one line of input and handle it. Returns the response as text, or None."""
        if len(line) > MAX_LINE:
            return json.dumps(_error(None, INVALID_REQUEST, "The message is too long."))
        try:
            message = json.loads(line)
        except ValueError:
            return json.dumps(_error(None, PARSE_ERROR, "Parse error."))
        response = self.handle(message)
        return None if response is None else json.dumps(response)


def serve(server, stdin=None, stdout=None):
    """Read one JSON message per line and answer each. Only JSON is ever written to stdout."""
    stdin, stdout = stdin or sys.stdin, stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        response = server.handle_line(line)
        if response is not None:
            stdout.write(response + "\n")
            stdout.flush()
