"""Planning and language detection for incremental generation."""

import re
from typing import List, Tuple, Dict, Any

from ..constants import PREFERRED_FILES, IGNORED_PATH_PATTERNS
from .models import CodeChunk


class IncrementalPlanner:
    """Creates implementation plans from requirements."""

    def __init__(
        self,
        target_chunk_kb: float = 1.0,
        plans: Dict[str, List[str]] = None,
    ):
        self.target_chunk_kb = target_chunk_kb

        # Default plans if none provided
        if plans is None:
            plans = {
                "python": [
                    "Create the main calculator file src/calculator.py with add, subtract, multiply, divide functions and error handling.",
                    "Create the CLI entry point src/main.py that parses arguments and calls the calculator functions.",
                    "Create unit tests tests/test_calculator.py with test cases for all operations.",
                ],
                "java": [
                    "Create the main Swing UI class src/CalculatorApp.java with JFrame, JTextField display, and button layout.",
                    "Create the calculator logic class src/CalculatorLogic.java with add, subtract, multiply, divide operations.",
                ],
                "javascript": [
                    "Create the main application file src/index.js with core logic.",
                    "Create the CLI entry point src/cli.js that parses arguments.",
                    "Create unit tests tests/test.js with test cases for all operations.",
                ],
                "typescript": [
                    "Create the main application file src/index.ts with core logic.",
                    "Create the CLI entry point src/cli.ts that parses arguments.",
                    "Create unit tests tests/test.ts with test cases for all operations.",
                ],
                "csharp": [
                    "Create the main application class src/Program.cs with core logic.",
                    "Create the CLI entry point with argument parsing.",
                    "Create unit tests tests/ with test cases.",
                ],
                "go": [
                    "Create the main application file src/main.go with core logic.",
                    "Create the CLI entry point with argument parsing.",
                    "Create unit tests src/main_test.go with test cases.",
                ],
                "rust": [
                    "Create the main application file src/main.rs with core logic.",
                    "Create the CLI entry point with argument parsing.",
                    "Create unit tests tests/ with test cases.",
                ],
                "default": [
                    "Create the main application file with core logic.",
                    "Create the CLI entry point with argument parsing.",
                    "Create unit tests with test cases.",
                ],
            }

        self.plans = plans

    def create_plan(
        self,
        requirements: str,
        repo_analysis: str = "",
        dependency_analysis: str = "",
    ) -> Tuple[str, str, List[CodeChunk]]:
        """Create a generation plan."""
        language, framework = self.detect_language_and_framework(requirements)
        chunks = self.build_plan(requirements, language, framework)
        return language, framework, chunks

    def build_plan(
        self,
        requirements: str,
        language: str,
        framework: str,
    ) -> List[CodeChunk]:
        """Build plan from requirements and language."""

        # Extract explicit file paths from requirements
        explicit_files = self._extract_file_paths(requirements)

        if explicit_files:
            chunks = []
            for index, filepath in enumerate(explicit_files, start=1):
                chunks.append(
                    CodeChunk(
                        chunk_id=f"file-{index}",
                        file_path=filepath,
                        description=f"Implement the required functionality for {filepath}.",
                        order=index,
                        target_kb=self.target_chunk_kb,
                    )
                )
            return chunks

        # Use language-specific plan
        plan = self.plans.get(language, self.plans.get("default", []))

        return [
            CodeChunk(
                chunk_id=f"{language}-{index}",
                file_path="src",
                description=description,
                order=index,
                target_kb=self.target_chunk_kb,
            )
            for index, description in enumerate(plan, start=1)
        ]

    @staticmethod
    def _extract_file_paths(requirements: str) -> List[str]:
        pattern = (
            r"(?:^|[\s`(])"
            r"((?:src/|app/|lib/|tests?/|config/|docs/)?"
            r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*\."
            r"(?:py|js|jsx|ts|tsx|java|kt|go|rs|"
            r"cs|cpp|c|h|json|yaml|yml|toml|xml|"
            r"md|txt|sql|html|css|scss|properties))"
            r"(?:[\s)`.,]|$)"
        )
        matches = re.findall(pattern, requirements, re.MULTILINE)
        result = []
        for filepath in matches:
            filepath = filepath.strip("`'\".,);(")
            if filepath not in result:
                result.append(filepath)
        return result[:50]

    @staticmethod
    def detect_language_and_framework(requirements: str) -> Tuple[str, str]:
        text = requirements.lower()

        if "typescript" in text:
            language = "typescript"
        elif "javascript" in text:
            language = "javascript"
        elif "python" in text:
            language = "python"
        elif "java" in text:
            language = "java"
        elif "c#" in text or ".net" in text:
            language = "csharp"
        elif "rust" in text:
            language = "rust"
        elif "go" in text:
            language = "go"
        else:
            language = "default"

        framework = "auto-detect"
        frameworks = [
            ("fastapi", "FastAPI"),
            ("django", "Django"),
            ("flask", "Flask"),
            ("spring boot", "Spring Boot"),
            ("spring", "Spring"),
            ("react", "React"),
            ("next.js", "Next.js"),
            ("nextjs", "Next.js"),
            ("angular", "Angular"),
            ("vue", "Vue"),
            ("express", "Express"),
            ("nestjs", "NestJS"),
            ("asp.net", "ASP.NET"),
            ("swing", "Swing"),
            ("javafx", "JavaFX"),
        ]

        for pattern, value in frameworks:
            if pattern in text:
                framework = value
                break

        return (language, framework)
