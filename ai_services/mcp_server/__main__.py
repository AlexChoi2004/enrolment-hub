"""Start the MCP server: python -m mcp_server [--db enrolment_hub.db] [--student DEMO0001]."""
import argparse
import os
import sys

from features.accounts.seed import DEMO_STUDENT_NUMBER
from ai_services.mcp_server.server import Server, SetupError, serve, snapshot, student_id


def main(argv=None):
    parser = argparse.ArgumentParser(prog="mcp_server", description="Read-only MCP tools for one simulated student.")
    parser.add_argument("--db", default=os.getenv("ENROLMENT_DB", "enrolment_hub.db"), help="the SQLite database file (opened read-only)")
    parser.add_argument("--student", default=os.getenv("MCP_STUDENT", DEMO_STUDENT_NUMBER), help="the student number the tools are bound to")
    args = parser.parse_args(argv)
    try:
        conn = snapshot(args.db)
        user_id = student_id(conn, args.student)
    except SetupError as exc:
        print(f"mcp_server: {exc}", file=sys.stderr)  # stdout is reserved for the protocol
        return 2
    print(f"mcp_server: serving read-only tools for student {args.student} from a snapshot of {args.db}", file=sys.stderr)
    serve(Server(conn, user_id))
    return 0


if __name__ == "__main__":
    sys.exit(main())
