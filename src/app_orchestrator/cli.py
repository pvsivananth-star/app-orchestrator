import sys
import logging
import traceback
from pathlib import Path
from .orchestrator import Orchestrator

def run():
    print("DEBUG: cli.run() entered", file=sys.stderr)
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
    if len(sys.argv) < 2:
        print("Usage: app-ox2 <repo-path>")
        sys.exit(1)
    repo_path = Path(sys.argv[1])
    if not repo_path.exists():
        print(f"Error: {repo_path} does not exist")
        sys.exit(1)
    print("Enter your requirements (end with Ctrl-D on new line):", file=sys.stderr)
    lines = sys.stdin.read()
    if not lines:
        print("No requirements provided.")
        sys.exit(1)
    print(f"DEBUG: requirements read: {lines[:50]}...", file=sys.stderr)
    print("DEBUG: creating Orchestrator", file=sys.stderr)
    try:
        orch = Orchestrator(repo_path)
        print("DEBUG: orchestrator created, calling run", file=sys.stderr)
        result = orch.run(lines)
        print("Pipeline result:", result)
    except Exception as e:
        print(f"Pipeline failed with exception: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)