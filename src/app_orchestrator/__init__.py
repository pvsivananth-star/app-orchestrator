import asyncio
from agent_framework import Agent
from app_orchestrator.providers.gemini_client import GeminiChatClient


async def run_demo() -> None:
    # Instantiate custom chat client and Agent primitive
    client = GeminiChatClient()
    agent = Agent(
        client=client,
        name="RequirementAnalyst",
        instructions="You are an expert software architect analyzing technical business requirements."
    )

    print("Sending task to RequirementAnalyst Agent...")
    response = await agent.get_response("Analyze requirement: Add real-time FX spot rate converter to x2-forex-app.")

    print("\n=== Agent Output ===")
    print(getattr(response, "text", None) or getattr(response, "content", str(response)))


def main() -> None:
    asyncio.run(run_demo())