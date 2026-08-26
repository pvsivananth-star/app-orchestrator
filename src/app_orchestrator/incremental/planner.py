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

        # Generic plans – not tied to any specific project
        if plans is None:
            plans = {
                "java": [
                    "Create the main application class with the GUI layout and entry point.",
                    "Create the logic class for business operations.",
                ],
                "python": [
                    "Create the main application logic.",
                    "Create the CLI entry point.",
                    "Create unit tests.",
                ],
                "javascript": [
                    "Create core application logic.",
                    "Create DOM/UI components.",
                    "Create event handlers.",
                ],
                "typescript": [
                    "Create core application logic.",
                    "Create DOM/UI components.",
                    "Create event handlers.",
                ],
                "default": [
                    "Create core application logic.",
                    "Create user interface.",
                    "Create tests.",
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

        # Try to extract explicit file paths from requirements
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

        # Otherwise, use language-specific generic plan
        plan = self.plans.get(language, self.plans.get("default", []))

        # Determine project name and path prefix
        project_name = self._detect_project_name(requirements)
        path_prefix = self._detect_path_prefix(requirements)

        chunks = []
        for index, description in enumerate(plan, start=1):
            # Generate a sensible filename based on description and language
            filename = self._generate_filename(description, language, project_name, index)
            # Prepend path prefix if detected
            if path_prefix:
                filename = f"{path_prefix}/{filename}"
            chunks.append(
                CodeChunk(
                    chunk_id=f"{language}-{index}",
                    file_path=filename,
                    description=description,
                    order=index,
                    target_kb=self.target_chunk_kb,
                )
            )
        return chunks

    @staticmethod
    def _detect_project_name(requirements: str) -> str:
        """Extract project name from requirements."""
        patterns = [
            r'project\s+name\s+["\']?([A-Za-z][A-Za-z0-9_\s\-]*)',
            r'application\s+name\s+["\']?([A-Za-z][A-Za-z0-9_\s\-]*)',
            r'^#\s*([A-Za-z][A-Za-z0-9_\s\-]*)',  # Markdown title
            r'Build\s+([A-Za-z][A-Za-z0-9_\s\-]*)',  # "Build a calculator" -> calculator
            r'Create\s+([A-Za-z][A-Za-z0-9_\s\-]*)',  # "Create a web API" -> web
        ]
        for pattern in patterns:
            match = re.search(pattern, requirements, re.IGNORECASE)
            if match:
                name = match.group(1).strip().replace(' ', '').replace('-', '')
                # Ensure it starts with uppercase for Java/C# etc.
                if name and name[0].islower():
                    name = name[0].upper() + name[1:]
                return name
        return "App"

    @staticmethod
    def _detect_path_prefix(requirements: str) -> str:
        """Detect if the project uses a standard source folder structure."""
        if re.search(r'\bsrc\b', requirements, re.IGNORECASE):
            return "src"
        elif re.search(r'\blib\b', requirements, re.IGNORECASE):
            return "lib"
        elif re.search(r'\bapp\b', requirements, re.IGNORECASE):
            return "app"
        return ""  # root

    @staticmethod
    def _generate_filename(description: str, language: str, project_name: str, index: int) -> str:
        """Generate a suitable filename from the chunk description and language."""
        # For Java, we'll base filename on project name for main class
        if language == "java":
            if index == 1:
                return f"{project_name}.java"
            else:
                return f"{project_name}Logic.java"
        # For Python, use lower-case underscores
        elif language == "python":
            if index == 1:
                return "main.py"
            elif "test" in description.lower():
                return "test_main.py"
            else:
                return f"module_{index}.py"
        # For JavaScript/TypeScript
        elif language in ("javascript", "typescript"):
            ext = "js" if language == "javascript" else "ts"
            if index == 1:
                return f"main.{ext}"
            elif "test" in description.lower():
                return f"main.test.{ext}"
            else:
                return f"module_{index}.{ext}"
        else:
            # Generic: use the language name and index
            return f"{language}_{index}.txt"

    @staticmethod
    def _extract_file_paths(requirements: str) -> List[str]:
        """Extract explicit file paths from requirements."""
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