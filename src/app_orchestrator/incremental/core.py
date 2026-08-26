"""Generic, stateful incremental code generation engine."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..constants import (
    DEFAULT_MAX_CHUNK_ITERATIONS,
    DEFAULT_MIN_REQUIREMENTS_LENGTH,
    DEFAULT_TARGET_CHUNK_KB,
    DEFAULT_MAX_CONTEXT_KB,
    DEFAULT_MAX_ITERATIONS,
    FILE_IMPLEMENTATION_PLAN,
    FILE_INCREMENTAL_RESULT,
    IGNORED_PATH_PATTERNS,
    PREFERRED_FILES,
)
from .models import CodeChunk, GenerationPlan, GenerationResult
from .planner import IncrementalPlanner
from .parser import ResponseParser

logger = logging.getLogger(__name__)


class IncrementalCodeGenerator:
    """Generate an application incrementally from deterministic work chunks."""

    def __init__(
            self,
            workspace,
            state,
            provider_registry,
            provider_chain: Optional[List[str]] = None,
            config: Optional[Dict[str, Any]] = None,
    ):
        self.workspace = workspace
        self.state = state
        self.provider_registry = provider_registry
        self.config = config or {}

        self.provider_chain = (
                provider_chain
                or provider_registry.get_agent_providers(
            "implementation"
        )
        )

        if not self.provider_chain:
            raise ValueError(
                "No implementation providers configured."
            )

        self.target_chunk_kb = self._get_float(
            "target_chunk_kb",
            DEFAULT_TARGET_CHUNK_KB,
        )

        self.max_context_kb = self._get_float(
            "max_context_kb",
            DEFAULT_MAX_CONTEXT_KB,
        )

        self.max_iterations = self._get_int(
            "max_iterations",
            DEFAULT_MAX_ITERATIONS,
        )

        self.max_chunk_iterations = self._get_int(
            "max_chunk_iterations",
            DEFAULT_MAX_CHUNK_ITERATIONS,
        )

        self.verify_each_chunk = self._get_bool(
            "verify_each_chunk",
            True,
        )

        self.preserve_existing_code = self._get_bool(
            "preserve_existing_code",
            True,
        )

        self.min_requirements_length = self._get_int(
            "min_requirements_length",
            DEFAULT_MIN_REQUIREMENTS_LENGTH,
        )

        if self.max_iterations < 1:
            raise ValueError(
                "max_iterations must be positive."
            )

        if self.max_chunk_iterations < 1:
            raise ValueError(
                "max_chunk_iterations must be positive."
            )

        if self.max_context_kb <= 0:
            raise ValueError(
                "max_context_kb must be positive."
            )

        if self.target_chunk_kb <= 0:
            raise ValueError(
                "target_chunk_kb must be positive."
            )

        self.plan: Optional[GenerationPlan] = None

        # IMPORTANT:
        # Give the planner the actual repository so that planning is based
        # on the repository structure rather than inventing a new directory.
        self.planner = IncrementalPlanner(
            target_chunk_kb=self.target_chunk_kb,
            repo_path=self.workspace.repo_path,
        )

        self.parser = ResponseParser()

    def _get_value(
            self,
            key: str,
            default: Any,
    ) -> Any:
        if key in self.config:
            return self.config[key]

        return os.getenv(
            "APP_ORCHESTRATOR_INCREMENTAL_"
            + key.upper(),
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
        except (TypeError, ValueError):
            logger.warning(
                "Invalid integer config %s; using %s",
                key,
                default,
            )
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
        except (TypeError, ValueError):
            logger.warning(
                "Invalid numeric config %s; using %s",
                key,
                default,
            )
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

        return str(value).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

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
                "============================================================"
            )
            logger.info(
                "Starting incremental code generation"
            )
            logger.info(
                "Repository: %s",
                self.workspace.repo_path,
            )
            logger.info(
                ".ox2 workspace: %s",
                self.workspace.ox2_path,
            )
            logger.info(
                "============================================================"
            )

            language, framework, chunks = (
                self.planner.create_plan(
                    requirements,
                    repo_analysis,
                    dependency_analysis,
                )
            )

            if not chunks:
                raise RuntimeError(
                    "Planner produced no implementation chunks."
                )

            logger.info(
                "Planner selected language=%s framework=%s",
                language,
                framework,
            )

            for chunk in chunks:
                logger.info(
                    "Planned chunk: %s -> %s",
                    chunk.chunk_id,
                    chunk.file_path,
                )

            self.plan = GenerationPlan(
                language=language,
                framework=framework,
                chunks=chunks,
                requirements_summary=(
                    self._summarize_requirements(
                        requirements
                    )
                ),
                metadata={
                    "planner": "deterministic-v3",
                    "target_chunk_kb": self.target_chunk_kb,
                    "max_context_kb": self.max_context_kb,
                },
            )

            self._save_plan()

            result.chunks_total = len(chunks)

            self._update_state_metadata(
                {
                    "implementation_mode": "incremental",
                    "implementation_complete": False,
                    "implementation_chunks_total": (
                        result.chunks_total
                    ),
                    "implementation_chunks_completed": 0,
                    "implementation_iterations": 0,
                }
            )

            for chunk in chunks:
                if (
                        result.iterations
                        >= self.max_iterations
                ):
                    raise RuntimeError(
                        "Maximum implementation iterations reached: "
                        f"{self.max_iterations}"
                    )

                result.iterations += 1

                logger.info(
                    "------------------------------------------------------------"
                )
                logger.info(
                    "Starting chunk %s/%s: %s",
                    result.chunks_completed + 1,
                    result.chunks_total,
                    chunk.file_path,
                    )

                self._generate_chunk(
                    chunk,
                    requirements,
                    repo_analysis,
                    dependency_analysis,
                )

                chunk.generated = True

                if self.verify_each_chunk:
                    self._verify_chunk(chunk)

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
                    "implementation_complete": True,
                    "files_written": result.files_created,
                }
            )

            logger.info(
                "============================================================"
            )
            logger.info(
                "Incremental generation completed"
            )
            logger.info(
                "Chunks: %d/%d",
                result.chunks_completed,
                result.chunks_total,
            )
            logger.info(
                "Files: %d",
                len(result.files_created),
            )
            logger.info(
                "============================================================"
            )

        except Exception as exc:
            logger.exception(
                "Incremental generation failed"
            )

            result.status = "failed"
            result.errors.append(str(exc))

            if hasattr(
                    self.state,
                    "add_error",
            ):
                self.state.add_error(
                    f"Incremental generation: {exc}"
                )

            self._update_state_metadata(
                {
                    "implementation_complete": False,
                    "implementation_error": str(exc),
                }
            )

        finally:
            result.duration_seconds = (
                    time.time() - started
            )

            self._save_result(result)

        return result

    def _validate_requirements(
            self,
            requirements: str,
    ) -> None:
        if (
                not isinstance(requirements, str)
                or not requirements.strip()
        ):
            raise ValueError(
                "No implementation requirements provided."
            )

        length = len(
            requirements.strip()
        )

        if length < self.min_requirements_length:
            raise ValueError(
                "Requirements too small: minimum "
                f"{self.min_requirements_length} characters, "
                f"got {length}"
            )

    @staticmethod
    def _summarize_requirements(
            requirements: str,
    ) -> str:
        return "\n".join(
            line.strip()
            for line in requirements.splitlines()
            if line.strip()
        )[:6000]

    def _generate_chunk(
            self,
            chunk: CodeChunk,
            requirements: str,
            repo_analysis: str,
            dependency_analysis: str,
    ) -> None:
        logger.info(
            "Generating chunk %s",
            chunk.chunk_id,
        )

        logger.info(
            "Chunk target: %s",
            chunk.file_path,
        )

        last_error: Optional[Exception] = None

        for iteration in range(
                1,
                self.max_chunk_iterations + 1,
        ):
            chunk.iterations = iteration

            logger.info(
                "Chunk %s attempt %d/%d",
                chunk.chunk_id,
                iteration,
                self.max_chunk_iterations,
            )

            try:
                context = self._build_context(
                    chunk,
                    requirements,
                    repo_analysis,
                    dependency_analysis,
                )

                prompt = self._build_prompt(
                    chunk,
                    context,
                )

                logger.info(
                    "Chunk %s prompt size: %d chars",
                    chunk.chunk_id,
                    len(prompt),
                )

                response = self._generate_response(
                    prompt,
                    context,
                )

                response_text = (
                    response.content
                    if hasattr(
                        response,
                        "content",
                    )
                    else str(response)
                )

                logger.info(
                    "Chunk %s provider response: %d chars",
                    chunk.chunk_id,
                    len(response_text),
                )

                if self._apply_response(
                        response,
                        chunk,
                ):
                    logger.info(
                        "Chunk %s generated successfully on attempt %d",
                        chunk.chunk_id,
                        iteration,
                    )
                    return

                last_error = RuntimeError(
                    "Provider response contained no applicable files"
                )

                logger.warning(
                    "Chunk %s produced no applicable files "
                    "on attempt %d",
                    chunk.chunk_id,
                    iteration,
                )

            except Exception as exc:
                last_error = exc

                logger.warning(
                    "Chunk %s attempt %d failed: %s",
                    chunk.chunk_id,
                    iteration,
                    exc,
                    exc_info=True,
                )

        raise RuntimeError(
            f"Chunk {chunk.chunk_id} failed after "
            f"{self.max_chunk_iterations} attempts: "
            f"{last_error}"
        )

    def _build_context(
            self,
            chunk: CodeChunk,
            requirements: str,
            repo_analysis: str,
            dependency_analysis: str,
    ) -> Dict[str, Any]:
        context: Dict[str, Any] = {
            "chunk": {
                "id": chunk.chunk_id,
                "file_path": chunk.file_path,
                "description": chunk.description,
            },
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
                4096,
            ),
            "dependency_analysis": self._limit_text(
                dependency_analysis,
                2048,
            ),
            "current_files": {},
        }

        budget = int(
            self.max_context_kb * 1024
        )

        relevant_files = (
            self._find_relevant_files(chunk)
        )

        logger.info(
            "Chunk %s relevant files: %s",
            chunk.chunk_id,
            relevant_files,
        )

        for filepath in relevant_files:
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
                content = encoded[
                    :budget
                ].decode(
                    "utf-8",
                    errors="ignore",
                )

            context[
                "current_files"
            ][filepath] = content

            budget -= len(
                content.encode("utf-8")
            )

        return context

    def _build_prompt(
            self,
            chunk: CodeChunk,
            context: Dict[str, Any],
    ) -> str:
        current = "".join(
            f"### CURRENT FILE: {p}\n"
            f"```text\n{c}\n```\n"
            for p, c in context[
                "current_files"
            ].items()
        )

        return f"""
You are a generic incremental software implementation agent.

Implement ONLY the requested logical unit.

Preserve compatible existing code.

Do not assume a specific application domain.

IMPORTANT FILE LOCATION RULES:
- The planned TARGET path is authoritative.
- Create or modify the requested file at exactly the TARGET path.
- Do not invent a new project directory.
- Do not move existing files.
- Do not create duplicate source directories.
- If CURRENT FILES are provided, preserve their structure and compatibility.

LANGUAGE: {context['language']}

FRAMEWORK: {context['framework']}

REQUIREMENTS:
{context['requirements']}

CURRENT UNIT:
ID: {context['chunk']['id']}
TARGET: {context['chunk']['file_path']}
DESCRIPTION: {context['chunk']['description']}

REPOSITORY ANALYSIS:
{context['repo_analysis']}

DEPENDENCY ANALYSIS:
{context['dependency_analysis']}

CURRENT FILES:
{current}

Return only files that must be created or modified, using:

## FILE: relative/path.ext
```text
complete file content

""".strip()

    def _generate_response(
            self,
            prompt: str,
            context: Dict[str, Any],
    ):
        last_error: Optional[Exception] = None

        for provider_name in self.provider_chain:
            if (
                    not provider_name
                    or provider_name == "FAIL"
            ):
                continue

            try:
                logger.info(
                    "Calling implementation provider: %s",
                    provider_name,
                )

                provider = (
                    self.provider_registry.get_provider(
                        provider_name
                    )
                )

                response = provider.generate(
                    prompt,
                    context,
                )

                logger.info(
                    "Implementation provider %s returned successfully",
                    provider_name,
                )

                return response

            except Exception as exc:
                last_error = exc

                logger.warning(
                    "Implementation provider %s failed: %s",
                    provider_name,
                    exc,
                    exc_info=True,
                )

        raise RuntimeError(
            "All implementation providers failed: "
            f"{last_error}"
        )

    def _apply_response(
            self,
            response,
            expected_chunk: Optional[CodeChunk] = None,
    ) -> bool:
        text = (
            response.content
            if hasattr(
                response,
                "content",
            )
            else str(response)
        )

        files = self.parser.parse_files(
            text
        )

        if not files:
            logger.warning(
                "Provider response contained no parseable files"
            )
            return False

        logger.info(
            "Provider returned %d file(s): %s",
            len(files),
            [filepath for filepath, _ in files],
        )

        # For incremental generation each chunk has one canonical target.
        # If the model invents another path, normalize it to the planner's
        # target rather than creating another directory.
        if (
                expected_chunk is not None
                and len(files) == 1
        ):
            returned_path, content = files[0]

            if (
                    returned_path
                    != expected_chunk.file_path
            ):
                logger.warning(
                    "Normalizing generated path %r -> planned path %r",
                    returned_path,
                    expected_chunk.file_path,
                )

            files = [
                (
                    expected_chunk.file_path,
                    content,
                )
            ]

        applied = False

        for filepath, content in files:
            if not self._is_safe_relative_path(
                    filepath
            ):
                logger.warning(
                    "Rejected unsafe generated path: %s",
                    filepath,
                )
                continue

            logger.info(
                "Applying generated file: %s",
                filepath,
            )

            if self._write_repo_file(
                    filepath,
                    content,
            ):
                applied = True

        return applied

    def _write_repo_file(
            self,
            filepath: str,
            content: str,
    ) -> bool:
        path = self._safe_repo_path(
            filepath
        )

        logger.info(
            "Repository write target: %s",
            path,
        )

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if (
                path.exists()
                and self.preserve_existing_code
        ):
            try:
                existing = path.read_text(
                    encoding="utf-8"
                )

                if existing == content:
                    logger.info(
                        "No change required: %s",
                        filepath,
                    )
                    return False

                logger.info(
                    "Updating existing file: %s",
                    filepath,
                )

            except (
                    OSError,
                    UnicodeDecodeError,
            ):
                logger.warning(
                    "Unable to compare existing file: %s",
                    filepath,
                )

        path.write_text(
            content,
            encoding="utf-8",
        )

        logger.info(
            "Generated/updated: %s (%d bytes)",
            filepath,
            len(
                content.encode("utf-8")
            ),
        )

        return True

    def _find_relevant_files(
            self,
            chunk: CodeChunk,
    ) -> List[str]:
        repo = self.workspace.repo_path

        if not repo.exists():
            return []

        target = chunk.file_path.strip(
            "/"
        )

        target_parent = (
            Path(target).parent.as_posix()
        )

        candidates: List[str] = []

        for path in repo.rglob("*"):
            if (
                    not path.is_file()
                    or self._should_ignore_path(path)
            ):
                continue

            relative = path.relative_to(
                repo
            ).as_posix()

            # Prefer files in the same source directory as the chunk.
            if (
                    target_parent != "."
                    and relative.startswith(
                target_parent + "/"
            )
            ):
                candidates.append(
                    relative
                )

            elif relative == target:
                candidates.append(
                    relative
                )

        ordered = [
            f
            for f in PREFERRED_FILES
            if f in candidates
        ]

        ordered.extend(
            f
            for f in sorted(candidates)
            if f not in ordered
        )

        return ordered[:20]

    @staticmethod
    def _should_ignore_path(
            path: Path,
    ) -> bool:
        ignored = {
            str(item)
            for item in IGNORED_PATH_PATTERNS
        }

        ignored.update(
            {
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
        )

        return any(
            part in ignored
            for part in path.parts
        )

    def _read_repo_file(
            self,
            relative_path: str,
    ) -> Optional[str]:
        try:
            path = self._safe_repo_path(
                relative_path
            )

            if (
                    not path.exists()
                    or not path.is_file()
            ):
                return None

            return path.read_text(
                encoding="utf-8"
            )

        except (
                OSError,
                UnicodeDecodeError,
                ValueError,
        ):
            logger.debug(
                "Unable to read repository file: %s",
                relative_path,
                exc_info=True,
            )
            return None

    def _verify_chunk(
            self,
            chunk: CodeChunk,
    ) -> None:
        target = self._safe_repo_path(
            chunk.file_path
        )

        logger.info(
            "VERIFY: checking expected generated path: %s",
            target,
        )

        if target.is_file():
            logger.info(
                "VERIFY SUCCESS: %s exists",
                chunk.file_path,
            )
            return

        if target.is_dir():
            files = [
                p
                for p in target.rglob("*")
                if (
                        p.is_file()
                        and not self._should_ignore_path(
                    p
                )
                )
            ]

            if files:
                logger.info(
                    "VERIFY SUCCESS: %s contains %d file(s)",
                    chunk.file_path,
                    len(files),
                )
                return

        logger.error(
            "VERIFY FAILED: expected generated file does not exist: %s",
            target,
        )

        raise RuntimeError(
            "No generated file found for chunk target: "
            f"{chunk.file_path}"
        )

    def _is_safe_relative_path(
            self,
            filepath: str,
    ) -> bool:
        if (
                not filepath
                or filepath.startswith(
            ("/", "\\")
        )
        ):
            return False

        path = Path(filepath)

        return (
                ".." not in path.parts
                and not path.is_absolute()
        )

    def _safe_repo_path(
            self,
            filepath: str,
    ) -> Path:
        if not self._is_safe_relative_path(
                filepath
        ):
            raise ValueError(
                f"Unsafe repository path: {filepath}"
            )

        repo = (
            self.workspace.repo_path.resolve()
        )

        target = (
                repo / filepath
        ).resolve()

        target.relative_to(repo)

        return target

    def _save_plan(self) -> None:
        if not self.plan:
            return

        payload = {
            "language": self.plan.language,
            "framework": self.plan.framework,
            "requirements_summary": (
                self.plan.requirements_summary
            ),
            "created_at": self.plan.created_at,
            "metadata": self.plan.metadata,
            "chunks": [
                {
                    "id": c.chunk_id,
                    "file_path": c.file_path,
                    "description": c.description,
                    "order": c.order,
                    "dependencies": c.dependencies,
                    "generated": c.generated,
                    "verified": c.verified,
                    "iterations": c.iterations,
                }
                for c in self.plan.chunks
            ],
        }

        logger.info(
            ".ox2: saving implementation plan"
        )

        self.workspace.write(
            FILE_IMPLEMENTATION_PLAN,
            json.dumps(
                payload,
                indent=2,
            ),
        )

    def _save_result(
            self,
            result: GenerationResult,
    ) -> None:
        try:
            logger.info(
                ".ox2: saving incremental result: status=%s",
                result.status,
            )

            self.workspace.write(
                FILE_INCREMENTAL_RESULT,
                json.dumps(
                    {
                        "status": result.status,
                        "files_created": result.files_created,
                        "files_modified": result.files_modified,
                        "chunks_completed": result.chunks_completed,
                        "chunks_total": result.chunks_total,
                        "iterations": result.iterations,
                        "errors": result.errors,
                        "duration_seconds": result.duration_seconds,
                    },
                    indent=2,
                ),
            )

        except Exception:
            logger.exception(
                "Failed to persist incremental result"
            )

    def _update_state_metadata(
            self,
            values: Dict[str, Any],
    ) -> None:
        if not hasattr(
                self.state,
                "metadata",
        ):
            self.state.metadata = {}

        self.state.metadata.update(
            values
        )

    def _collect_plan_files(
            self,
    ) -> List[str]:
        if not self.plan:
            return []

        files = set()

        repo = (
            self.workspace.repo_path.resolve()
        )

        for chunk in self.plan.chunks:
            try:
                target = (
                    self._safe_repo_path(
                        chunk.file_path
                    )
                )

            except ValueError:
                continue

            if target.is_file():
                files.add(
                    target.relative_to(
                        repo
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
                                repo
                            ).as_posix()
                        )

        return sorted(files)

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
                + "\n\n[Context truncated.]"
        )