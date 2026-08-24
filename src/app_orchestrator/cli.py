"""CLI entry point for app-ox2."""

import sys
import logging
from pathlib import Path
from .orchestrator import Orchestrator

def run():
    print("DEBUG: cli.run() started")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    if len(sys.argv) < 2:
        print("Usage: app-ox2 <repo-path>")
        sys.exit(1)
    repo_path = Path(sys.argv[1])
    if not repo_path.exists():
        print(f"Error: {repo_path} does not exist")
        sys.exit(1)
    print("Enter your requirements (end with Ctrl-D on new line):")
    lines = sys.stdin.read()
    if not lines:
        print("No requirements provided.")
        sys.exit(1)
    orch = Orchestrator(repo_path)
    result = orch.run(lines)
    print("Pipeline result:", result)
