#!/bin/bash
# test_agents.sh - Test the full agent pipeline

echo "=========================================="
echo "Testing Agent Pipeline"
echo "=========================================="

# Clean previous artifacts
rm -rf ../test-ox2/.ox2 2>/dev/null || true

# Run the orchestrator with a simple request
echo "Build a simple calculator with add, subtract, multiply, divide" | uv run python -c "
import sys
import logging
sys.path.insert(0, 'src')
from app_orchestrator.cli import run
run()
" ../test-ox2

echo ""
echo "=========================================="
echo ".ox2 Artifacts:"
echo "=========================================="
ls -la ../test-ox2/.ox2/ 2>/dev/null || echo "No .ox2 folder found"
echo ""

if [ -f ../test-ox2/.ox2/requirements.md ]; then
    echo "✅ requirements.md found!"
    echo ""
    echo "Contents of requirements.md (first 500 chars):"
    echo "----------------------------------------"
    head -c 500 ../test-ox2/.ox2/requirements.md
    echo ""
    echo "... (truncated)"
else
    echo "❌ requirements.md not found"
fi

echo ""
echo "=========================================="
echo "Done!"
echo "=========================================="