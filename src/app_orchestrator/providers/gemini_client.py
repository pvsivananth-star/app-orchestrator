import os
from typing import Any
from agent_framework._clients import BaseChatClient
from agent_framework._types import ChatMessage, ChatResponse
from google import genai
from google.genai import types

from app_orchestrator.config import get_gemini_api_key, get_gemini_model

class GeminiChatClient(BaseChatClient):
    """Concrete Gemini implementation extending Microsoft Agent Framework's BaseChatClient."""

    def __init__(self, model: str | None = None, api_key: str | None = None):
        super().__init__()
        self.model = model or get_gemini_model()
        resolved_key = api_key or get_gemini_api_key()
        self.client = genai.Client(api_key=resolved_key)

    async def _inner_get_response(
            self,
            messages: list[ChatMessage],
            **kwargs: Any
    ) -> ChatResponse:
        """Translates Agent Framework ChatMessage format to Google GenAI SDK format."""
        contents = []
        for msg in messages:
            contents.append(
                types.Content(
                    role="user" if msg.role == "user" else "model",
                    parts=[types.Part.from_text(text=msg.content or "")]
                )
            )

        # Call the Google GenAI SDK
        response = self.client.models.generate_content(
            model=self.model,
            contents=contents
        )

        return ChatResponse(
            content=response.text,
            role="assistant"
        )
