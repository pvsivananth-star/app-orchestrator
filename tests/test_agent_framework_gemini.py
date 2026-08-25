import pytest

from app_orchestrator.runtime import GeminiAgentRuntime


@pytest.mark.anyio
async def test_gemini_agent_runtime():
    runtime = GeminiAgentRuntime(
        model="gemini-3.5-flash",
        instructions="Answer briefly.",
    )

    result = await runtime.run(
        "Reply with exactly: AGENT RUNTIME OK"
    )

    assert result.text
    assert "AGENT RUNTIME OK" in result.text