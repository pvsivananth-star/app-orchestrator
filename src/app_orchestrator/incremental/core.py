"""Main incremental code generator."""

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
    """Stateful incremental implementation engine."""

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
                provider_chain or self.provider_registry.get_agent_providers("implementation")
        )

        self.target_chunk_kb = self._get_float("target_chunk_kb", DEFAULT_TARGET_CHUNK_KB)
        self.max_context_kb = self._get_float("max_context_kb", DEFAULT_MAX_CONTEXT_KB)
        self.max_iterations = self._get_int("max_iterations", DEFAULT_MAX_ITERATIONS)
        self.max_chunk_iterations = self._get_int("max_chunk_iterations", DEFAULT_MAX_CHUNK_ITERATIONS)
        self.verify_each_chunk = self._get_bool("verify_each_chunk", True)
        self.preserve_existing_code = self._get_bool("preserve_existing_code", True)
        self.min_requirements_length = self._get_int("min_requirements_length", DEFAULT_MIN_REQUIREMENTS_LENGTH)

        self.plan: Optional[GenerationPlan] = None
        self.planner = IncrementalPlanner(self.target_chunk_kb)
        self.parser = ResponseParser()

    def _get_value(self, key: str, default: Any) -> Any:
        if key in self.config:
            return self.config[key]
        env_key = "APP_ORCHESTRATOR_INCREMENTAL_" + key.upper()
        return os.getenv(env_key, default)

    def _get_int(self, key: str, default: int) -> int:
        try:
            return int(self._get_value(key, default))
        except (TypeError, ValueError):
            return default

    def _get_float(self, key: str, default: float) -> float:
        try:
            return float(self._get_value(key, default))
        except (TypeError, ValueError):
            return default

    def _get_bool(self, key: str, default: bool) -> bool:
        value = self._get_value(key, default)
        if isinstance(value, bool):
            return value
        return str(value).lower() in {"1", "true", "yes", "on"}

    def generate(
            self,
            requirements: str,
            repo_analysis: str = "",
            dependency_analysis: str = "",
    ) -> GenerationResult:
        started = time.time()
        result = GenerationResult(status="started")

        try:
            self._validate_requirements(requirements)
            logger.info("Creating incremental implementation plan")

            language, framework, chunks = self.planner.create_plan(
                requirements, repo_analysis, dependency_analysis
            )

            self.plan = GenerationPlan(
                language=language,
                framework=framework,
                chunks=chunks,
                requirements_summary=self._summarize_requirements(requirements),
                metadata={
                    "planner": "deterministic-v1",
                    "target_chunk_kb": self.target_chunk_kb,
                    "max_context_kb": self.max_context_kb,
                    "repo_analysis_available": bool(repo_analysis),
                    "dependency_analysis_available": bool(dependency_analysis),
                },
            )

            self._save_plan()
            result.chunks_total = len(self.plan.chunks)

            self._update_state_metadata({
                "implementation_mode": "incremental",
                "implementation_complete": False,
                "implementation_chunks_total": result.chunks_total,
                "implementation_chunks_completed": 0,
                "implementation_iterations": 0,
            })

            logger.info("Incremental plan contains %d chunks", result.chunks_total)

            for chunk in self.plan.chunks:
                if result.iterations >= self.max_iterations:
                    raise RuntimeError(f"Max iterations reached: {self.max_iterations}")

                result.iterations += 1
                self._generate_chunk(chunk, requirements, repo_analysis, dependency_analysis)

                chunk.generated = True
                if self.verify_each_chunk:
                    self._verify_chunk(chunk)
                chunk.verified = True

                result.chunks_completed += 1
                self._update_state_metadata({
                    "implementation_chunks_completed": result.chunks_completed,
                    "implementation_iterations": result.iterations,
                })
                self._save_plan()

            result.status = "completed"
            result.files_created = self._collect_plan_files()
            result.files_modified = list(result.files_created)

            self._update_state_metadata({
                "implementation_mode": "incremental",
                "implementation_complete": True,
                "implementation_chunks_total": result.chunks_total,
                "implementation_chunks_completed": result.chunks_completed,
                "implementation_iterations": result.iterations,
                "files_written": result.files_created,
            })

        except Exception as exc:
            logger.exception("Incremental generation failed")
            result.status = "failed"
            result.errors.append(str(exc))
            self.state.add_error(f"Incremental generation: {exc}")
            self._update_state_metadata({
                "implementation_mode": "incremental",
                "implementation_complete": False,
                "implementation_error": str(exc),
            })

        result.duration_seconds = time.time() - started
        self._save_result(result)
        return result

    def _validate_requirements(self, requirements: str):
        if not requirements:
            raise ValueError("No implementation requirements provided.")
        if len(requirements.strip()) < self.min_requirements_length:
            raise ValueError(
                f"Requirements too small for incremental implementation. "
                f"Minimum {self.min_requirements_length} chars, got {len(requirements.strip())}"
            )

    @staticmethod
    def _summarize_requirements(requirements: str) -> str:
        lines = [line.strip() for line in requirements.splitlines() if line.strip()]
        return "\n".join(lines[:60])

    def _generate_chunk(self, chunk, requirements, repo_analysis, dependency_analysis):
        logger.info("Generating chunk %s: %s", chunk.chunk_id, chunk.description)

        for iteration in range(1, self.max_chunk_iterations + 1):
            chunk.iterations = iteration
            context = self._build_context(chunk, requirements, repo_analysis, dependency_analysis)
            prompt = self._build_prompt(chunk, context)
            response = self._generate_response(prompt, context)

            if self._apply_response(response):
                logger.info("Chunk %s completed on iteration %d", chunk.chunk_id, iteration)
                return

            logger.warning("Chunk %s no files on iteration %d", chunk.chunk_id, iteration)

        raise RuntimeError(f"Chunk {chunk.chunk_id} failed after {self.max_chunk_iterations} attempts.")

    def _build_context(self, chunk, requirements, repo_analysis, dependency_analysis):
        context = {
            "chunk": {
                "id": chunk.chunk_id,
                "file_path": chunk.file_path,
                "description": chunk.description,
            },
            "language": self.plan.language if self.plan else "",
            "framework": self.plan.framework if self.plan else "",
            "requirements": self._limit_text(requirements, int(self.max_context_kb * 1024)),
            "repo_analysis": self._limit_text(repo_analysis, 1024),
            "dependency_analysis": self._limit_text(dependency_analysis, 512),
            "current_files": {},
        }

        budget = int(self.max_context_kb * 1024)
        for filepath in self._find_relevant_files(chunk):
            if budget <= 0:
                break
            content = self._read_repo_file(filepath)
            if content is None:
                continue
            encoded = content.encode("utf-8")
            if len(encoded) > budget:
                content = encoded[:budget].decode("utf-8", errors="ignore")
            context["current_files"][filepath] = content
            budget -= len(content.encode("utf-8"))

        return context

    def _build_prompt(self, chunk, context):
        current_files = []
        for filepath, content in context["current_files"].items():
            current_files.append(f"### CURRENT FILE: {filepath}\n```text\n{content}\n```\n")

        return f"""
You are an incremental software implementation agent.

Implement ONLY this logical unit. DO NOT generate the entire project.

LANGUAGE: {context["language"]}
FRAMEWORK: {context["framework"]}

REQUIREMENTS:
{context["requirements"]}

CURRENT UNIT:
ID: {context["chunk"]["id"]}
FILE: {context["chunk"]["file_path"]}
DESCRIPTION: {context["chunk"]["description"]}

CURRENT REPOSITORY STATE:
{"".join(current_files)}

OUTPUT FORMAT:
## FILE: relative/path.ext
```text
complete file content
```

Return only files that must be created or modified.
""".strip()
    def _generate_response(self, prompt, context):
        """Generate response using provider chain."""
        last_error = None
        for provider_name in self.provider_chain:
            if provider_name == "FAIL":
                break
            try:
                provider = self.provider_registry.get_provider(provider_name)
                return provider.generate(prompt, context)
            except Exception as exc:
                last_error = exc
                logger.warning("Provider %s failed: %s", provider_name, exc)
        raise RuntimeError(f"All providers failed. Last error: {last_error}")

    def _apply_response(self, response) -> bool:
        text = response.content if hasattr(response, "content") else str(response)
        logger.debug("Applying response of length %d chars", len(text))
        files = self.parser.parse_files(text)
        if not files:
            logger.warning("No files parsed, using entire response as output.txt")
            files = [("output.txt", text)]
        applied = False
        for filepath, content in files:
            if self._write_repo_file(filepath, content):
                applied = True
        return applied

    def _write_repo_file(self, filepath: str, content: str) -> bool:
        path = self.workspace.repo_path / filepath
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            try:
                existing = path.read_text(encoding="utf-8")
                if self.preserve_existing_code and existing == content:
                    logger.info("No change: %s", filepath)
                    return False
            except (OSError, UnicodeDecodeError):
                pass
        path.write_text(content, encoding="utf-8")
        logger.info("Generated: %s", filepath)
        return True

    def _find_relevant_files(self, chunk):
        repo = self.workspace.repo_path
        if not repo.exists():
            return []
        target = chunk.file_path.strip("/")
        candidates = []
        for path in repo.rglob("*"):
            if not path.is_file():
                continue
            if self._should_ignore_path(path):
                continue
            relative = path.relative_to(repo).as_posix()
            if target and (relative == target or relative.startswith(target + "/")):
                candidates.append(relative)
            elif not target:
                candidates.append(relative)
        ordered = [f for f in PREFERRED_FILES if f in candidates]
        ordered.extend(sorted([f for f in candidates if f not in ordered]))
        return ordered[:20]

    @staticmethod
    def _should_ignore_path(path: Path) -> bool:
        return bool(set(path.parts) & IGNORED_PATH_PATTERNS)

    def _read_repo_file(self, relative_path: str):
        repo = self.workspace.repo_path.resolve()
        path = (repo / relative_path).resolve()
        try:
            path.relative_to(repo)
        except ValueError:
            return None
        try:
            if not path.exists():
                return None
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None

    def _verify_chunk(self, chunk):
        target = self.workspace.repo_path / chunk.file_path
        if "." in chunk.file_path:
            if not target.exists():
                raise RuntimeError(f"Missing file: {target}")
            return
        if target.exists() and target.is_dir():
            files = [
                p for p in target.rglob("*")
                if p.is_file() and not self._should_ignore_path(p)
            ]
            if not files:
                logger.warning("No files generated under %s", chunk.file_path)
            return
        logger.warning("Directory %s does not exist", chunk.file_path)

    def _save_plan(self):
        if self.plan is None:
            return
        payload = {
            "language": self.plan.language,
            "framework": self.plan.framework,
            "requirements_summary": self.plan.requirements_summary,
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
        self.workspace.write(FILE_IMPLEMENTATION_PLAN, json.dumps(payload, indent=2))

    def _save_result(self, result):
        self.workspace.write(
            FILE_INCREMENTAL_RESULT,
            json.dumps(
                {
                    "status": result.status,
                    "files_created": result.files_created,
                    "chunks_completed": result.chunks_completed,
                    "chunks_total": result.chunks_total,
                    "iterations": result.iterations,
                    "errors": result.errors,
                    "duration_seconds": result.duration_seconds,
                },
                indent=2,
            ),
        )

    def _update_state_metadata(self, values):
        if not hasattr(self.state, "metadata"):
            self.state.metadata = {}
        self.state.metadata.update(values)

    def _collect_plan_files(self):
        if self.plan is None:
            return []
        files = set()
        for chunk in self.plan.chunks:
            target = self.workspace.repo_path / chunk.file_path
            if target.is_file():
                files.add(target.relative_to(self.workspace.repo_path).as_posix())
            elif target.is_dir():
                for path in target.rglob("*"):
                    if path.is_file() and not self._should_ignore_path(path):
                        files.add(path.relative_to(self.workspace.repo_path).as_posix())
        return sorted(files)

    @staticmethod
    def _limit_text(text: str, max_bytes: int) -> str:
        if not text:
            return ""
        encoded = text.encode("utf-8")
        if len(encoded) <= max_bytes:
            return text
        return encoded[:max_bytes].decode("utf-8", errors="ignore") + "\n\n[Context truncated.]"

