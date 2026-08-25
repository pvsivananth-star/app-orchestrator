from abc import ABC, abstractmethod
from typing import Any


class AgentRuntime(ABC):
    """
    Application-level runtime abstraction.

    The application depends on this interface rather than directly
    depending on a specific model provider.
    """

    @abstractmethod
    async def run(
            self,
            prompt: str,
            **kwargs: Any,
    ) -> Any:
        """Execute an agent request."""
        raise NotImplementedError


class GeminiAgentRuntime(AgentRuntime):
    """Agent Framework runtime backed by Gemini."""

    def __init__(
            self,
            model: str | None = None,
            instructions: str = "You are a helpful assistant.",
    ):
        from .agent_framework import AgentFrameworkGeminiRuntime

        self._runtime = AgentFrameworkGeminiRuntime(
            model=model,
            instructions=instructions,
        )

    async def run(
            self,
            prompt: str,
            **kwargs: Any,
    ) -> Any:
        return await self._runtime.run(prompt)