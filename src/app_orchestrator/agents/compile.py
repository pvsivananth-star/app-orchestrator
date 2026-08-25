"""Local compilation and test validation agent."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

from ..agent import Agent

logger = logging.getLogger(__name__)


class CompileAgent(Agent):
    """Compile and test the generated application locally."""

    def _get_provider_chain(self) -> list[str]:
        return ["FAIL"]

    def _build_prompt(self, context: dict[str, Any]) -> str:
        return ""

    def _parse_response(
            self,
            response: str,
            context: dict[str, Any],
    ) -> dict[str, Any]:
        return {"status": "compiled"}

    def run(self) -> dict[str, Any]:
        """Run syntax validation followed by the project's test suite."""

        repo_path = self.workspace.repo_path
        log: list[str] = []
        success = True

        python_files = [
            path
            for path in repo_path.rglob("*.py")
            if ".venv" not in path.parts
               and ".git" not in path.parts
               and ".ox2" not in path.parts
               and "__pycache__" not in path.parts
        ]

        log.append(f"Found {len(python_files)} Python file(s).")

        for path in python_files:
            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "py_compile",
                    str(path),
                ],
                capture_output=True,
                text=True,
                cwd=repo_path,
            )

            if result.returncode == 0:
                log.append(f"PASS syntax: {path.relative_to(repo_path)}")
            else:
                success = False
                log.append(f"FAIL syntax: {path.relative_to(repo_path)}")
                if result.stderr:
                    log.append(result.stderr.strip())

        tests_dir = repo_path / "tests"
        has_tests = tests_dir.exists() and any(tests_dir.rglob("test_*.py"))

        test_result: dict[str, Any] = {
            "status": "skipped",
            "returncode": None,
        }

        if has_tests and success:
            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "pytest",
                    "-q",
                ],
                capture_output=True,
                text=True,
                cwd=repo_path,
            )

            test_result = {
                "status": "pass" if result.returncode == 0 else "fail",
                "returncode": result.returncode,
            }

            if result.stdout:
                log.append(result.stdout.strip())

            if result.stderr:
                log.append(result.stderr.strip())

            if result.returncode != 0:
                success = False

        elif has_tests:
            test_result["status"] = "blocked_by_syntax_failure"
            log.append("Tests skipped because syntax validation failed.")
        else:
            log.append("No pytest tests found; test phase skipped.")

        status = "pass" if success else "fail"
        log.append(f"Overall status: {status.upper()}")

        compile_log = "\n".join(log)
        self._write_artifact("compile.log", compile_log)

        return {
            "status": status,
            "syntax_status": "pass" if success or test_result["status"] != "fail" else "fail",
            "test": test_result,
            "log": compile_log,
        }