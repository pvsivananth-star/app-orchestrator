"""Compile Agent – local compilation tool."""

from typing import Dict, Any, List
import logging
import subprocess
import tempfile
from pathlib import Path
from ..agent import Agent

logger = logging.getLogger(__name__)

class CompileAgent(Agent):
    def _get_provider_chain(self) -> List[str]:
        return ["FAIL"]  # No providers needed, just local execution

    def _build_prompt(self, context: Dict[str, Any]) -> str:
        return ""  # Not used

    def _parse_response(self, response: str, context: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "compiled"}  # Not used

    def run(self) -> Dict[str, Any]:
        """Run the compile check locally."""
        logger.info("Running CompileAgent (local)")

        repo_path = self.workspace.repo_path
        log_content = []
        success = True

        # Check for Python files
        py_files = list(repo_path.glob("*.py"))
        if py_files:
            log_content.append(f"Found {len(py_files)} Python file(s):")
            for f in py_files:
                log_content.append(f"  - {f.name}")

            # Check syntax for each Python file
            for f in py_files:
                result = subprocess.run(
                    ["python", "-m", "py_compile", str(f)],
                    capture_output=True,
                    text=True,
                    cwd=repo_path
                )
                if result.returncode == 0:
                    log_content.append(f"✅ {f.name}: syntax OK")
                else:
                    log_content.append(f"❌ {f.name}: syntax error")
                    log_content.append(result.stderr)
                    success = False

        # Check for Java files
        java_files = list(repo_path.glob("*.java"))
        if java_files:
            log_content.append(f"Found {len(java_files)} Java file(s):")
            for f in java_files:
                log_content.append(f"  - {f.name}")

            # Java compilation
            for f in java_files:
                result = subprocess.run(
                    ["javac", str(f)],
                    capture_output=True,
                    text=True,
                    cwd=repo_path
                )
                if result.returncode == 0:
                    log_content.append(f"✅ {f.name}: compiled OK")
                else:
                    log_content.append(f"❌ {f.name}: compilation failed")
                    log_content.append(result.stderr)
                    success = False

        # Check for JavaScript/TypeScript files
        js_files = list(repo_path.glob("*.js"))
        ts_files = list(repo_path.glob("*.ts"))
        if js_files or ts_files:
            log_content.append(f"Found {len(js_files)} JS file(s) and {len(ts_files)} TS file(s)")
            # Check if Node.js is available
            try:
                subprocess.run(["node", "--version"], capture_output=True, check=True)
                log_content.append("✅ Node.js available")
            except:
                log_content.append("⚠️ Node.js not found (skipping JS checks)")

        # Check for requirements.txt and suggest installing
        req_file = repo_path / "requirements.txt"
        if req_file.exists():
            log_content.append(f"Found requirements.txt")

        log_content.append("")
        log_content.append(f"Overall status: {'✅ PASS' if success else '❌ FAIL'}")

        # Write log
        compile_log = "\n".join(log_content)
        self._write_artifact("compile.log", compile_log)

        return {
            "status": "pass" if success else "fail",
            "log": compile_log
        }
