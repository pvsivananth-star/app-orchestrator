"""Deterministic, domain-neutral planning for incremental generation."""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

from .models import CodeChunk


class IncrementalPlanner:
    """Create practical file-level implementation chunks without LLM calls."""

    def __init__(self, target_chunk_kb: float = 1.0, plans: Dict[str, List[str]] | None = None):
        self.target_chunk_kb = target_chunk_kb
        self.plans = plans or {
            "python": ["Implement the core application logic.", "Implement the application entry point."],
            "javascript": ["Implement the core application logic.", "Implement the application entry point."],
            "typescript": ["Implement the core application logic.", "Implement the application entry point."],
            "java": ["Implement the core application logic.", "Implement the application entry point."],
            "csharp": ["Implement the core application logic.", "Implement the application entry point."],
            "go": ["Implement the core application logic.", "Implement the application entry point."],
            "rust": ["Implement the core application logic.", "Implement the application entry point."],
            "default": ["Implement the core application logic.", "Implement the application entry point."],
        }

    def create_plan(self, requirements: str, repo_analysis: str = "", dependency_analysis: str = "") -> Tuple[str, str, List[CodeChunk]]:
        language, framework = self.detect_language_and_framework(requirements, repo_analysis)
        return language, framework, self.build_plan(requirements, language, framework)

    def build_plan(self, requirements: str, language: str, framework: str) -> List[CodeChunk]:
        explicit_files = self._extract_file_paths(requirements)
        if explicit_files:
            return [CodeChunk(f"file-{i}", path, f"Implement the required functionality for {path}.", i, self.target_chunk_kb) for i, path in enumerate(explicit_files, 1)]

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
        project_dir = self._safe_name(project_name)
        descriptions = self.plans.get(language, self.plans["default"])
        chunks: List[CodeChunk] = []

        for index, description in enumerate(descriptions, 1):
            filename = self._meaningful_filename(
                project_name, description, language, extension, index
            )
            relative_path = f"{project_dir}/src/{filename}"
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


    @staticmethod
    def _detect_project_name(requirements: str) -> str:
        patterns = (
            r"\b(?:project|application|app)\s+name\s*[:=]?\s*[\"']?([A-Za-z][A-Za-z0-9_-]*)",
            r"\b(?:build|create|develop|implement)\s+(?:a|an|the)?\s*([A-Za-z][A-Za-z0-9_-]*)",
        )
        for pattern in patterns:
            match = re.search(pattern, requirements, re.IGNORECASE)
            if match:
                value = match.group(1).strip("_- ")
                if value and value.lower() not in {"an", "a", "the", "application", "app"}:
                    return value
        return "application"

    @staticmethod
    def _safe_name(value: str) -> str:
        value = re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip()).strip("-")
        return value.lower() or "application"

    @staticmethod
    def _meaningful_filename(project_name: str, description: str, language: str, extension: str, index: int) -> str:
        base = re.sub(r"[^A-Za-z0-9]+", " ", project_name).strip() or "Application"
        pascal = "".join(part.capitalize() for part in base.split())
        text = description.lower()

        if "test" in text:
            stem = f"{pascal}Test"
        elif "entry point" in text or "main application" in text:
            stem = f"{pascal}Application"
        elif "business" in text or "logic" in text or "core" in text:
            stem = f"{pascal}Service"
        else:
            stem = f"{pascal}Module{index}"

        if language == "python":
            stem = re.sub(r"(?<!^)([A-Z])", r"_\1", stem).lower()
        return f"{stem}.{extension}"

    @staticmethod
    def detect_language_and_framework(requirements: str, repo_analysis: str = "") -> Tuple[str, str]:
        text = f"{requirements}\n{repo_analysis}".lower()
        language = "default"
        for marker, value in (("typescript", "typescript"), ("javascript", "javascript"), ("python", "python"), ("java", "java"), ("c#", "csharp"), (".net", "csharp"), ("rust", "rust"), (" go ", "go")):
            if marker in text:
                language = value
                break
        framework = "auto-detect"
        frameworks = ("fastapi", "django", "flask", "spring boot", "spring", "react", "next.js", "angular", "vue", "express", "nestjs", "asp.net", "javafx")
        for value in frameworks:
            if value in text:
                framework = value.title() if value != "next.js" else "Next.js"
                break
        return language, framework

    @staticmethod
    def _extract_file_paths(requirements: str) -> List[str]:
        pattern = r"(?:^|[\s`(])((?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:py|js|jsx|ts|tsx|java|kt|go|rs|cs|cpp|c|h|json|yaml|yml|toml|xml|md|txt|sql|html|css|scss|properties))(?:[\s`).,]|$)"
        result: List[str] = []
        for path in re.findall(pattern, requirements, re.MULTILINE):
            path = path.strip("`'\".,);(")
            if ".." not in path.split("/") and path not in result:
                result.append(path)
        return result[:50]
