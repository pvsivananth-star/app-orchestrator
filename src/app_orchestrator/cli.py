"""CLI entry point for app-ox2."""

import sys
import logging
from pathlib import Path
from .orchestrator import Orchestrator

def run():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
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
    orch = Orchestrator(repo_path)
    try:
        result = orch.run(lines)
        # Print result to stdout so it's visible
        print("\n" + "="*60)
        print("✅ Pipeline Result")
        print("="*60)
        print(f"Status: {result.get('status')}")
        if result.get('message'):
            print(f"Message: {result.get('message')}")
        if result.get('files_written'):
            print(f"Files written: {result.get('files_written')}")
        if result.get('state'):
            stage = result.get('state', {}).get('stage', 'unknown')
            print(f"Stage: {stage}")
        print("="*60)
        # Also show what files were created in .ox2
        ox2_path = repo_path / ".ox2"
        if ox2_path.exists():
            print("\n📁 .ox2 artifacts:")
            for f in sorted(ox2_path.iterdir()):
                if f.is_file():
                    print(f"  - {f.name}")
        print("="*60)
    except Exception as e:
        print(f"Pipeline failed with exception: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)