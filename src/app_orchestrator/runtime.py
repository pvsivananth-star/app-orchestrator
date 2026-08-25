from abc import ABC, abstractmethod
from typing import Any, Dict


class AgentRuntime(ABC):
    """Provider-independent asynchronous agent execution contract."""

    @abstractmethod
    async def run(
            self,
            prompt: str,
            **kwargs: Any,
    ) -> Any:
        """Execute an agent request."""
        raise NotImplementedError

    async def text(
            self,
            prompt: str,
            **kwargs: Any,
    ) -> str:
        """Execute an agent request and return response text."""
        result = await self.run(prompt, **kwargs)

        text = getattr(result, "text", None)

        if not text:
            raise RuntimeError(
                "Agent runtime returned an empty response."
            )

        return text


class GeminiAgentRuntime(AgentRuntime):
    """Agent Framework runtime backed by Google Gemini."""

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

    @property
    def model(self) -> str:
        return self._runtime.model

    async def run(
            self,
            prompt: str,
            **kwargs: Any,
    ) -> Any:
        return await self._runtime.run(prompt)