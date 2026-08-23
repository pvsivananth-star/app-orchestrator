import asyncio
from agent_framework import Agent
from app_orchestrator.providers.gemini_client import GeminiChatClient

async def run_demo() -> None:
    # 1. Instantiate concrete provider adapter
    gemini_client = GeminiChatClient()

    # 2. Wrap client inside Microsoft Agent Framework's Agent primitive
    agent = Agent(
        client=gemini_client,
        name="RequirementAnalyst",
        instructions="You are an expert software architect analyzing technical requirements."
    )

    # 3. Execute prompt
    prompt = "Analyze requirement: Add an automated currency conversion tool to x2-forex-app."
    response = await agent.get_response(prompt)

    print("=== Execution Output ===")
    print(response.content)

def main() -> None:
    asyncio.run(run_demo())

if __name__ == "__main__":
    main()