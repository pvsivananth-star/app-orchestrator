import os
from typing import Dict, Any

from google import genai
from google.genai import types

from .base import (
    BaseProvider,
    ProviderResponse,
    ProviderError,
    ProviderErrorType,
)


class GeminiProvider(BaseProvider):
    """
    Google Gemini provider.

    The BaseProvider is responsible for:
        - model fallback
        - retry handling
        - rate limiting
        - caching

    This provider is responsible for:
        - Gemini client initialization
        - Gemini API requests
        - Gemini-specific error handling
        - Gemini usage extraction
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)

        self.api_key = os.getenv("GEMINI_API_KEY")

        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY not found in environment"
            )

        # Primary model comes from YAML/config.
        self.model = config.get(
            "model",
            "gemini-3.7-flash",
        )

        # Keep provider-specific fallback configuration.
        #
        # BaseProvider.generate() is responsible for selecting
        # fallback models.
        self.fallback_models = config.get(
            "fallback_models",
            [
                "gemini-3.6-flash",
                "gemini-3.5-flash",
                "gemini-3.5-flash-lite",
            ],
        )

        # BaseProvider timeout is expressed in seconds.
        # google-genai HttpOptions.timeout expects milliseconds.
        timeout = config.get(
            "timeout",
            60,
        )

        http_options = types.HttpOptions(
            timeout=int(float(timeout) * 1000)
        )

        self.client = genai.Client(
            api_key=self.api_key,
            http_options=http_options,
        )

    def _validate_config(self):
        """
        Validate provider configuration.
        """

        if "name" not in self.config:
            raise ValueError(
                "Missing config key: name"
            )

    def _generate(
            self,
            prompt: str,
            context: Dict[str, Any],
    ) -> ProviderResponse:
        """
        Required implementation of BaseProvider._generate().

        The BaseProvider owns model fallback.

        This method therefore performs one generation using
        the currently selected model.
        """

        model = context.get(
            "model",
            self.config.get(
                "model",
                self.model,
            ),
        )

        return self._call_model(
            prompt=prompt,
            context=context,
            model=model,
        )

    def _call_model(
            self,
            prompt: str,
            context: Dict[str, Any],
            model: str,
    ) -> ProviderResponse:
        """
        Call a specific Gemini model.
        """

        try:
            config_kwargs = {}

            # -------------------------------------------------
            # Generation parameters
            # -------------------------------------------------

            if "temperature" in context:
                config_kwargs["temperature"] = float(
                    context["temperature"]
                )

            if "max_tokens" in context:
                config_kwargs["max_output_tokens"] = int(
                    context["max_tokens"]
                )

            if "top_p" in context:
                config_kwargs["top_p"] = float(
                    context["top_p"]
                )

            if "top_k" in context:
                config_kwargs["top_k"] = int(
                    context["top_k"]
                )

            # -------------------------------------------------
            # Gemini generation configuration
            # -------------------------------------------------

            generation_config = (
                types.GenerateContentConfig(
                    automatic_function_calling=(
                        types.AutomaticFunctionCallingConfig(
                            disable=True
                        )
                    ),
                    **config_kwargs,
                )
            )

            # -------------------------------------------------
            # Gemini API call
            # -------------------------------------------------

            response = self.client.models.generate_content(
                model=model,
                contents=prompt,
                config=generation_config,
            )

            # -------------------------------------------------
            # Validate response
            # -------------------------------------------------

            if not response.text:
                raise ProviderError(
                    error_type=ProviderErrorType.UNKNOWN,
                    message=(
                        f"Empty response from Gemini "
                        f"model {model}"
                    ),
                    provider=self.provider_name,
                    retryable=True,
                )

            # -------------------------------------------------
            # Extract usage
            # -------------------------------------------------

            usage = {}

            if (
                    hasattr(response, "usage_metadata")
                    and response.usage_metadata
            ):
                usage = {
                    "prompt_tokens": getattr(
                        response.usage_metadata,
                        "prompt_token_count",
                        0,
                    ),
                    "completion_tokens": getattr(
                        response.usage_metadata,
                        "candidates_token_count",
                        0,
                    ),
                    "total_tokens": getattr(
                        response.usage_metadata,
                        "total_token_count",
                        0,
                    ),
                }

            # -------------------------------------------------
            # Return normalized provider response
            # -------------------------------------------------

            return ProviderResponse(
                content=response.text,
                provider=self.provider_name,
                model=model,
                usage=usage,
            )

        except ProviderError:
            # Preserve our own normalized errors.
            raise

        except Exception as exc:
            error_msg = str(exc)
            error_lower = error_msg.lower()

            # -------------------------------------------------
            # Model not found
            # -------------------------------------------------

            if (
                    "404" in error_msg
                    or "not found" in error_lower
                    or "model_not_found" in error_lower
            ):
                raise ProviderError(
                    error_type=ProviderErrorType.UNKNOWN,
                    message=(
                        f"Gemini model not found "
                        f"({model}): {error_msg}"
                    ),
                    provider=self.provider_name,
                    retryable=True,
                )

            # -------------------------------------------------
            # Authentication / authorization
            # -------------------------------------------------

            if (
                    "401" in error_msg
                    or "403" in error_msg
                    or "authentication" in error_lower
                    or "api key" in error_lower
                    or "permission" in error_lower
            ):
                raise ProviderError(
                    error_type=(
                        ProviderErrorType.AUTHENTICATION
                    ),
                    message=(
                        f"Gemini authentication error: "
                        f"{error_msg}"
                    ),
                    provider=self.provider_name,
                    retryable=False,
                )

            # -------------------------------------------------
            # Rate limit / quota / temporary service failure
            # -------------------------------------------------

            if (
                    "429" in error_msg
                    or "quota" in error_lower
                    or "rate limit" in error_lower
                    or "resource exhausted" in error_lower
                    or "503" in error_msg
                    or "unavailable" in error_lower
            ):
                raise ProviderError(
                    error_type=(
                        ProviderErrorType.RATE_LIMIT
                    ),
                    message=(
                        f"Gemini rate/quota/service "
                        f"error on {model}: {error_msg}"
                    ),
                    provider=self.provider_name,
                    retryable=True,
                )

            # -------------------------------------------------
            # Invalid request
            # -------------------------------------------------

            if (
                    "400" in error_msg
                    or "invalid argument" in error_lower
                    or "invalid request" in error_lower
            ):
                raise ProviderError(
                    error_type=(
                        ProviderErrorType.INVALID_REQUEST
                    ),
                    message=(
                        f"Invalid Gemini request: "
                        f"{error_msg}"
                    ),
                    provider=self.provider_name,
                    retryable=False,
                )

            # -------------------------------------------------
            # Unknown Gemini error
            # -------------------------------------------------

            raise ProviderError(
                error_type=ProviderErrorType.UNKNOWN,
                message=(
                    f"Gemini error on {model}: "
                    f"{error_msg}"
                ),
                provider=self.provider_name,
                retryable=True,
            )