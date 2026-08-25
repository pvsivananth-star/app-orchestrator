import pytest

from app_orchestrator.providers.gemini import GeminiProvider


@pytest.mark.anyio
async def test_gemini_provider_agent_framework():
    provider = GeminiProvider(
        {
            "name": "gemini",
            "model": "gemini-3.5-flash",
        }
    )

    response = await provider.generate_with_agent_framework(
        prompt="Reply with exactly: PROVIDER AGENT FRAMEWORK OK",
        context={},
    )

    assert response.content
    assert "PROVIDER AGENT FRAMEWORK OK" in response.content
    assert response.provider == "gemini"
    assert response.model == "gemini-3.5-flash"