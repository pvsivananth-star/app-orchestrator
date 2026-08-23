import os
from typing import Dict, Any
from google import genai
from google.genai import types
from .base import BaseProvider, ProviderResponse, ProviderError, ProviderErrorType

class GeminiProvider(BaseProvider):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in environment")

        # Fallback away from deprecated models automatically
        raw_model = config.get("model", "gemini-3.6-flash")
        if "2.0-flash-exp" in raw_model:
            self.model_name = "gemini-3.6-flash"
        else:
            self.model_name = raw_model

        # Set 30s timeout for stability
        http_options = types.HttpOptions(timeout=30000)
        self.client = genai.Client(api_key=self.api_key, http_options=http_options)

    def _validate_config(self):
        if "name" not in self.config:
            raise ValueError("Missing config key: name")

    def _generate(self, prompt: str, context: Dict[str, Any]) -> ProviderResponse:
        try:
            config_kwargs = {}
            if "temperature" in context:
                config_kwargs["temperature"] = float(context["temperature"])
            if "max_tokens" in context:
                config_kwargs["max_output_tokens"] = int(context["max_tokens"])
            if "top_p" in context:
                config_kwargs["top_p"] = float(context["top_p"])
            if "top_k" in context:
                config_kwargs["top_k"] = int(context["top_k"])

            # Disable AFC to suppress log warnings if no tools are passed
            gen_config = types.GenerateContentConfig(
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                **config_kwargs
            )

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=gen_config
            )

            if not response.text:
                raise ProviderError(
                    error_type=ProviderErrorType.UNKNOWN,
                    message="Empty response from Gemini",
                    provider=self.provider_name,
                    retryable=True
                )

            usage = {}
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                usage = {
                    "prompt_tokens": getattr(response.usage_metadata, "prompt_token_count", 0),
                    "completion_tokens": getattr(response.usage_metadata, "candidates_token_count", 0),
                    "total_tokens": getattr(response.usage_metadata, "total_token_count", 0),
                }

            return ProviderResponse(
                content=response.text,
                provider=self.provider_name,
                model=self.model_name,
                usage=usage
            )

        except Exception as e:
            error_msg = str(e)
            if "404" in error_msg:
                raise ProviderError(
                    error_type=ProviderErrorType.UNKNOWN,
                    message=f"Model not found ({self.model_name}): {error_msg}",
                    provider=self.provider_name,
                    retryable=False
                )
            elif "503" in error_msg or "quota" in error_msg.lower() or "rate" in error_msg.lower():
                raise ProviderError(
                    error_type=ProviderErrorType.RATE_LIMIT,
                    message=f"Rate limit or high demand: {error_msg}",
                    provider=self.provider_name,
                    retryable=True
                )
            elif "401" in error_msg or "auth" in error_msg.lower():
                raise ProviderError(
                    error_type=ProviderErrorType.AUTHENTICATION,
                    message=f"Authentication error: {error_msg}",
                    provider=self.provider_name,
                    retryable=False
                )
            else:
                raise ProviderError(
                    error_type=ProviderErrorType.UNKNOWN,
                    message=f"Gemini error: {error_msg}",
                    provider=self.provider_name,
                    retryable=True
                )
