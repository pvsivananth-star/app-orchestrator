import asyncio
import unittest

from agent_framework import Agent
from agent_framework.gemini import GeminiChatClient


MODEL = "gemini-3.5-flash"


async def run_test() -> str:
    agent = Agent(
        client=GeminiChatClient(model=MODEL),
        instructions="Answer briefly.",
    )

    result = await agent.run(
        "Reply with exactly: AGENT FRAMEWORK GEMINI OK"
    )

    return str(result)


class TestAgentFrameworkGemini(unittest.TestCase):
    def test_gemini_agent(self):
        result = asyncio.run(run_test())
        self.assertIn("AGENT FRAMEWORK GEMINI OK", result)


if __name__ == "__main__":
    unittest.main()