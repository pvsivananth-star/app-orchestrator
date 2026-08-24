cat > src/app_orchestrator/agents/implementation.py << 'EOF'
"""Implementation Agent – generates code based on requirements (language-agnostic)."""

from typing import Dict, Any, List
import logging
import re
from pathlib import Path
from ..agent import Agent

logger = logging.getLogger(__name__)

class ImplementationAgent(Agent):
    def _get_provider_chain(self) -> List[str]:
        return self.provider_registry.get_agent_providers("implementation")

    def _build_prompt(self, context: Dict[str, Any]) -> str:
        requirements = self._read_artifact("requirements.md")
        if not requirements:
            requirements = self._read_artifact("clarified_requirements.md") or "No requirements found."

        repo_info = self._read_artifact("repo_analysis.md")
        if not repo_info:
            repo_info = "No repository analysis available."

        prompt = f"""You are the Implementation Agent for an AI-powered software development orchestrator.

Your role is to generate working, compilable code based on the requirements.

**IMPORTANT:** The language/framework is determined by the requirements.

REQUIREMENTS:
{requirements}

text

REPOSITORY CONTEXT:
{repo_info}

text

Based on this, you MUST:
1. Detect the appropriate language and framework from the requirements
2. Generate the complete code for the project
3. Follow best practices for the detected language/framework
4. Include proper error handling
5. Write clean, readable, well-commented code
6. Include the necessary project structure (package.json, requirements.txt, Cargo.toml, etc.)

OUTPUT FORMAT - **CRITICAL: Use this exact format for each file:**

## FILE: path/to/file.py
[file content]

text

Do NOT include any language tag inside the code block markers. Just use triple backticks.

Start with the main application file, then add supporting files.
"""
        return prompt

    def _parse_response(self, response: str, context: Dict[str, Any]) -> Dict[str, Any]:
        files_written = []

        # Pattern: ## FILE: path/to/file.ext followed by ``` then content then ```
        pattern = r'##\s*FILE:\s*([^\n]+?)\s*\n```\s*\n(.*?)```'
        matches = re.findall(pattern, response, re.DOTALL)

        if not matches:
            # Try with optional newline
            pattern2 = r'##\s*FILE:\s*([^\n]+?)\s*\n```(.*?)```'
            matches = re.findall(pattern2, response, re.DOTALL)

        if not matches:
            # Try without code block markers (just the file path and content)
            pattern3 = r'##\s*FILE:\s*([^\n]+?)\s*\n(.*?)(?=\n##\s*FILE:|$)'
            matches = re.findall(pattern3, response, re.DOTALL)

        if matches:
            for filepath, content in matches:
                filepath = filepath.strip()
                content = content.strip()

                # Remove any accidental language tags in the filepath
                # e.g., "app.py python" -> "app.py"
                if ' ' in filepath:
                    parts = filepath.split()
                    # If the first part looks like a file with extension, use it
                    if '.' in parts[0]:
                        filepath = parts[0]

                if filepath and content:
                    full_path = self.workspace.repo_path / filepath
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    full_path.write_text(content)
                    files_written.append(filepath)
                    logger.info(f"Wrote file: {filepath}")
        else:
            # Fallback: look for any code blocks
            fallback_pattern = r'```\s*\n(.*?)```'
            fallback_matches = re.findall(fallback_pattern, response, re.DOTALL)

            if fallback_matches:
                for i, content in enumerate(fallback_matches):
                    content = content.strip()
                    if not content:
                        continue
                    # Try to guess filename from first few lines
                    first_line = content.split('\n')[0] if content else ''
                    filename = f"file_{i+1}.txt"

                    # Guess based on content
                    if 'flask' in first_line.lower() or 'app = Flask' in content:
                        filename = "app.py"
                    elif 'express' in content.lower():
                        filename = "server.js"
                    elif 'react' in content.lower() or 'React' in content:
                        filename = "App.jsx"
                    elif 'requirements.txt' in content:
                        filename = "requirements.txt"
                    elif 'package.json' in content:
                        filename = "package.json"
                    elif 'class' in content and '(' in content and ':' in content:
                        # Could be Python class
                        if 'def ' in content:
                            filename = "app.py"

                    full_path = self.workspace.repo_path / filename
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    full_path.write_text(content)
                    files_written.append(filename)
                    logger.info(f"Wrote file (fallback): {filename}")

        # Write the full response as a log for debugging
        self._write_artifact("implementation_log.md", response)

        if not hasattr(self.state, "metadata"):
            self.state.metadata = {}
        self.state.metadata["files_written"] = files_written
        self.state.metadata["implementation_complete"] = True

        return {
            "files_written": files_written,
            "status": "implemented",
            "file_count": len(files_written)
        }
EOF

# Clean cache
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true

echo "✅ Implementation Agent fixed with clean file parsing"