import requests
import logging
from .base import BaseProvider, ProviderResponse, ProviderError, ProviderErrorType

logger = logging.getLogger(__name__)

class OllamaProvider(BaseProvider):
    def __init__(self, config):
        super().__init__(config)
        self.model = config.get("model", "deepseek-coder:1.3b")
        self.api_url = "http://localhost:11434/api/generate"
        self.timeout = config.get("timeout", 120)

    def _validate_config(self):
        if "name" not in self.config:
            raise ValueError("Missing config key: name")

    def _generate(self, prompt: str, context: dict):
        try:
            # Check if Ollama is running
            try:
                requests.get("http://localhost:11434", timeout=2)
            except requests.ConnectionError:
                raise ProviderError(
                    ProviderErrorType.CONNECTION,
                    "Ollama not running. Start with: ollama serve",
                    "ollama",
                    retryable=False
                )

            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": context.get("temperature", 0.2),
                    "num_predict": context.get("max_tokens", 4096),
                    "top_p": context.get("top_p", 0.95),
                }
            }

            response = requests.post(
                self.api_url,
                json=payload,
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                content = data.get("response", "")
                if not content.strip():
                    raise ProviderError(
                        ProviderErrorType.UNKNOWN,
                        "Empty response from Ollama",
                        "ollama",
                        retryable=True
                    )
                return ProviderResponse(
                    content=content,
                    provider="ollama",
                    model=self.model,
                    usage={"total_tokens": data.get("eval_count", 0)}
                )
            else:
                error_data = response.json() if response.text else {}
                raise self._parse_error_response(response.status_code, error_data)

        except requests.Timeout:
            raise ProviderError(
                ProviderErrorType.TIMEOUT,
                f"Ollama timeout after {self.timeout}s",
                "ollama",
                retryable=True
            )
        except requests.ConnectionError:
            raise ProviderError(
                ProviderErrorType.CONNECTION,
                "Ollama not reachable. Run: ollama serve",
                "ollama",
                retryable=False
            )
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError(
                ProviderErrorType.UNKNOWN,
                str(e),
                "ollama",
                retryable=True
            )
