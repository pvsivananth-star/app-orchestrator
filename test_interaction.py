#!/usr/bin/env python3
"""Test the Interaction Agent directly."""

import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from app_orchestrator.orchestrator import Orchestrator

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def main():
    # Use the test repo
    repo_path = Path("../test-ox2")
    if not repo_path.exists():
        repo_path = Path(".")  # fallback to current dir
    
    print(f"Using repo: {repo_path.resolve()}")
    
    # Create orchestrator
    orch = Orchestrator(repo_path)
    
    # Run with a simple requirement
    requirements = "Build a simple calculator with add, subtract, multiply, divide"
    print(f"Requirements: {requirements}")
    print("\n" + "="*50)
    print("Running orchestrator...")
    print("="*50 + "\n")
    
    result = orch.run(requirements)
    
    print("\n" + "="*50)
    print("RESULT:")
    print("="*50)
    print(result)
    
    # Check what was written to .ox2
    ox2_path = repo_path / ".ox2"
    if ox2_path.exists():
        print("\n" + "="*50)
        print(".ox2 artifacts:")
        print("="*50)
        for f in sorted(ox2_path.iterdir()):
            if f.is_file():
                print(f"\n📄 {f.name}:")
                print("-" * 40)
                print(f.read_text()[:500])
                if len(f.read_text()) > 500:
                    print("... (truncated)")

if __name__ == "__main__":
    main()
