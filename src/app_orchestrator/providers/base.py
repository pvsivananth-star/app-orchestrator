import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Any, Optional
import time
import logging
from enum import Enum
import hashlib
import json
from pathlib import Path

logger = logging.getLogger(__name__)

CACHE_DIR = Path(".ox2/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

DISABLE_CACHE = bool(
    int(os.getenv("APP_ORCHESTRATOR_DISABLE_CACHE", "0"))
)


class ProviderErrorType(Enum):
    RATE_LIMIT = "rate_limit"
    CONNECTION = "connection"
    TIMEOUT = "timeout"
    AUTHENTICATION = "authentication"
    INVALID_REQUEST = "invalid_request"
    SERVER_ERROR = "server_error"
    UNKNOWN = "unknown"


@dataclass
class ProviderResponse:
    content: str
    provider: str
    model: str
    usage: Optional[Dict[str, int]] = None
    duration_ms: float = 0.0
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


@dataclass
class ProviderError(Exception):
    error_type: ProviderErrorType
    message: str
    provider: str
    retryable: bool = True
    details: Optional[Dict[str, Any]] = None

    def __str__(self):
        return (
            f"[{self.provider}] "
            f"{self.error_type.value}: "
            f"{self.message}"
        )


class BaseProvider(ABC):

    def __init__(self, config: Dict[str, Any]):

        self.config = config

        self.provider_name = config.get(
            "name",
            self.__class__.__name__,
        )

        self.timeout = config.get(
            "timeout",
            30,
        )

        self.max_retries = config.get(
            "max_retries",
            5,
        )

        self.retry_delay = config.get(
            "retry_delay",
            1.0,
        )

        self.rate_limit_interval = config.get(
            "rate_limit_interval",
            0.0,
        )

        self.fallback_models = config.get(
            "fallback_models",
            [],
        )

        self._last_request_time = 0.0

        self._validate_config()

    # =========================================================
    # Provider contract
    # =========================================================

    @abstractmethod
    def _validate_config(self):
        pass

    @abstractmethod
    def _generate(
            self,
            prompt: str,
            context: Dict[str, Any],
    ) -> ProviderResponse:
        """
        Generate using the provider's default model.

        Provider implementations must implement this method.
        """
        pass

    def _call_model(
            self,
            prompt: str,
            context: Dict[str, Any],
            model: str,
    ) -> ProviderResponse:
        """
        Generate using a specific model.

        Providers that support model selection should override
        this method.

        Default behavior falls back to _generate().
        """

        return self._generate(
            prompt,
            context,
        )

    # =========================================================
    # Rate limiting
    # =========================================================

    def _rate_limit(self):

        if self.rate_limit_interval <= 0:
            return

        now = time.time()

        elapsed = (
                now -
                self._last_request_time
        )

        if elapsed < self.rate_limit_interval:

            sleep_time = (
                    self.rate_limit_interval -
                    elapsed
            )

            time.sleep(sleep_time)

        self._last_request_time = time.time()

    # =========================================================
    # Cache
    # =========================================================

    def _get_cache_key(
            self,
            prompt: str,
            context: Dict[str, Any],
    ) -> str:
        """
        Generate a deterministic cache key.

        Workspace/state objects are intentionally excluded.
        """

        safe_context = {}

        for key, value in context.items():

            if key in [
                "workspace",
                "state",
            ]:
                continue

            try:
                json.dumps(value)

                safe_context[key] = value

            except (
                    TypeError,
                    ValueError,
            ):
                continue

        data = {
            "provider": self.provider_name,
            "model": self.config.get(
                "model",
                "",
            ),
            "prompt": prompt,
            "context": safe_context,
        }

        key_str = json.dumps(
            data,
            sort_keys=True,
            default=str,
        )

        return hashlib.md5(
            key_str.encode()
        ).hexdigest()

    def _read_cache(
            self,
            cache_key: str,
    ) -> Optional[ProviderResponse]:

        if DISABLE_CACHE:
            return None

        cache_file = (
                CACHE_DIR /
                f"{cache_key}.json"
        )

        if not cache_file.exists():
            return None

        try:

            data = json.loads(
                cache_file.read_text()
            )

            response = ProviderResponse(
                content=data["content"],
                provider=data["provider"],
                model=data["model"],
                usage=data.get("usage"),
                duration_ms=data.get(
                    "duration_ms",
                    0.0,
                ),
                timestamp=(
                    datetime.fromisoformat(
                        data["timestamp"]
                    )
                    if data.get("timestamp")
                    else None
                ),
            )

            logger.debug(
                f"Cache hit for "
                f"{self.provider_name}"
            )

            return response

        except Exception as e:

            logger.warning(
                f"Cache read failed: {e}"
            )

            return None

    def _write_cache(
            self,
            cache_key: str,
            response: ProviderResponse,
    ):

        if DISABLE_CACHE:
            return

        try:

            cache_file = (
                    CACHE_DIR /
                    f"{cache_key}.json"
            )

            data = asdict(response)

            if data.get("timestamp"):
                data["timestamp"] = (
                    data["timestamp"]
                    .isoformat()
                )

            cache_file.write_text(
                json.dumps(
                    data,
                    indent=2,
                )
            )

            logger.debug(
                f"Cached response for "
                f"{self.provider_name}"
            )

        except Exception as e:

            logger.warning(
                f"Cache write failed: {e}"
            )

    # =========================================================
    # Main generation entry point
    # =========================================================

    def generate(
            self,
            prompt: str,
            context: Dict[str, Any],
    ) -> ProviderResponse:

        cache_key = self._get_cache_key(
            prompt,
            context,
        )

        cached = self._read_cache(
            cache_key
        )

        if cached:
            return cached

        # -----------------------------------------------------
        # IMPORTANT:
        #
        # Primary model MUST be tried first.
        #
        # Existing code used fallback_models as the complete
        # model list, which could cause the configured primary
        # model to be skipped.
        # -----------------------------------------------------

        primary_model = self.config.get(
            "model"
        )

        models_to_try = []

        if primary_model:
            models_to_try.append(
                primary_model
            )

        for model in self.fallback_models:

            if model and model not in models_to_try:
                models_to_try.append(model)

        if not models_to_try:

            models_to_try = [
                "default"
            ]

        last_error = None

        for model in models_to_try:

            try:

                self._rate_limit()

                start_time = time.time()

                response = self._call_model(
                    prompt,
                    context,
                    model,
                )

                response.duration_ms = (
                                               time.time() -
                                               start_time
                                       ) * 1000

                response.provider = (
                    f"{self.provider_name}:"
                    f"{model}"
                )

                response.model = model

                logger.info(
                    f"Provider "
                    f"{self.provider_name} "
                    f"success with model "
                    f"{model}"
                )

                self._write_cache(
                    cache_key,
                    response,
                )

                return response

            except ProviderError as e:

                last_error = e

                # -------------------------------------------------
                # IMPORTANT:
                #
                # Only retry/fallback when the provider explicitly
                # marks the error as retryable.
                #
                # Authentication errors, invalid requests, etc.
                # should not blindly cascade through every model.
                # -------------------------------------------------

                if not e.retryable:

                    logger.error(
                        f"Provider "
                        f"{self.provider_name} "
                        f"non-retryable error: "
                        f"{e}"
                    )

                    break

                logger.warning(
                    f"Model {model} failed: "
                    f"{e}. "
                    f"Trying next model."
                )

                continue

            except Exception as e:

                # -------------------------------------------------
                # Do NOT silently retry arbitrary programming errors.
                #
                # This is particularly important for bugs such as:
                #
                #   Can't instantiate abstract class ...
                #
                # Those are application/provider implementation
                # errors, not model availability failures.
                # -------------------------------------------------

                raise ProviderError(
                    error_type=(
                        ProviderErrorType.UNKNOWN
                    ),
                    message=(
                        f"Unexpected error "
                        f"on {model}: "
                        f"{str(e)}"
                    ),
                    provider=self.provider_name,
                    retryable=False,
                )

        if last_error:

            raise last_error

        raise ProviderError(
            error_type=(
                ProviderErrorType.UNKNOWN
            ),
            message=(
                "All configured models "
                "failed with no specific error"
            ),
            provider=self.provider_name,
            retryable=False,
        )

    # =========================================================
    # Generic HTTP error parser
    # =========================================================

    def _parse_error_response(
            self,
            status_code: int,
            response_data: Dict,
    ) -> ProviderError:

        error_type = (
            ProviderErrorType.UNKNOWN
        )

        message = "Unknown error"

        retryable = False

        if status_code == 429:

            error_type = (
                ProviderErrorType.RATE_LIMIT
            )

            message = (
                "Rate limit exceeded"
            )

            retryable = True

        elif status_code in [
            500,
            502,
            503,
            504,
        ]:

            error_type = (
                ProviderErrorType.SERVER_ERROR
            )

            message = "Server error"

            retryable = True

        elif status_code == 401:

            error_type = (
                ProviderErrorType.AUTHENTICATION
            )

            message = "Invalid API key"

            retryable = False

        elif status_code == 408:

            error_type = (
                ProviderErrorType.TIMEOUT
            )

            message = "Timeout"

            retryable = True

        elif status_code == 400:

            error_type = (
                ProviderErrorType.INVALID_REQUEST
            )

            message = "Invalid request"

            retryable = False

        return ProviderError(
            error_type=error_type,
            message=message,
            provider=self.provider_name,
            retryable=retryable,
            details={
                "status_code": status_code,
                "response": response_data,
            },
        )