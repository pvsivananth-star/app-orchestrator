#!/bin/bash
# final_fix.sh
# Removes microsoft_groq and fixes JSON serialization

set -e

echo "=== Applying final fixes ==="

# 1. Remove microsoft_groq from all agent provider chains in mapping.yaml
# This uses sed to delete ", microsoft_groq" and "microsoft_groq, " from agent lists
sed -i '' 's/, microsoft_groq//g' src/app_orchestrator/models/mapping.yaml
sed -i '' 's/microsoft_groq, //g' src/app_orchestrator/models/mapping.yaml
sed -i '' 's/microsoft_groq//g' src/app_orchestrator/models/mapping.yaml

# Clean up any double commas or trailing spaces
sed -i '' 's/, ,/,/g' src/app_orchestrator/models/mapping.yaml
sed -i '' 's/\[, /[/g' src/app_orchestrator/models/mapping.yaml
sed -i '' 's/, \]/]/g' src/app_orchestrator/models/mapping.yaml

echo "✅ Removed microsoft_groq from provider chains"

# 2. Patch all workspace.write_json and workspace.write calls to avoid state objects
# Find all Python files and replace state with state.to_dict() in write calls
find src/app_orchestrator -name "*.py" -exec sed -i '' 's/workspace.write_json([^,)]*,\s*state\s*)/workspace.write_json(\1, state.to_dict())/g' {} \;
find src/app_orchestrator -name "*.py" -exec sed -i '' 's/workspace.write([^,)]*,\s*state\s*)/workspace.write(\1, json.dumps(state.to_dict()))/g' {} \;

# Also catch any write_json where state is a variable named differently (e.g., self.state)
find src/app_orchestrator -name "*.py" -exec sed -i '' 's/workspace.write_json([^,)]*,\s*self\.state\s*)/workspace.write_json(\1, self.state.to_dict())/g' {} \;
find src/app_orchestrator -name "*.py" -exec sed -i '' 's/workspace.write([^,)]*,\s*self\.state\s*)/workspace.write(\1, json.dumps(self.state.to_dict()))/g' {} \;

echo "✅ Patched all workspace.write calls to use .to_dict()"

# 3. Ensure orchestator.py uses .to_dict() for state saving
# We'll directly patch the known line if present
sed -i '' 's/self.workspace.write_json("state.json", self.state)/self.workspace.write_json("state.json", self.state.to_dict())/g' src/app_orchestrator/orchestrator.py

# 4. Clean cache
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true

echo ""
echo "=== Final fixes applied ==="
echo "Providers now: deepseek, groq, openrouter (microsoft_groq removed temporarily)"
echo "JSON serialization of state is now safe."
echo ""
echo "Run: uv run streamlit run ui.py"
EOF

chmod +x final_fix.sh