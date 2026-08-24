#!/bin/bash
# test_code_gen.sh - Test Java calculator generation

echo "=========================================="
echo "Testing: Java Swing Calculator"
echo "=========================================="

# Clean previous artifacts and generated files
rm -rf ../test-ox2/.ox2 2>/dev/null
rm -f ../test-ox2/*.java ../test-ox2/*.class ../test-ox2/*.jar 2>/dev/null

# Run the orchestrator with Java GUI requirement
echo "Create a calculator GUI application in Java using Swing with basic operations: add, subtract, multiply, divide. Include a clean UI with buttons and a display field." | uv run python -c "
import sys
import os
sys.path.insert(0, 'src')
from app_orchestrator.orchestrator import Orchestrator
from pathlib import Path

print('Running orchestrator...')
orch = Orchestrator(Path('../test-ox2'))
result = orch.run('Create a calculator GUI application in Java using Swing with basic operations: add, subtract, multiply, divide. Include a clean UI with buttons and a display field.')

print('')
print('=' * 60)
print('RESULT:')
print('=' * 60)
status = result.get('status', 'unknown')
print('Status:', status)
print('Message:', result.get('message', ''))

state = result.get('state', {})
metadata = state.get('metadata', {})
files_written = metadata.get('files_written', [])
print('Files written:', files_written)

print('')
print('=' * 60)
print('FILES IN REPO:')
print('=' * 60)
for f in os.listdir('../test-ox2'):
    if not f.startswith('.') and f not in ['LICENSE', 'README.md', '.gitignore']:
        if f != '.ox2':
            print('  -', f)
"

# Show the generated Java file
echo ""
echo "=" * 60
echo "JAVA CODE PREVIEW:"
echo "=" * 60
find ../test-ox2 -name "*.java" -exec echo "File: {}" \; -exec head -80 {} \; 2>/dev/null || echo "No Java file found"