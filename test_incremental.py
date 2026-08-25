#!/usr/bin/env python3
"""Test the incremental code generator with Ollama."""

import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from app_orchestrator.providers import ProviderRegistry
from app_orchestrator.workspace import Workspace
from app_orchestrator.state import PipelineState
from app_orchestrator.incremental import IncrementalCodeGenerator

# Enable logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

def main():
    # Setup
    repo_path = Path("../test-ox2")
    workspace = Workspace(repo_path)
    state = PipelineState()
    registry = ProviderRegistry()

    # Create a requirements file
    requirements = """# Calculator Application

## Overview
Build a Python CLI calculator with add, subtract, multiply, divide operations.

## User Stories
- As a user, I want to add two numbers.
- As a user, I want to subtract two numbers.
- As a user, I want to multiply two numbers.
- As a user, I want to divide two numbers.

## Functional Requirements
- FR-1: The calculator shall accept two numbers and an operation.
- FR-2: The calculator shall return the correct result.
- FR-3: The calculator shall handle division by zero.
- FR-4: The calculator shall handle invalid input.

## Technical Specifications
- Language: Python 3.14
- Architecture: CLI
- Testing: pytest

## Acceptance Criteria
- AC-1: Add operation returns correct result.
- AC-2: Subtract operation returns correct result.
- AC-3: Multiply operation returns correct result.
- AC-4: Divide operation returns correct result.
- AC-5: Division by zero shows error message.
- AC-6: Invalid input shows error message.
"""

    workspace.write("requirements.md", requirements)
    print(f"✅ Requirements written ({len(requirements)} chars)")

    # Create generator with Ollama
    gen = IncrementalCodeGenerator(
        workspace,
        state,
        registry,
        provider_chain=['ollama', 'FAIL'],
        config={
            'max_chunk_iterations': 3,
            'verify_each_chunk': False,
            'target_chunk_kb': 0.5,
            'min_requirements_length': 50,
        }
    )

    print("\n🚀 Starting incremental generation...")
    print("=" * 50)

    result = gen.generate(requirements)

    print("\n" + "=" * 50)
    print("📊 RESULTS")
    print("=" * 50)
    print(f"Status: {result.status}")
    print(f"Chunks: {result.chunks_completed} / {result.chunks_total}")
    print(f"Iterations: {result.iterations}")
    print(f"Files created: {result.files_created}")
    print(f"Duration: {result.duration_seconds:.2f}s")

    if result.errors:
        print(f"\n❌ Errors: {result.errors}")

    # Check generated files
    print("\n📁 Generated files in repo:")
    repo_files = list(repo_path.glob("*.py"))
    if repo_files:
        for f in repo_files:
            print(f"  - {f.name} ({f.stat().st_size} bytes)")
    else:
        print("  No Python files found")

    # Show the main file if it exists
    main_file = repo_path / "src" / "main.py"
    if main_file.exists():
        print(f"\n📄 Contents of {main_file}:")
        print("=" * 50)
        print(main_file.read_text()[:500])
        print("... (truncated)")
    else:
        # Try alternative locations
        alt_files = list(repo_path.glob("**/main.py")) + list(repo_path.glob("*.py"))
        if alt_files:
            f = alt_files[0]
            print(f"\n📄 Contents of {f.relative_to(repo_path)}:")
            print("=" * 50)
            print(f.read_text()[:500])
            print("... (truncated)")

if __name__ == "__main__":
    main()
