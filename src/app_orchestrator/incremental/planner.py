"""Deterministic, domain-neutral planning for incremental generation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Tuple

from .models import CodeChunk


class IncrementalPlanner:
    """Create practical file-level implementation chunks without LLM calls."""

    def __init__(
            self,
            target_chunk_kb: float = 1.0,
            plans: Dict[str, List[str]] | None = None,
            repo_path: Path | None = None,
    ):
        self.target_chunk_kb = target_chunk_kb
        self.repo_path = Path(repo_path).resolve() if repo_path else None

        self.plans = plans or {
            "python": [
                "Implement the core application logic.",
                "Implement the application entry point.",
            ],
            "javascript": [
                "Implement the core application logic.",
                "Implement the application entry point.",
            ],
            "typescript": [
                "Implement the core application logic.",
                "Implement the application entry point.",
            ],
            "java": [
                "Implement the core application logic.",
                "Implement the application entry point.",
            ],
            "csharp": [
                "Implement the core application logic.",
                "Implement the application entry point.",
            ],
            "go": [
                "Implement the core application logic.",
                "Implement the application entry point.",
            ],
            "rust": [
                "Implement the core application logic.",
                "Implement the application entry point.",
            ],
            "default": [
                "Implement the core application logic.",
                "Implement the application entry point.",
            ],
        }

    def create_plan(
            self,
            requirements: str,
            repo_analysis: str = "",
            dependency_analysis: str = "",
    ) -> Tuple[str, str, List[CodeChunk]]:
        language, framework = self.detect_language_and_framework(
            requirements,
            repo_analysis,
        )

        return (
            language,
            framework,
            self.build_plan(
                requirements,
                language,
                framework,
            ),
        )

    def build_plan(
            self,
            requirements: str,
            language: str,
            framework: str,
    ) -> List[CodeChunk]:
        explicit_files = self._extract_file_paths(requirements)

        if explicit_files:
            return [
                CodeChunk(
                    f"file-{i}",
                    path,
                    f"Implement the required functionality for {path}.",
                    i,
                    self.target_chunk_kb,
                )
                for i, path in enumerate(explicit_files, 1)
            ]

        extension = {
            "python": "py",
            "javascript": "js",
            "typescript": "ts",
            "java": "java",
            "csharp": "cs",
            "go": "go",
            "rust": "rs",
        }.get(language, "txt")

        project_name = self._detect_project_name(requirements)

        source_root = self._detect_source_root(
            project_name=project_name,
            language=language,
        )

        descriptions = self.plans.get(
            language,
            self.plans["default"],
        )

        chunks: List[CodeChunk] = []

        for index, description in enumerate(descriptions, 1):
            filename = self._meaningful_filename(
                project_name,
                description,
                language,
                extension,
                index,
            )

            relative_path = f"{source_root}/{filename}"

            chunks.append(
                CodeChunk(
                    f"{language}-{index}",
                    relative_path,
                    description,
                    index,
                    self.target_chunk_kb,
                )
            )

        return chunks

    def _detect_source_root(
            self,
            project_name: str,
            language: str,
    ) -> str:
        """
        Determine where generated source files should live.

        Existing repository structure always wins over project-name inference.

        Priority:

        1. Existing root-level src/
        2. Existing project/src/
        3. Existing nested */src/ containing source files
        4. Existing root-level source files
        5. New project/src/

        This prevents repeated generation into directories such as:

            calculator/
            simple/
            new/
            java/

        when the repository already has a usable src/ directory.
        """

        if self.repo_path is None or not self.repo_path.exists():
            return f"{self._safe_name(project_name)}/src"

        # --------------------------------------------------------------
        # 1. Root-level src/
        # --------------------------------------------------------------

        root_src = self.repo_path / "src"

        if self._usable_source_directory(root_src, language):
            return "src"

        # --------------------------------------------------------------
        # 2. Explicit project-name/src/
        # --------------------------------------------------------------

        project_dir = self._safe_name(project_name)

        project_src = self.repo_path / project_dir / "src"

        if self._usable_source_directory(project_src, language):
            return f"{project_dir}/src"

        # --------------------------------------------------------------
        # 3. Search existing nested src/ directories
        # --------------------------------------------------------------

        candidates: List[tuple[int, str]] = []

        try:
            for src_dir in self.repo_path.rglob("src"):
                if not src_dir.is_dir():
                    continue

                # Never consider .venv, .git, .ox2, caches, etc.
                if self._should_ignore(src_dir):
                    continue

                relative = src_dir.relative_to(self.repo_path).as_posix()

                if relative == "src":
                    continue

                if self._usable_source_directory(src_dir, language):
                    score = self._source_directory_score(
                        src_dir,
                        language,
                    )
                    candidates.append((score, relative))

        except OSError:
            pass

        if candidates:
            candidates.sort(
                key=lambda item: (
                    -item[0],
                    item[1],
                )
            )

            return candidates[0][1]

        # --------------------------------------------------------------
        # 4. Existing root-level source files
        # --------------------------------------------------------------

        if self._has_root_source_files(language):
            return "src"

        # --------------------------------------------------------------
        # 5. No usable source root exists.
        #
        # Only now do we create a project-specific source directory.
        # --------------------------------------------------------------

        return f"{project_dir}/src"

    def _usable_source_directory(
            self,
            directory: Path,
            language: str,
    ) -> bool:
        if not directory.exists() or not directory.is_dir():
            return False

        try:
            for path in directory.rglob("*"):
                if not path.is_file():
                    continue

                if self._should_ignore(path):
                    continue

                if self._is_source_file(path, language):
                    return True

        except OSError:
            return False

        return False

    def _source_directory_score(
            self,
            directory: Path,
            language: str,
    ) -> int:
        score = 0

        relative = directory.relative_to(self.repo_path).as_posix()

        # Prefer shallow directories.
        depth = len(Path(relative).parts)
        score += max(0, 20 - depth * 5)

        # Strong preference for Java/other language files.
        try:
            files = [
                path
                for path in directory.rglob("*")
                if path.is_file()
                   and not self._should_ignore(path)
            ]
        except OSError:
            files = []

        for path in files:
            if self._is_source_file(path, language):
                score += 20

        # Existing application entry points are a very strong signal.
        names = {path.name.lower() for path in files}

        if "main.java" in names:
            score += 30

        if "application.java" in names:
            score += 25

        if "main.py" in names:
            score += 30

        return score

    def _has_root_source_files(self, language: str) -> bool:
        if self.repo_path is None:
            return False

        try:
            for path in self.repo_path.iterdir():
                if not path.is_file():
                    continue

                if self._should_ignore(path):
                    continue

                if self._is_source_file(path, language):
                    return True

        except OSError:
            pass

        return False

    @staticmethod
    def _is_source_file(
            path: Path,
            language: str,
    ) -> bool:
        extensions = {
            "python": {".py"},
            "javascript": {".js", ".jsx"},
            "typescript": {".ts", ".tsx"},
            "java": {".java"},
            "csharp": {".cs"},
            "go": {".go"},
            "rust": {".rs"},
            "default": {
                ".py",
                ".js",
                ".jsx",
                ".ts",
                ".tsx",
                ".java",
                ".kt",
                ".cs",
                ".go",
                ".rs",
                ".cpp",
                ".c",
                ".h",
            },
        }

        return path.suffix.lower() in extensions.get(
            language,
            extensions["default"],
        )

    @staticmethod
    def _should_ignore(path: Path) -> bool:
        ignored = {
            ".git",
            ".ox2",
            ".venv",
            "venv",
            "__pycache__",
            ".pytest_cache",
            "node_modules",
            "build",
            "dist",
            "target",
            ".idea",
        }

        return any(part in ignored for part in path.parts)

    @staticmethod
    def _detect_project_name(requirements: str) -> str:
        patterns = (
            r"\b(?:project|application|app)\s+name\s*[:=]?\s*[\"']?([A-Za-z][A-Za-z0-9_-]*)",
            r"\b(?:build|create|develop|implement)\s+(?:a|an|the)?\s*([A-Za-z][A-Za-z0-9_-]*)",
        )

        for pattern in patterns:
            match = re.search(
                pattern,
                requirements,
                re.IGNORECASE,
            )

            if match:
                value = match.group(1).strip("_- ")

                if value and value.lower() not in {
                    "an",
                    "a",
                    "the",
                    "application",
                    "app",
                }:
                    return value

        return "application"

    @staticmethod
    def _safe_name(value: str) -> str:
        value = re.sub(
            r"[^A-Za-z0-9_-]+",
            "-",
            value.strip(),
        ).strip("-")

        return value.lower() or "application"

    @staticmethod
    def _meaningful_filename(
            project_name: str,
            description: str,
            language: str,
            extension: str,
            index: int,
    ) -> str:
        base = re.sub(
            r"[^A-Za-z0-9]+",
            " ",
            project_name,
        ).strip() or "Application"

        pascal = "".join(
            part.capitalize()
            for part in base.split()
        )

        text = description.lower()

        if "test" in text:
            stem = f"{pascal}Test"

        elif (
                "entry point" in text
                or "main application" in text
        ):
            stem = f"{pascal}Application"

        elif (
                "business" in text
                or "logic" in text
                or "core" in text
        ):
            stem = f"{pascal}Service"

        else:
            stem = f"{pascal}Module{index}"

        if language == "python":
            stem = re.sub(
                r"(?<!^)([A-Z])",
                r"_\1",
                stem,
            ).lower()

        return f"{stem}.{extension}"

    @staticmethod
    def detect_language_and_framework(
            requirements: str,
            repo_analysis: str = "",
    ) -> Tuple[str, str]:
        text = f"{requirements}\n{repo_analysis}".lower()

        language = "default"

        for marker, value in (
                ("typescript", "typescript"),
                ("javascript", "javascript"),
                ("python", "python"),
                ("java", "java"),
                ("c#", "csharp"),
                (".net", "csharp"),
                ("rust", "rust"),
                (" go ", "go"),
        ):
            if marker in text:
                language = value
                break

        framework = "auto-detect"

        frameworks = (
            "fastapi",
            "django",
            "flask",
            "spring boot",
            "spring",
            "react",
            "next.js",
            "angular",
            "vue",
            "express",
            "nestjs",
            "asp.net",
            "javafx",
        )

        for value in frameworks:
            if value in text:
                framework = (
                    value.title()
                    if value != "next.js"
                    else "Next.js"
                )
                break

        return language, framework

    @staticmethod
    def _extract_file_paths(
            requirements: str,
    ) -> List[str]:
        pattern = (
            r"(?:^|[\s`(])"
            r"((?:[A-Za-z0-9_.-]+/)*"
            r"[A-Za-z0-9_.-]+\."
            r"(?:py|js|jsx|ts|tsx|java|kt|go|rs|cs|cpp|c|h|json|yaml|yml|toml|xml|md|txt|sql|html|css|scss|properties))"
            r"(?:[\s`).,]|$)"
        )

        result: List[str] = []

        for path in re.findall(
                pattern,
                requirements,
                re.MULTILINE,
        ):
            path = path.strip(
                "`'\".,);("
            )

            if (
                    ".." not in path.split("/")
                    and path not in result
            ):
                result.append(path)

        return result[:50]