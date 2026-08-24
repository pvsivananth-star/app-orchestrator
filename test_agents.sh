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
else
    echo "❌ requirements.md not found"
fi

if [ -f ../test-ox2/.ox2/clarified_requirements.md ]; then
    echo "✅ clarified_requirements.md found!"
else
    echo "❌ clarified_requirements.md not found"
fi

if [ -f ../test-ox2/.ox2/compile.log ]; then
    echo "✅ compile.log found!"
    echo ""
    echo "Compile log:"
    echo "----------------------------------------"
    cat ../test-ox2/.ox2/compile.log
else
    echo "❌ compile.log not found"
fi

if [ -f ../test-ox2/.ox2/implementation_log.md ]; then
    echo "✅ implementation_log.md found!"
else
    echo "❌ implementation_log.md not found"
fi

echo ""
echo "=========================================="
echo "Generated Files in Repository:"
echo "=========================================="
find ../test-ox2 -maxdepth 1 -type f -not -name ".*" -not -name "LICENSE" -not -name "README.md" -not -name ".gitignore" 2>/dev/null | head -20

echo ""
echo "=========================================="
echo "Done!"
echo "=========================================="