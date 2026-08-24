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

        # Fallback list containing active Gemini 3.x models
        if not getattr(self, "fallback_models", None):
            self.fallback_models = [
                "gemini-3.5-flash-lite",  # High throughput / Generous free quota
                "gemini-3.1-flash-lite",  # Secondary fast fallback
                "gemini-3.6-flash",       # Standard Flash workhorse
                "gemini-3.5-flash",       # General reasoning fallback
            ]
        # Client with timeout
        http_options = types.HttpOptions(timeout=30000)
        self.client = genai.Client(api_key=self.api_key, http_options=http_options)
    
    def _validate_config(self):
        if "name" not in self.config:
            raise ValueError("Missing config key: name")
    
    def _call_model(self, prompt: str, context: Dict[str, Any], model: str) -> ProviderResponse:
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
            
            gen_config = types.GenerateContentConfig(
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                **config_kwargs
            )
            
            response = self.client.models.generate_content(
                model=model,
                contents=prompt,
                config=gen_config
            )
            
            if not response.text:
                raise ProviderError(
                    error_type=ProviderErrorType.UNKNOWN,
                    message=f"Empty response from {model}",
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
                model=model,
                usage=usage
            )
        except Exception as e:
            error_msg = str(e)
            if "404" in error_msg:
                raise ProviderError(
                    error_type=ProviderErrorType.UNKNOWN,
                    message=f"Model not found ({model}): {error_msg}",
                    provider=self.provider_name,
                    retryable=False
                )
            elif "503" in error_msg or "quota" in error_msg.lower() or "rate" in error_msg.lower():
                raise ProviderError(
                    error_type=ProviderErrorType.RATE_LIMIT,
                    message=f"Rate limit or high demand on {model}: {error_msg}",
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
                    message=f"Gemini error on {model}: {error_msg}",
                    provider=self.provider_name,
                    retryable=True
                )
