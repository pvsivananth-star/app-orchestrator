from typing import Any
from google import genai
from google.genai import types
from agent_framework import BaseChatClient, Message, ChatResponse

from app_orchestrator.config import get_gemini_api_key, get_gemini_model


class GeminiChatClient(BaseChatClient):
    """Concrete Gemini adapter subclassing Microsoft Agent Framework's BaseChatClient."""

    def __init__(self, model: str | None = None, api_key: str | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.model = model or get_gemini_model()
        resolved_key = api_key or get_gemini_api_key()
        self.client = genai.Client(api_key=resolved_key)

    async def _inner_get_response(
            self,
            *,
            messages: list[ChatMessage],
            chat_options: Any | None = None,
            **kwargs: Any,
    ) -> ChatResponse:
        """Translates Agent Framework messages to Google GenAI SDK format and calls the model."""
        contents = []
        for msg in messages:
            role = "user" if getattr(msg, "role", None) == "user" else "model"
            text_content = str(getattr(msg, "text", None) or getattr(msg, "content", "") or "")
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=text_content)]
                )
            )

        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
        )

        return ChatResponse(
            messages=[ChatMessage(role="assistant", text=response.text or "")],
            response_id=getattr(response, "id", "gemini-response"),
        )

    async def _inner_get_streaming_response(
            self,
            *,
            messages: list[ChatMessage],
            chat_options: Any | None = None,
            **kwargs: Any,
    ):
        """Placeholder for streaming support required by BaseChatClient contract."""
        raise NotImplementedError("Streaming is not yet implemented for GeminiChatClient.")