#!/bin/bash

# test_code_gen.sh
# Incremental code-generation integration test
#
# Test repository:
#   ../test-ox2
#
# Purpose:
#   Verify that a multi-file project is generated incrementally
#   instead of being sent to an AI provider as one large request.

set -e

echo "============================================================"
echo " App Orchestrator - Incremental Code Generation Test"
echo "============================================================"
echo ""

TEST_REPO="../test-ox2"

if [ ! -d "$TEST_REPO" ]; then
    echo "ERROR: Test repository not found:"
    echo "  $TEST_REPO"
    exit 1
fi

echo "Test repository:"
echo "  $TEST_REPO"
echo ""

# ------------------------------------------------------------
# Clean ONLY orchestrator artifacts and previously generated
# source files.
#
# IMPORTANT:
# Do NOT remove README.md.
# README.md is the requirement source for this test.
# ------------------------------------------------------------

echo "Cleaning previous orchestrator artifacts..."

rm -rf "$TEST_REPO/.ox2"

# Remove source files from previous test runs.
# Keep README, LICENSE and git files intact.
find "$TEST_REPO" \
    -type f \
    \( \
        -name "*.java" \
        -o -name "*.class" \
        -o -name "*.jar" \
    \) \
    -delete 2>/dev/null || true

echo "Clean complete."
echo ""

# ------------------------------------------------------------
# Validate README
# ------------------------------------------------------------

if [ ! -f "$TEST_REPO/README.md" ]; then
    echo "ERROR: $TEST_REPO/README.md not found."
    exit 1
fi

README_BYTES=$(wc -c < "$TEST_REPO/README.md" | tr -d ' ')
README_LINES=$(wc -l < "$TEST_REPO/README.md" | tr -d ' ')

echo "Requirement source:"
echo "  README.md"
echo "  Bytes : $README_BYTES"
echo "  Lines : $README_LINES"
echo ""

# ------------------------------------------------------------
# Show requirement
# ------------------------------------------------------------

echo "============================================================"
echo " REQUIREMENTS"
echo "============================================================"
cat "$TEST_REPO/README.md"
echo ""
echo "============================================================"
echo ""

# ------------------------------------------------------------
# Run orchestrator
# ------------------------------------------------------------

START_TIME=$(date +%s)

echo "Starting incremental orchestrator..."
echo ""

uv run python -c "
import os
import sys
from pathlib import Path

sys.path.insert(0, 'src')

from app_orchestrator.orchestrator import Orchestrator


repo = Path('$TEST_REPO').resolve()

print('=' * 60)
print('Running Orchestrator')
print('=' * 60)
print('Repository:', repo)
print('')

orch = Orchestrator(repo)

result = orch.run(
    '''\
$(cat "$TEST_REPO/README.md")
'''
)

print('')
print('=' * 60)
print('ORCHESTRATOR RESULT')
print('=' * 60)

status = result.get('status', 'unknown')

print('Status:', status)
print('Message:', result.get('message', ''))

state = result.get('state', {})
metadata = state.get('metadata', {})

print('')
print('Implementation mode:',
      metadata.get('implementation_mode', 'unknown'))

print('Implementation complete:',
      metadata.get('implementation_complete', 'unknown'))

print('Chunks completed:',
      metadata.get('implementation_chunks_completed', 'unknown'))

print('Chunks total:',
      metadata.get('implementation_chunks_total', 'unknown'))

print('Iterations:',
      metadata.get('implementation_iterations', 'unknown'))

print('Implementation duration:',
      metadata.get(
          'implementation_duration_seconds',
          'unknown'
      ))

print('')

files_written = metadata.get(
    'files_written',
    []
)

print('Files written:')

if files_written:
    for filename in files_written:
        print('  -', filename)
else:
    print('  (none)')

print('')
"

END_TIME=$(date +%s)

TOTAL_SECONDS=$((END_TIME - START_TIME))

echo ""
echo "============================================================"
echo " TEST TIMING"
echo "============================================================"
echo "Total wall-clock time: ${TOTAL_SECONDS}s"
echo "============================================================"
echo ""

# ------------------------------------------------------------
# Show incremental plan
# ------------------------------------------------------------

echo "============================================================"
echo " INCREMENTAL PLAN"
echo "============================================================"

if [ -f "$TEST_REPO/.ox2/implementation_plan.json" ]; then
    cat "$TEST_REPO/.ox2/implementation_plan.json"
else
    echo "ERROR: implementation_plan.json was not generated."
fi

echo ""
echo "============================================================"
echo ""

# ------------------------------------------------------------
# Show incremental result
# ------------------------------------------------------------

echo "============================================================"
echo " INCREMENTAL RESULT"
echo "============================================================"

if [ -f "$TEST_REPO/.ox2/incremental_generation_result.json" ]; then
    cat "$TEST_REPO/.ox2/incremental_generation_result.json"
else
    echo "ERROR: incremental_generation_result.json was not generated."
fi

echo ""
echo "============================================================"
echo ""

# ------------------------------------------------------------
# Repository contents
# ------------------------------------------------------------

echo "============================================================"
echo " GENERATED REPOSITORY FILES"
echo "============================================================"

find "$TEST_REPO" \
    -type f \
    ! -path "*/.git/*" \
    ! -path "*/.ox2/*" \
    -print \
    | sort

echo ""
echo "============================================================"
echo ""

# ------------------------------------------------------------
# Java source preview
# ------------------------------------------------------------

echo "============================================================"
echo " JAVA SOURCE FILES"
echo "============================================================"

JAVA_FILES=$(find "$TEST_REPO" \
    -type f \
    -name "*.java" \
    ! -path "*/.git/*" \
    ! -path "*/.ox2/*" \
    | sort)

if [ -n "$JAVA_FILES" ]; then

    while IFS= read -r file; do

        echo ""
        echo "------------------------------------------------------------"
        echo "FILE: $file"
        echo "------------------------------------------------------------"

        cat "$file"

    done <<< "$JAVA_FILES"

else

    echo "NO JAVA FILES GENERATED."

fi

echo ""
echo "============================================================"
echo ""

# ------------------------------------------------------------
# Java compilation test
# ------------------------------------------------------------

echo "============================================================"
echo " JAVA COMPILATION TEST"
echo "============================================================"

if command -v javac >/dev/null 2>&1; then

    JAVA_FILES=$(find "$TEST_REPO" \
        -type f \
        -name "*.java" \
        ! -path "*/.git/*" \
        ! -path "*/.ox2/*" \
        | sort)

    if [ -n "$JAVA_FILES" ]; then

        BUILD_DIR="$TEST_REPO/.ox2/java-test-build"

        rm -rf "$BUILD_DIR"
        mkdir -p "$BUILD_DIR"

        if javac \
            -d "$BUILD_DIR" \
            $JAVA_FILES
        then
            echo ""
            echo "JAVA COMPILATION: PASS"
        else
            echo ""
            echo "JAVA COMPILATION: FAIL"
            exit 1
        fi

    else

        echo "SKIPPED: no Java files generated."

    fi

else

    echo "SKIPPED: javac is not installed."

fi

echo ""
echo "============================================================"
echo " TEST COMPLETE"
echo "============================================================"