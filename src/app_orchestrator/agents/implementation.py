"""Implementation Agent - incremental code generation."""

from __future__ import annotations

from typing import Dict, Any, List
import logging
import os

from ..agent import Agent
from ..incremental import (
    IncrementalCodeGenerator,
)


logger = logging.getLogger(__name__)


class ImplementationAgent(Agent):
    """
    Implementation agent.

    The implementation agent is intentionally thin.

    It prepares the requirements/context and delegates actual
    code generation to IncrementalCodeGenerator.

    This prevents large README/project requests from becoming one
    enormous provider request.
    """

    def _get_provider_chain(self) -> List[str]:
        return (
            self.provider_registry
            .get_agent_providers(
                "implementation"
            )
        )

    # ------------------------------------------------------------------
    # Normal Agent interface
    # ------------------------------------------------------------------

    def _build_prompt(
            self,
            context: Dict[str, Any],
    ) -> str:
        """
        Retained for compatibility with the Agent abstraction.

        Actual implementation generation is performed by
        IncrementalCodeGenerator.
        """

        requirements = (
                self._read_artifact(
                    "requirements.md"
                )
                or self._read_artifact(
            "clarified_requirements.md"
        )
                or self._read_artifact(
            "user_requirements.md"
        )
        )

        if not requirements:
            requirements = (
                "No requirements found."
            )

        return (
            "Incremental implementation generation "
            "is enabled.\n\n"
            "Requirements:\n"
            f"{requirements}"
        )

    def _parse_response(
            self,
            response: str,
            context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Compatibility parser.

        IncrementalCodeGenerator owns response parsing during
        implementation generation.
        """

        return {
            "status": "incremental",
            "response": response,
        }

    # ------------------------------------------------------------------
    # Main implementation entry point
    # ------------------------------------------------------------------

    def run(self) -> Dict[str, Any]:
        """
        Generate the project incrementally.

        Required flow:

            requirements
                ->
            repository analysis
                ->
            dependency analysis
                ->
            incremental planner
                ->
            small generation requests
                ->
            apply
                ->
            next chunk
                ->
            final implementation state
        """

        logger.info(
            "Running %s in incremental mode",
            self.__class__.__name__,
        )

        requirements = (
            self._load_requirements()
        )

        if not requirements:
            message = (
                "Implementation cannot start: "
                "no requirements artifact found. "
                "Create requirements.md or "
                "clarified_requirements.md first."
            )

            self.state.add_error(
                message
            )

            raise RuntimeError(
                message
            )

        repo_analysis = (
                self._read_artifact(
                    "repo_analysis.md"
                )
                or ""
        )

        dependency_analysis = (
                self._read_artifact(
                    "dependency_analysis.md"
                )
                or self._read_artifact(
            "dependencies.md"
        )
                or ""
        )

        config = (
            self._get_incremental_config()
        )

        logger.info(
            "Starting incremental implementation "
            "with provider chain: %s",
            self.provider_chain,
        )

        generator = IncrementalCodeGenerator(
            workspace=self.workspace,
            state=self.state,
            provider_registry=(
                self.provider_registry
            ),
            provider_chain=(
                self.provider_chain
            ),
            config=config,
        )

        result = generator.generate(
            requirements=requirements,
            repo_analysis=repo_analysis,
            dependency_analysis=(
                dependency_analysis
            ),
        )

        self._update_state(
            result
        )

        if result.status != "completed":
            raise RuntimeError(
                "Incremental implementation "
                "failed: "
                + "; ".join(
                    result.errors
                )
            )

        logger.info(
            "Incremental implementation completed: "
            "%d/%d chunks in %.2fs",
            result.chunks_completed,
            result.chunks_total,
            result.duration_seconds,
        )

        return {
            "status": "implemented",
            "mode": "incremental",
            "chunks_completed": (
                result.chunks_completed
            ),
            "chunks_total": (
                result.chunks_total
            ),
            "iterations": (
                result.iterations
            ),
            "files_created": (
                result.files_created
            ),
            "files_modified": (
                result.files_modified
            ),
            "duration_seconds": (
                result.duration_seconds
            ),
            "errors": result.errors,
        }

    # ------------------------------------------------------------------
    # Requirements
    # ------------------------------------------------------------------

    def _load_requirements(
            self,
    ) -> str:
        """
        Load the strongest available requirements artifact.

        Priority:

            requirements.md
            clarified_requirements.md
            user_requirements.md
            README.md
        """

        candidates = [
            "requirements.md",
            "clarified_requirements.md",
            "user_requirements.md",
            "README.md",
        ]

        for filename in candidates:
            content = (
                self._read_artifact(
                    filename
                )
            )

            if content and content.strip():
                logger.info(
                    "Implementation requirements "
                    "loaded from %s",
                    filename,
                )

                return content

        return ""

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def _get_incremental_config(
            self,
    ) -> Dict[str, Any]:
        """
        Read incremental-generation configuration.

        Environment variables are supported so the initial rollout
        does not require another mapping.yaml schema change.
        """

        return {
            "target_chunk_kb": self._env_float(
                "APP_ORCHESTRATOR_INCREMENTAL_TARGET_CHUNK_KB",
                1.0,
            ),
            "max_context_kb": self._env_float(
                "APP_ORCHESTRATOR_INCREMENTAL_MAX_CONTEXT_KB",
                6.0,
            ),
            "max_iterations": self._env_int(
                "APP_ORCHESTRATOR_INCREMENTAL_MAX_ITERATIONS",
                20,
            ),
            "max_chunk_iterations": self._env_int(
                "APP_ORCHESTRATOR_INCREMENTAL_MAX_CHUNK_ITERATIONS",
                3,
            ),
            "verify_each_chunk": self._env_bool(
                "APP_ORCHESTRATOR_INCREMENTAL_VERIFY_EACH_CHUNK",
                True,
            ),
            "preserve_existing_code": self._env_bool(
                "APP_ORCHESTRATOR_INCREMENTAL_PRESERVE_EXISTING_CODE",
                True,
            ),
        }

    @staticmethod
    def _env_int(
            name: str,
            default: int,
    ) -> int:
        value = os.getenv(
            name
        )

        if value is None:
            return default

        try:
            return int(value)
        except ValueError:
            logger.warning(
                "Invalid integer environment "
                "variable %s=%r; using %s",
                name,
                value,
                default,
            )

            return default

    @staticmethod
    def _env_float(
            name: str,
            default: float,
    ) -> float:
        value = os.getenv(
            name
        )

        if value is None:
            return default

        try:
            return float(value)
        except ValueError:
            logger.warning(
                "Invalid float environment "
                "variable %s=%r; using %s",
                name,
                value,
                default,
            )

            return default

    @staticmethod
    def _env_bool(
            name: str,
            default: bool,
    ) -> bool:
        value = os.getenv(
            name
        )

        if value is None:
            return default

        return value.strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    def _update_state(
            self,
            result: Any,
    ):
        """
        Preserve implementation information in PipelineState.

        This metadata is intentionally compact; the detailed
        generation plan/result is stored under .ox2.
        """

        if not hasattr(
                self.state,
                "metadata",
        ):
            self.state.metadata = {}

        self.state.metadata[
            "implementation_mode"
        ] = "incremental"

        self.state.metadata[
            "implementation_complete"
        ] = (
                result.status == "completed"
        )

        self.state.metadata[
            "implementation_chunks_completed"
        ] = result.chunks_completed

        self.state.metadata[
            "implementation_chunks_total"
        ] = result.chunks_total

        self.state.metadata[
            "implementation_iterations"
        ] = result.iterations

        self.state.metadata[
            "implementation_duration_seconds"
        ] = result.duration_seconds

        self.state.metadata[
            "files_written"
        ] = result.files_created