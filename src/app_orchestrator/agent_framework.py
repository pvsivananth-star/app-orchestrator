from agent_framework import Agent
from agent_framework.gemini import GeminiChatClient

from .config import get_gemini_api_key, get_gemini_model


class AgentFrameworkGeminiRuntime:
    """
    Agent Framework runtime backed by Google Gemini.

    Agent Framework execution is asynchronous, so this runtime remains
    separate from the existing synchronous BaseProvider contract.
    """

    def __init__(
            self,
            model: str | None = None,
            instructions: str = "You are a helpful assistant.",
    ):
        self.model = model or get_gemini_model()
        self.instructions = instructions

        self.client = GeminiChatClient(
            api_key=get_gemini_api_key(),
            model=self.model,
        )

        self.agent = Agent(
            client=self.client,
            instructions=self.instructions,
        )

    async def run(self, prompt: str):
        """Execute the Agent Framework agent."""
        if not prompt.strip():
            raise ValueError("Agent prompt cannot be empty.")

        return await self.agent.run(prompt)

    async def text(self, prompt: str) -> str:
        """Execute the agent and return response text."""
        result = await self.run(prompt)

        if not result.text:
            raise RuntimeError(
                f"Agent Framework returned an empty response "
                f"from Gemini model {self.model}"
            )

        return result.text