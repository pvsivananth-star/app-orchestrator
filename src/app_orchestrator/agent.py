"""Base agent class with context management, file I/O and execution."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Iterable
import logging
import os
import re

from .workspace import Workspace
from .state import PipelineState
from .providers import ProviderRegistry


logger = logging.getLogger(__name__)


class Agent(ABC):
    """Base class for all agents.

    The base agent deliberately does not implement provider-specific
    generation logic. It provides:

    - provider-chain execution
    - state/context construction
    - controlled artifact selection
    - context-size budgeting
    - artifact helpers

    Incremental code generation is implemented separately so that
    normal agents and code-generation agents remain decoupled.
    """

    def __init__(
            self,
            workspace: Workspace,
            state: PipelineState,
            provider_registry: ProviderRegistry,
    ):
        self.workspace = workspace
        self.state = state
        self.provider_registry = provider_registry
        self.provider_chain = self._get_provider_chain()

    # ------------------------------------------------------------------
    # Abstract agent contract
    # ------------------------------------------------------------------

    @abstractmethod
    def _get_provider_chain(self) -> List[str]:
        """Return the provider chain for this agent."""
        pass

    @abstractmethod
    def _build_prompt(self, context: Dict[str, Any]) -> str:
        """Build the LLM prompt from the supplied context."""
        pass

    @abstractmethod
    def _parse_response(
            self,
            response: str,
            context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Parse the LLM response and update artifacts/state."""
        pass

    # ------------------------------------------------------------------
    # Main execution
    # ------------------------------------------------------------------

    def run(self) -> Dict[str, Any]:
        """Execute the agent using its configured provider chain."""

        logger.info(
            "Running %s",
            self.__class__.__name__,
        )

        context = self._build_context()

        prompt = self._build_prompt(context)

        logger.info(
            "%s prompt size: %d chars (~%d KB)",
            self.__class__.__name__,
            len(prompt),
            max(1, len(prompt) // 1024),
        )

        last_error = None

        for provider_name in self.provider_chain:
            if provider_name == "FAIL":
                break

            try:
                provider = self.provider_registry.get_provider(
                    provider_name
                )

                response = provider.generate(
                    prompt,
                    context,
                )

                result = self._parse_response(
                    response.content,
                    context,
                )

                logger.info(
                    "%s completed successfully",
                    self.__class__.__name__,
                )

                return result

            except Exception as exc:
                last_error = exc

                logger.warning(
                    "Provider %s failed: %s",
                    provider_name,
                    exc,
                )

                continue

        error_msg = (
            f"All providers failed for "
            f"{self.__class__.__name__}. "
            f"Last error: {last_error}"
        )

        self.state.add_error(error_msg)

        raise RuntimeError(error_msg)

    # ------------------------------------------------------------------
    # Context configuration
    # ------------------------------------------------------------------

    def _context_max_kb(self) -> int:
        """Return the maximum context size for this agent.

        Configuration can be supplied through environment variables
        without changing the existing mapping.yaml structure.

        APP_ORCHESTRATOR_CONTEXT_MAX_KB
            Default: 32 KB

        APP_ORCHESTRATOR_CONTEXT_README_KB
            Default: 8 KB

        These are safety limits for context assembly. They do not
        truncate the repository itself.
        """

        value = os.getenv(
            "APP_ORCHESTRATOR_CONTEXT_MAX_KB",
            "32",
        )

        try:
            return max(1, int(value))
        except ValueError:
            return 32

    def _context_readme_max_kb(self) -> int:
        """Maximum README/requirements context size."""

        value = os.getenv(
            "APP_ORCHESTRATOR_CONTEXT_README_KB",
            "8",
        )

        try:
            return max(1, int(value))
        except ValueError:
            return 8

    def _context_artifact_limit(self) -> int:
        """Maximum number of artifacts included in generic context."""

        value = os.getenv(
            "APP_ORCHESTRATOR_CONTEXT_MAX_ARTIFACTS",
            "12",
        )

        try:
            return max(1, int(value))
        except ValueError:
            return 12

    # ------------------------------------------------------------------
    # Context construction
    # ------------------------------------------------------------------

    def _build_context(self) -> Dict[str, Any]:
        """Build a controlled context for the current agent.

        The old implementation loaded every .ox2 artifact into every
        agent. That causes unnecessary prompt growth as the pipeline
        gets larger.

        This implementation:

        1. Always exposes state.
        2. Selects high-value artifacts first.
        3. Gives README/requirements artifacts priority.
        4. Applies a global context budget.
        5. Preserves metadata about omitted artifacts.
        6. Never modifies or truncates the actual workspace files.
        """

        context: Dict[str, Any] = {
            "workspace": self.workspace,
            "state": self.state.to_dict(),
            "artifacts": {},
            "context_info": {},
            "loop_a_iteration": self.state.loop_a_iteration,
            "loop_b_iteration": self.state.loop_b_iteration,
        }

        filenames = self.workspace.list_files()

        selected_files = self._select_context_artifacts(
            filenames
        )

        max_bytes = (
                self._context_max_kb() * 1024
        )

        used_bytes = 0
        omitted: List[str] = []

        for filename in selected_files:
            content = self.workspace.read(filename)

            if content is None:
                continue

            encoded_size = len(
                content.encode("utf-8")
            )

            # README/requirements get their own controlled limit.
            if self._is_requirements_artifact(filename):
                content = self._limit_text(
                    content,
                    self._context_readme_max_kb() * 1024,
                    )

                encoded_size = len(
                    content.encode("utf-8")
                )

            if (
                    used_bytes + encoded_size
                    > max_bytes
            ):
                omitted.append(filename)
                continue

            context["artifacts"][filename] = content

            used_bytes += encoded_size

        context["context_info"] = {
            "agent": self.__class__.__name__,
            "total_workspace_artifacts": len(filenames),
            "selected_artifacts": len(
                context["artifacts"]
            ),
            "omitted_artifacts": omitted,
            "context_bytes": used_bytes,
            "context_kb": round(
                used_bytes / 1024,
                2,
                ),
            "context_max_kb": self._context_max_kb(),
        }

        logger.info(
            "%s context: %d/%d artifacts, %.2f KB",
            self.__class__.__name__,
            len(context["artifacts"]),
            len(filenames),
            context["context_info"]["context_kb"],
        )

        if omitted:
            logger.debug(
                "%s omitted artifacts: %s",
                self.__class__.__name__,
                ", ".join(omitted),
            )

        return context

    # ------------------------------------------------------------------
    # Artifact selection
    # ------------------------------------------------------------------

    def _select_context_artifacts(
            self,
            filenames: Iterable[str],
    ) -> List[str]:
        """Select the most useful artifacts for the current agent.

        This is intentionally conservative.

        Agent-specific prompt builders can still call _read_artifact()
        directly when they need a particular artifact.

        The goal here is to stop unrelated artifacts from being
        automatically included in the provider context.
        """

        files = list(filenames)

        if not files:
            return []

        agent_name = (
            self.__class__.__name__
            .lower()
        )

        priority_groups = self._artifact_priority_groups(
            agent_name
        )

        selected: List[str] = []

        # First select known high-value artifacts.
        for group in priority_groups:
            for filename in files:
                normalized = filename.lower()

                if normalized in group:
                    if filename not in selected:
                        selected.append(filename)

        # Then select artifacts containing important keywords.
        keyword_patterns = self._artifact_keyword_patterns(
            agent_name
        )

        for filename in files:
            if filename in selected:
                continue

            normalized = filename.lower()

            if any(
                    re.search(pattern, normalized)
                    for pattern in keyword_patterns
            ):
                selected.append(filename)

        # Do not blindly load everything.
        max_artifacts = (
            self._context_artifact_limit()
        )

        return selected[:max_artifacts]

    def _artifact_priority_groups(
            self,
            agent_name: str,
    ) -> List[set]:
        """Return artifact priority groups."""

        common = [
            {
                "user_requirements.md",
                "clarified_requirements.md",
                "requirements.md",
            },
            {
                "readme.md",
                "README.md",
            },
        ]

        if "interaction" in agent_name:
            return common

        if "requirement" in agent_name:
            return [
                {
                    "user_requirements.md",
                    "clarified_requirements.md",
                    "requirements.md",
                },
                {
                    "readme.md",
                    "README.md",
                },
            ]

        if "implementation" in agent_name:
            return [
                {
                    "requirements.md",
                    "clarified_requirements.md",
                    "user_requirements.md",
                },
                {
                    "repo_analysis.md",
                },
                {
                    "dependency_analysis.md",
                    "dependencies.md",
                },
                {
                    "architecture.md",
                },
                {
                    "readme.md",
                    "README.md",
                },
            ]

        if "repo" in agent_name:
            return [
                {
                    "requirements.md",
                    "clarified_requirements.md",
                    "user_requirements.md",
                },
                {
                    "readme.md",
                    "README.md",
                },
            ]

        if "dependency" in agent_name:
            return [
                {
                    "requirements.md",
                    "clarified_requirements.md",
                },
                {
                    "repo_analysis.md",
                },
                {
                    "readme.md",
                    "README.md",
                },
            ]

        if "verification" in agent_name:
            return [
                {
                    "implementation_log.md",
                },
                {
                    "requirements.md",
                    "clarified_requirements.md",
                },
                {
                    "repo_analysis.md",
                },
            ]

        if "test" in agent_name:
            return [
                {
                    "requirements.md",
                    "clarified_requirements.md",
                },
                {
                    "repo_analysis.md",
                },
                {
                    "implementation_log.md",
                },
            ]

        if "security" in agent_name:
            return [
                {
                    "requirements.md",
                    "clarified_requirements.md",
                },
                {
                    "repo_analysis.md",
                },
            ]

        if "lint" in agent_name:
            return [
                {
                    "requirements.md",
                    "clarified_requirements.md",
                },
                {
                    "repo_analysis.md",
                },
            ]

        if "doc" in agent_name:
            return [
                {
                    "requirements.md",
                    "clarified_requirements.md",
                },
                {
                    "repo_analysis.md",
                },
                {
                    "implementation_log.md",
                },
            ]

        return common

    def _artifact_keyword_patterns(
            self,
            agent_name: str,
    ) -> List[str]:
        """Return secondary artifact filename patterns."""

        if "implementation" in agent_name:
            return [
                r"require",
                r"repo",
                r"depend",
                r"architect",
                r"design",
            ]

        if "verification" in agent_name:
            return [
                r"implement",
                r"test",
                r"compile",
                r"verify",
            ]

        if "test" in agent_name:
            return [
                r"implement",
                r"require",
                r"depend",
            ]

        if "security" in agent_name:
            return [
                r"implement",
                r"depend",
                r"architect",
            ]

        if "doc" in agent_name:
            return [
                r"implement",
                r"require",
                r"architect",
            ]

        return [
            r"require",
            r"readme",
        ]

    # ------------------------------------------------------------------
    # Context helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_requirements_artifact(
            filename: str,
    ) -> bool:
        """Return True for requirement/README artifacts."""

        normalized = filename.lower()

        return normalized in {
            "readme.md",
            "requirements.md",
            "clarified_requirements.md",
            "user_requirements.md",
        }

    @staticmethod
    def _limit_text(
            content: str,
            max_bytes: int,
    ) -> str:
        """Limit text without splitting UTF-8 characters."""

        encoded = content.encode("utf-8")

        if len(encoded) <= max_bytes:
            return content

        truncated = encoded[:max_bytes]

        # Decode safely if the boundary falls in a multibyte
        # UTF-8 character.
        safe = truncated.decode(
            "utf-8",
            errors="ignore",
        )

        return (
                safe
                + "\n\n"
                + "[Context truncated by orchestrator. "
                  "The original artifact remains unchanged.]"
        )

    # ------------------------------------------------------------------
    # Artifact helpers
    # ------------------------------------------------------------------

    def _read_artifact(
            self,
            filename: str,
    ) -> Optional[str]:
        """Read an artifact from the .ox2 workspace."""

        return self.workspace.read(filename)

    def _write_artifact(
            self,
            filename: str,
            content: str,
    ):
        """Write an artifact to the .ox2 workspace."""

        self.workspace.write(
            filename,
            content,
        )