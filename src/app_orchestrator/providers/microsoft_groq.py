
import os
from typing import Dict, Any
import asyncio
import logging
from .base import BaseProvider, ProviderResponse, ProviderError, ProviderErrorType

logger = logging.getLogger(__name__)

class MicrosoftGroqProvider(BaseProvider):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not found in environment")
        self.model_name = config.get("model", "mixtral-8x7b-32768")
        self._kernel = None
        self._initialize_kernel()
    
    def _validate_config(self):
        if "name" not in self.config:
            raise ValueError("Missing config key: name")
        try:
            import semantic_kernel
        except ImportError:
            raise ImportError("semantic-kernel not installed. Run: uv sync --extra microsoft-agent")
    
    def _initialize_kernel(self):
        try:
            from semantic_kernel import Kernel
            from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion
            self._kernel = Kernel()
            service = OpenAIChatCompletion(
                service_id="groq",
                ai_model_id=self.model_name,
                api_key=self.api_key,
                endpoint="https://api.groq.com/openai/v1"
            )
            self._kernel.add_service(service)
        except Exception as e:
            raise ProviderError(ProviderErrorType.UNKNOWN, f"Kernel init failed: {e}", self.provider_name, False)
    
    def _generate(self, prompt: str, context: Dict[str, Any]) -> ProviderResponse:
        try:
            from semantic_kernel.contents import ChatHistory
            chat = ChatHistory()
            if "system_instruction" in context:
                chat.add_system_message(context["system_instruction"])
            chat.add_user_message(prompt)
            response = asyncio.run(self._generate_async(chat, context))
            return ProviderResponse(content=response, provider=self.provider_name, model=self.model_name)
        except Exception as e:
            if "rate" in str(e).lower():
                raise ProviderError(ProviderErrorType.RATE_LIMIT, f"Rate limit: {e}", self.provider_name, True)
            raise ProviderError(ProviderErrorType.UNKNOWN, str(e), self.provider_name, True)
    
    async def _generate_async(self, chat, context):
        from semantic_kernel.connectors.ai.open_ai import OpenAIChatPromptExecutionSettings
        settings = OpenAIChatPromptExecutionSettings()
        settings.temperature = context.get("temperature", 0.7)
        settings.max_tokens = context.get("max_tokens", 8192)
        settings.top_p = context.get("top_p", 0.95)
        response = await self._kernel.get_service("groq").get_chat_message_content(chat_history=chat, settings=settings)
        return str(response)

