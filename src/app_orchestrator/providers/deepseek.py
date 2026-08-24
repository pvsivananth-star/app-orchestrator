
import os
from typing import Dict, Any
import requests
from .base import BaseProvider, ProviderResponse, ProviderError, ProviderErrorType

class DeepSeekProvider(BaseProvider):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY not found in environment")
        self.model_name = config.get("model", "deepseek-chat")
        self.api_url = "https://api.deepseek.com/v1/chat/completions"
        self.headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
    
    def _validate_config(self):
        if "name" not in self.config:
            raise ValueError("Missing config key: name")
    
    def _generate(self, prompt: str, context: Dict[str, Any]) -> ProviderResponse:
        try:
            messages = []
            if "system_instruction" in context:
                messages.append({"role": "system", "content": context["system_instruction"]})
            messages.append({"role": "user", "content": prompt})
            payload = {
                "model": self.model_name,
                "messages": messages,
                "temperature": context.get("temperature", 0.7),
                "max_tokens": context.get("max_tokens", 8192),
                "top_p": context.get("top_p", 0.95),
                "stream": False,
            }
            response = requests.post(self.api_url, headers=self.headers, json=payload, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                return ProviderResponse(
                    content=data["choices"][0]["message"]["content"],
                    provider=self.provider_name,
                    model=self.model_name,
                    usage=data.get("usage", {})
                )
            raise self._parse_error_response(response.status_code, response.json() if response.text else {})
        except requests.Timeout:
            raise ProviderError(ProviderErrorType.TIMEOUT, "Timeout", self.provider_name, True)
        except requests.ConnectionError:
            raise ProviderError(ProviderErrorType.CONNECTION, "Connection error", self.provider_name, True)
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError(ProviderErrorType.UNKNOWN, str(e), self.provider_name, True)


    def _call_model(self, prompt: str, context: Dict[str, Any], model: str) -> ProviderResponse:
        """Delegate to _generate (ignores model)."""
        return self._generate(prompt, context)
