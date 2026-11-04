# MCP server

The app can offer its ten read-only tools to another AI application (for example Claude Desktop) over the Model Context Protocol.

## What it is, and is not
- **Read-only.** No tool can enrol, withdraw, plan, move, swap or change anything. They return facts.
- **One student.** It is bound to one student when it starts (the simulated demo student, `DEMO0001`, by default). The tools never take a
  student, so a caller cannot ask about anyone else.
- **A snapshot.** It reads an in-memory copy of the database, opened read-only from the file, so it cannot modify the real data. Restart it
  to see newer data.
- **Local only.** It talks over standard input and output to the application that starts it. It opens no network port.
- **Simulated data.** Everything it returns is simulated, not genuine UTS academic records.

## Run it by hand
```bash
python -m mcp_server --db enrolment_hub.db --student DEMO0001
```
It prints one line to stderr when it is ready, then waits for newline-delimited JSON-RPC messages on stdin.

## Use it from Claude Desktop
Add this to Claude Desktop's configuration (`claude_desktop_config.json`), changing the two paths to your own:
```json
{
  "mcpServers": {
    "enrolment-hub": {
      "command": "C:\\Users\\camel\\PROJECTS\\enrolment-hub\\.venv\\Scripts\\python.exe",
      "args": ["-m", "mcp_server", "--db", "enrolment_hub.db"],
      "cwd": "C:\\Users\\camel\\PROJECTS\\enrolment-hub"
    }
  }
}
```
Restart Claude Desktop, then ask something like "What is my degree plan?" or "Should I swap to Networking and Cybersecurity?".

## The tools
search_subjects, get_subject_info, check_prerequisites, list_offerings, check_plan_placement, get_my_plan, get_session_workload,
find_clash_free_classes, get_my_results and get_swap_advice. They are the same functions the AI mode uses, so the answers match the app.
