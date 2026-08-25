"""
Incremental code generation engine.

Generates a project in small logical implementation units rather than
asking an AI provider to generate the entire repository in one request.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .providers import ProviderRegistry
from .state import PipelineState
from .workspace import Workspace


logger = logging.getLogger(__name__)


# ======================================================================
# Data structures
# ======================================================================


@dataclass
class CodeChunk:
    """One logical implementation unit."""

    chunk_id: str
    file_path: str
    description: str
    order: int

    target_kb: float = 1.0

    dependencies: List[str] = field(
        default_factory=list
    )

    generated: bool = False
    verified: bool = False
    iterations: int = 0


@dataclass
class GenerationPlan:
    """Complete incremental implementation plan."""

    language: str
    framework: str

    chunks: List[CodeChunk] = field(
        default_factory=list
    )

    requirements_summary: str = ""

    created_at: float = field(
        default_factory=time.time
    )

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )


@dataclass
class GenerationResult:
    """Result of incremental generation."""

    status: str

    files_created: List[str] = field(
        default_factory=list
    )

    files_modified: List[str] = field(
        default_factory=list
    )

    chunks_completed: int = 0
    chunks_total: int = 0

    iterations: int = 0

    errors: List[str] = field(
        default_factory=list
    )

    duration_seconds: float = 0.0


# ======================================================================
# Incremental generator
# ======================================================================


class IncrementalCodeGenerator:
    """
    Stateful incremental implementation engine.

    Design:

        requirements
             |
             v
        implementation plan
             |
             v
        logical chunk
             |
             v
        small provider request
             |
             v
        apply files
             |
             v
        verify
             |
             v
        next chunk

    Every completed chunk changes the repository state. The next chunk
    therefore sees the implementation produced by previous chunks.
    """

    def __init__(
            self,
            workspace: Workspace,
            state: PipelineState,
            provider_registry: ProviderRegistry,
            provider_chain: Optional[List[str]] = None,
            config: Optional[Dict[str, Any]] = None,
    ):
        self.workspace = workspace
        self.state = state
        self.provider_registry = provider_registry

        self.config = config or {}

        self.provider_chain = (
                provider_chain or []
        )

        self.target_chunk_kb = self._get_float(
            "target_chunk_kb",
            1.0,
        )

        self.max_context_kb = self._get_float(
            "max_context_kb",
            6.0,
        )

        self.max_iterations = self._get_int(
            "max_iterations",
            30,
        )

        self.max_chunk_iterations = self._get_int(
            "max_chunk_iterations",
            3,
        )

        self.verify_each_chunk = self._get_bool(
            "verify_each_chunk",
            True,
        )

        self.preserve_existing_code = self._get_bool(
            "preserve_existing_code",
            True,
        )

        self.plan: Optional[GenerationPlan] = None

    # ==================================================================
    # Configuration
    # ==================================================================

    def _get_value(
            self,
            key: str,
            default: Any,
    ) -> Any:

        if key in self.config:
            return self.config[key]

        env_key = (
                "APP_ORCHESTRATOR_INCREMENTAL_"
                + key.upper()
        )

        return os.getenv(
            env_key,
            default,
        )

    def _get_int(
            self,
            key: str,
            default: int,
    ) -> int:

        try:
            return int(
                self._get_value(
                    key,
                    default,
                )
            )
        except (
                TypeError,
                ValueError,
        ):
            return default

    def _get_float(
            self,
            key: str,
            default: float,
    ) -> float:

        try:
            return float(
                self._get_value(
                    key,
                    default,
                )
            )
        except (
                TypeError,
                ValueError,
        ):
            return default

    def _get_bool(
            self,
            key: str,
            default: bool,
    ) -> bool:

        value = self._get_value(
            key,
            default,
        )

        if isinstance(value, bool):
            return value

        return str(value).lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    # ==================================================================
    # Main generation entry point
    # ==================================================================

    def generate(
            self,
            requirements: str,
            repo_analysis: str = "",
            dependency_analysis: str = "",
    ) -> GenerationResult:

        started = time.time()

        result = GenerationResult(
            status="started"
        )

        try:
            self._validate_requirements(
                requirements
            )

            logger.info(
                "Creating incremental implementation plan"
            )

            self.plan = self._create_plan(
                requirements=requirements,
                repo_analysis=repo_analysis,
                dependency_analysis=dependency_analysis,
            )

            # IMPORTANT:
            # Persist the plan before making the first provider call.
            self._save_plan()

            result.chunks_total = len(
                self.plan.chunks
            )

            self._update_state_metadata(
                {
                    "implementation_mode": (
                        "incremental"
                    ),
                    "implementation_complete": (
                        False
                    ),
                    "implementation_chunks_total": (
                        result.chunks_total
                    ),
                    "implementation_chunks_completed": (
                        0
                    ),
                    "implementation_iterations": (
                        0
                    ),
                }
            )

            logger.info(
                "Incremental implementation plan "
                "contains %d logical chunks",
                result.chunks_total,
            )

            for chunk in self.plan.chunks:

                if (
                        result.iterations
                        >= self.max_iterations
                ):
                    raise RuntimeError(
                        "Maximum incremental "
                        "generation iterations reached: "
                        f"{self.max_iterations}"
                    )

                result.iterations += 1

                self._generate_chunk(
                    chunk=chunk,
                    requirements=requirements,
                    repo_analysis=repo_analysis,
                    dependency_analysis=dependency_analysis,
                )

                chunk.generated = True

                if self.verify_each_chunk:
                    self._verify_chunk(
                        chunk
                    )

                chunk.verified = True

                result.chunks_completed += 1

                self._update_state_metadata(
                    {
                        "implementation_chunks_completed": (
                            result.chunks_completed
                        ),
                        "implementation_iterations": (
                            result.iterations
                        ),
                    }
                )

                # Persist after every chunk.
                self._save_plan()

            result.status = "completed"

            result.files_created = (
                self._collect_plan_files()
            )

            result.files_modified = list(
                result.files_created
            )

            self._update_state_metadata(
                {
                    "implementation_mode": (
                        "incremental"
                    ),
                    "implementation_complete": (
                        True
                    ),
                    "implementation_chunks_total": (
                        result.chunks_total
                    ),
                    "implementation_chunks_completed": (
                        result.chunks_completed
                    ),
                    "implementation_iterations": (
                        result.iterations
                    ),
                    "files_written": (
                        result.files_created
                    ),
                }
            )

        except Exception as exc:

            logger.exception(
                "Incremental generation failed"
            )

            result.status = "failed"

            result.errors.append(
                str(exc)
            )

            self.state.add_error(
                "Incremental generation: "
                + str(exc)
            )

            self._update_state_metadata(
                {
                    "implementation_mode": (
                        "incremental"
                    ),
                    "implementation_complete": (
                        False
                    ),
                    "implementation_chunks_total": (
                        result.chunks_total
                    ),
                    "implementation_chunks_completed": (
                        result.chunks_completed
                    ),
                    "implementation_iterations": (
                        result.iterations
                    ),
                    "implementation_error": (
                        str(exc)
                    ),
                }
            )

        result.duration_seconds = (
                time.time() - started
        )

        self._save_result(
            result
        )

        return result

    # ==================================================================
    # Requirements
    # ==================================================================

    def _validate_requirements(
            self,
            requirements: str,
    ):

        if not requirements:
            raise ValueError(
                "No implementation requirements "
                "provided."
            )

        if len(
                requirements.strip()
        ) < 512:
            raise ValueError(
                "README/requirements are too small "
                "for incremental implementation."
            )

    # ==================================================================
    # Planning
    # ==================================================================

    def _create_plan(
            self,
            requirements: str,
            repo_analysis: str,
            dependency_analysis: str,
    ) -> GenerationPlan:

        language, framework = (
            self._detect_language_and_framework(
                requirements
            )
        )

        chunks = (
            self._build_plan(
                requirements,
                language,
                framework,
            )
        )

        return GenerationPlan(
            language=language,
            framework=framework,
            chunks=chunks,
            requirements_summary=(
                self._summarize_requirements(
                    requirements
                )
            ),
            metadata={
                "planner": (
                    "deterministic-v1"
                ),
                "target_chunk_kb": (
                    self.target_chunk_kb
                ),
                "max_context_kb": (
                    self.max_context_kb
                ),
                "repo_analysis_available": bool(
                    repo_analysis
                ),
                "dependency_analysis_available": bool(
                    dependency_analysis
                ),
            },
        )

    def _build_plan(
            self,
            requirements: str,
            language: str,
            framework: str,
    ) -> List[CodeChunk]:

        explicit_files = (
            self._extract_file_paths(
                requirements
            )
        )

        if explicit_files:

            chunks = []

            for index, filepath in enumerate(
                    explicit_files,
                    start=1,
            ):

                chunks.append(
                    CodeChunk(
                        chunk_id=(
                            f"file-{index}"
                        ),
                        file_path=filepath,
                        description=(
                            "Implement the required "
                            f"functionality for "
                            f"{filepath} according "
                            "to the requirements."
                        ),
                        order=index,
                        target_kb=(
                            self.target_chunk_kb
                        ),
                    )
                )

            return chunks

        if language == "python":
            return self._python_plan(
                framework
            )

        if language in {
            "javascript",
            "typescript",
        }:
            return self._javascript_plan(
                language
            )

        if language == "java":
            return self._java_plan()

        return self._generic_plan()

    @staticmethod
    def _extract_file_paths(
            requirements: str,
    ) -> List[str]:

        pattern = (
            r"(?:^|[\s`(])"
            r"((?:src/|app/|lib/|tests?/|"
            r"config/|docs/)?"
            r"[A-Za-z0-9_.-]+"
            r"(?:/[A-Za-z0-9_.-]+)*"
            r"\."
            r"(?:py|js|jsx|ts|tsx|java|kt|go|rs|"
            r"cs|cpp|c|h|json|yaml|yml|toml|xml|"
            r"md|txt|sql|html|css|scss|properties))"
            r"(?:[\s)`.,]|$)"
        )

        matches = re.findall(
            pattern,
            requirements,
            re.MULTILINE,
        )

        result = []

        for filepath in matches:

            filepath = filepath.strip(
                "`'\".,);("
            )

            if filepath not in result:
                result.append(
                    filepath
                )

        return result[:50]

    # ==================================================================
    # Default language plans
    # ==================================================================

    @staticmethod
    def _python_plan(
            framework: str,
    ) -> List[CodeChunk]:

        descriptions = [
            (
                "Create the application entry point "
                "and configuration."
            ),
            (
                "Create domain models and data structures."
            ),
            (
                "Implement core business logic."
            ),
            (
                "Implement services and external "
                "integrations."
            ),
            (
                "Implement API or application "
                "interface."
            ),
            (
                "Implement validation and error handling."
            ),
            (
                "Create automated tests."
            ),
        ]

        return [
            CodeChunk(
                chunk_id=f"python-{index}",
                file_path="src",
                description=description,
                order=index,
                target_kb=1.0,
            )
            for index, description in enumerate(
                descriptions,
                start=1,
            )
        ]

    @staticmethod
    def _javascript_plan(
            language: str,
    ) -> List[CodeChunk]:

        descriptions = [
            "Create project entry point and configuration.",
            "Create types/models and shared interfaces.",
            "Implement core business logic.",
            "Implement services and integrations.",
            "Implement UI/application components.",
            "Implement validation and error handling.",
            "Create automated tests.",
        ]

        return [
            CodeChunk(
                chunk_id=f"{language}-{index}",
                file_path="src",
                description=description,
                order=index,
                target_kb=1.0,
            )
            for index, description in enumerate(
                descriptions,
                start=1,
            )
        ]

    @staticmethod
    def _java_plan() -> List[CodeChunk]:

        descriptions = [
            "Create application entry point and configuration.",
            "Create domain models and state.",
            "Implement calculation or business logic.",
            "Implement services and supporting utilities.",
            "Implement the user interface.",
            "Implement validation and error handling.",
            "Create automated tests.",
        ]

        return [
            CodeChunk(
                chunk_id=f"java-{index}",
                file_path="src",
                description=description,
                order=index,
                target_kb=1.0,
            )
            for index, description in enumerate(
                descriptions,
                start=1,
            )
        ]

    @staticmethod
    def _generic_plan() -> List[CodeChunk]:

        descriptions = [
            "Create project skeleton and entry point.",
            "Create core data structures and interfaces.",
            "Implement core business logic.",
            "Implement integrations and I/O.",
            "Implement validation and error handling.",
            "Create automated tests.",
        ]

        return [
            CodeChunk(
                chunk_id=f"core-{index}",
                file_path="src",
                description=description,
                order=index,
                target_kb=1.0,
            )
            for index, description in enumerate(
                descriptions,
                start=1,
            )
        ]

    # ==================================================================
    # Language detection
    # ==================================================================

    @staticmethod
    def _detect_language_and_framework(
            requirements: str,
    ) -> Tuple[str, str]:

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
            language = "auto-detect"

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

        return (
            language,
            framework,
        )

    @staticmethod
    def _summarize_requirements(
            requirements: str,
    ) -> str:

        lines = [
            line.strip()
            for line in requirements.splitlines()
            if line.strip()
        ]

        return "\n".join(
            lines[:60]
        )

    # ==================================================================
    # Chunk generation
    # ==================================================================

    def _generate_chunk(
            self,
            chunk: CodeChunk,
            requirements: str,
            repo_analysis: str,
            dependency_analysis: str,
    ):

        logger.info(
            "Generating chunk %s: %s",
            chunk.chunk_id,
            chunk.description,
        )

        for iteration in range(
                1,
                self.max_chunk_iterations + 1,
        ):

            chunk.iterations = iteration

            context = (
                self._build_generation_context(
                    chunk=chunk,
                    requirements=requirements,
                    repo_analysis=repo_analysis,
                    dependency_analysis=dependency_analysis,
                )
            )

            prompt = (
                self._build_chunk_prompt(
                    chunk,
                    context,
                )
            )

            response = self._generate(
                prompt,
                context,
            )

            if self._apply_response(
                    response
            ):

                logger.info(
                    "Chunk %s completed "
                    "on iteration %d",
                    chunk.chunk_id,
                    iteration,
                )

                return

            logger.warning(
                "Chunk %s produced no applicable files "
                "on iteration %d",
                chunk.chunk_id,
                iteration,
            )

        raise RuntimeError(
            f"Chunk {chunk.chunk_id} failed "
            f"after {self.max_chunk_iterations} "
            "attempts."
        )

    # ==================================================================
    # Context
    # ==================================================================

    def _build_generation_context(
            self,
            chunk: CodeChunk,
            requirements: str,
            repo_analysis: str,
            dependency_analysis: str,
    ) -> Dict[str, Any]:

        context = {
            "chunk": asdict(chunk),
            "language": (
                self.plan.language
                if self.plan
                else ""
            ),
            "framework": (
                self.plan.framework
                if self.plan
                else ""
            ),
            "requirements": self._limit_text(
                requirements,
                int(
                    self.max_context_kb
                    * 1024
                ),
            ),
            "repo_analysis": self._limit_text(
                repo_analysis,
                1536,
            ),
            "dependency_analysis": (
                self._limit_text(
                    dependency_analysis,
                    1536,
                )
            ),
            "current_files": {},
        }

        budget = int(
            self.max_context_kb
            * 1024
        )

        for filepath in self._find_relevant_files(
                chunk
        ):

            if budget <= 0:
                break

            content = self._read_repo_file(
                filepath
            )

            if content is None:
                continue

            encoded = content.encode(
                "utf-8"
            )

            if len(encoded) > budget:
                content = (
                    encoded[:budget]
                    .decode(
                        "utf-8",
                        errors="ignore",
                    )
                )

            context[
                "current_files"
            ][filepath] = content

            budget -= len(
                content.encode(
                    "utf-8"
                )
            )

        return context

    def _find_relevant_files(
            self,
            chunk: CodeChunk,
    ) -> List[str]:

        repo = (
            self.workspace.repo_path
        )

        if not repo.exists():
            return []

        target = (
            chunk.file_path.strip("/")
        )

        candidates = []

        for path in repo.rglob("*"):

            if not path.is_file():
                continue

            if self._should_ignore_path(
                    path
            ):
                continue

            relative = path.relative_to(
                repo
            ).as_posix()

            if target:

                if (
                        relative == target
                        or relative.startswith(
                    target + "/"
                )
                ):
                    candidates.append(
                        relative
                    )

            else:
                candidates.append(
                    relative
                )

        preferred = [
            "README.md",
            "pom.xml",
            "build.gradle",
            "build.gradle.kts",
            "package.json",
            "pyproject.toml",
            "requirements.txt",
        ]

        ordered = []

        for filename in preferred:

            if filename in candidates:
                ordered.append(
                    filename
                )

        for filename in sorted(
                candidates
        ):

            if filename not in ordered:
                ordered.append(
                    filename
                )

        return ordered[:20]

    @staticmethod
    def _should_ignore_path(
            path: Path,
    ) -> bool:

        ignored = {
            ".git",
            ".ox2",
            "__pycache__",
            "node_modules",
            ".venv",
            "venv",
            "dist",
            "build",
            "target",
            ".idea",
        }

        return bool(
            set(path.parts)
            & ignored
        )

    def _read_repo_file(
            self,
            relative_path: str,
    ) -> Optional[str]:

        repo = (
            self.workspace.repo_path
            .resolve()
        )

        path = (
                repo / relative_path
        ).resolve()

        try:
            path.relative_to(
                repo
            )
        except ValueError:
            return None

        try:

            if not path.exists():
                return None

            return path.read_text(
                encoding="utf-8"
            )

        except (
                OSError,
                UnicodeDecodeError,
        ):
            return None

    # ==================================================================
    # Prompt
    # ==================================================================

    def _build_chunk_prompt(
            self,
            chunk: CodeChunk,
            context: Dict[str, Any],
    ) -> str:

        current_files = []

        for filepath, content in (
                context[
                    "current_files"
                ].items()
        ):

            current_files.append(
                "### CURRENT FILE: "
                + filepath
                + "\n"
                + "```text\n"
                + content
                + "\n```\n"
            )

        return f"""
You are an incremental software implementation agent.

You are implementing ONE logical unit of a larger project.

DO NOT generate the entire project.

LANGUAGE:
{context["language"]}

FRAMEWORK:
{context["framework"]}

REQUIREMENTS:
{context["requirements"]}

REPOSITORY ANALYSIS:
{context["repo_analysis"]}

DEPENDENCY ANALYSIS:
{context["dependency_analysis"]}

CURRENT IMPLEMENTATION UNIT:
ID: {chunk.chunk_id}

TARGET:
{chunk.file_path}

DESCRIPTION:
{chunk.description}

CURRENT REPOSITORY STATE:
{"".join(current_files)}

IMPLEMENTATION RULES:

1. Implement ONLY the current logical unit.
2. Preserve existing working functionality.
3. Never overwrite unrelated functionality.
4. Follow the existing project architecture.
5. Reuse existing code where appropriate.
6. Do not invent unnecessary dependencies.
7. Write production-quality code.
8. Make the smallest coherent change necessary.
9. If modifying an existing file, return its COMPLETE resulting content.
10. Never return a partial file.
11. Do not return explanations outside file blocks.

OUTPUT FORMAT:

## FILE: relative/path.ext
```text
complete file content
Return only files that must be created or modified.
""".strip()

# ==================================================================
# Provider
# ==================================================================

def _generate(
        self,
        prompt: str,
        context: Dict[str, Any],
):

    last_error = None

    for provider_name in (
            self.provider_chain
    ):

        if provider_name == "FAIL":
            break

        try:

            provider = (
                self.provider_registry
                .get_provider(
                    provider_name
                )
            )

            return provider.generate(
                prompt,
                context,
            )

        except Exception as exc:

            last_error = exc

            logger.warning(
                "Incremental provider %s failed: %s",
                provider_name,
                exc,
            )

    raise RuntimeError(
        "All incremental generation "
        "providers failed. "
        f"Last error: {last_error}"
    )

# ==================================================================
# Response parsing/application
# ==================================================================

def _apply_response(
        self,
        response: Any,
) -> bool:

    text = (
        response.content
        if hasattr(
            response,
            "content",
        )
        else str(response)
    )

    files = self._parse_files(
        text
    )

    if not files:
        return False

    applied = False

    for filepath, content in files:

        if self._write_repo_file(
                filepath,
                content,
        ):
            applied = True

    return applied

def _parse_files(
        self,
        response: str,
) -> List[
    Tuple[str, str]
]:

    patterns = [
        (
            r"##\s*FILE:\s*"
            r"([^\n]+?)\s*\n"
            r"```[^\n]*\n"
            r"(.*?)"
            r"```"
        ),
        (
            r"##\s*FILE:\s*"
            r"([^\n]+?)\s*\n"
            r"(.*?)(?="
            r"\n##\s*FILE:|$)"
        ),
    ]

    matches = []

    for pattern in patterns:

        matches = re.findall(
            pattern,
            response,
            re.DOTALL,
        )

        if matches:
            break

    result = []

    for filepath, content in matches:

        filepath = filepath.strip()

        safe_path = (
            self._safe_relative_path(
                filepath
            )
        )

        if safe_path is None:

            logger.warning(
                "Rejected unsafe generated path: %s",
                filepath,
            )

            continue

        content = content.strip()

        if not content:
            continue

        result.append(
            (
                safe_path,
                content,
            )
        )

    return result

def _safe_relative_path(
        self,
        filepath: str,
) -> Optional[str]:

    if not filepath:
        return None

    if filepath.startswith("/"):
        return None

    path = Path(
        filepath
    )

    if ".." in path.parts:
        return None

    repo = (
        self.workspace.repo_path
        .resolve()
    )

    target = (
            repo / path
    ).resolve()

    try:

        target.relative_to(
            repo
        )

    except ValueError:

        return None

    return path.as_posix()

def _write_repo_file(
        self,
        filepath: str,
        content: str,
) -> bool:

    path = (
            self.workspace.repo_path
            / filepath
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    existing = None

    if path.exists():

        try:

            existing = path.read_text(
                encoding="utf-8"
            )

        except (
                OSError,
                UnicodeDecodeError,
        ):

            existing = None

    if (
            self.preserve_existing_code
            and existing == content
    ):

        logger.info(
            "No change: %s",
            filepath,
        )

        return False

    path.write_text(
        content,
        encoding="utf-8",
    )

    logger.info(
        "Generated: %s",
        filepath,
    )

    return True

# ==================================================================
# Verification
# ==================================================================

def _verify_chunk(
        self,
        chunk: CodeChunk,
):

    target = (
            self.workspace.repo_path
            / chunk.file_path
    )

    if target.is_file():

        if not target.exists():
            raise RuntimeError(
                f"Generated file missing: "
                f"{target}"
            )

        return

    if target.is_dir():

        files = [
            path
            for path in target.rglob("*")
            if (
                    path.is_file()
                    and not self._should_ignore_path(
                path
            )
            )
        ]

        if not files:

            logger.warning(
                "No generated files found "
                "under %s",
                chunk.file_path,
            )

# ==================================================================
# Persistence
# ==================================================================

    def _save_plan(self):
        """
        Persist the current implementation plan.

        This MUST exist because the plan is saved before the first
        provider request and again after every completed chunk.
        """

        if self.plan is None:
            return

        payload = {
            "language": self.plan.language,
            "framework": self.plan.framework,
            "requirements_summary": (
                self.plan.requirements_summary
            ),
            "created_at": (
                self.plan.created_at
            ),
            "metadata": self.plan.metadata,
            "chunks": [
                asdict(chunk)
                for chunk in self.plan.chunks
            ],
        }

        self.workspace.write(
            "implementation_plan.json",
            json.dumps(
                payload,
                indent=2,
            ),
        )

    def _save_result(
            self,
            result: GenerationResult,
    ):
        """
        Persist final incremental generation result.

        This MUST also execute on failure so that the test harness can
        inspect exactly what happened.
        """

        self.workspace.write(
            "incremental_generation_result.json",
            json.dumps(
                asdict(result),
                indent=2,
            ),
        )

    def _update_state_metadata(
            self,
            values: Dict[str, Any],
    ):
        """
        Safely update PipelineState metadata.

        PipelineState already exposes a metadata dictionary, so keep
        incremental-generation telemetry there for the orchestrator and
        test scripts.
        """

        if not hasattr(
                self.state,
                "metadata",
        ):
            self.state.metadata = {}

        self.state.metadata.update(
            values
        )

    # ==================================================================
    # Generated-file reporting
    # ==================================================================

    def _collect_plan_files(
            self,
    ) -> List[str]:

        if self.plan is None:
            return []

        files = set()

        for chunk in self.plan.chunks:

            target = (
                    self.workspace.repo_path
                    / chunk.file_path
            )

            if target.is_file():

                files.add(
                    target.relative_to(
                        self.workspace.repo_path
                    ).as_posix()
                )

            elif target.is_dir():

                for path in target.rglob("*"):

                    if (
                            path.is_file()
                            and not self._should_ignore_path(
                        path
                    )
                    ):

                        files.add(
                            path.relative_to(
                                self.workspace.repo_path
                            ).as_posix()
                        )

        return sorted(
            files
        )

    # ==================================================================
    # Utilities
    # ==================================================================

    @staticmethod
    def _limit_text(
            text: str,
            max_bytes: int,
    ) -> str:

        if not text:
            return ""

        encoded = text.encode(
            "utf-8"
        )

        if len(encoded) <= max_bytes:
            return text

        return (
                encoded[:max_bytes]
                .decode(
                    "utf-8",
                    errors="ignore",
                )
                + "\n\n"
                  "[Context truncated by "
                  "incremental generator.]"
        )