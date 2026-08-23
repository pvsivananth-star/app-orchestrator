
import os
from typing import Dict, Any
import requests
from .base import BaseProvider, ProviderResponse, ProviderError, ProviderErrorType

class HuggingFaceProvider(BaseProvider):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = os.getenv("HUGGINGFACE_API_KEY")
        if not self.api_key:
            raise ValueError("HUGGINGFACE_API_KEY not found in environment")
        self.model_name = config.get("model", "meta-llama/Llama-2-70b-chat-hf")
        self.api_url = f"https://api-inference.huggingface.co/models/{self.model_name}"
        self.headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
    
    def _validate_config(self):
        if "name" not in self.config:
            raise ValueError("Missing config key: name")
    
    def _generate(self, prompt: str, context: Dict[str, Any]) -> ProviderResponse:
        try:
            payload = {
                "inputs": prompt,
                "parameters": {
                    "temperature": context.get("temperature", 0.7),
                    "max_new_tokens": context.get("max_tokens", 2048),
                    "top_p": context.get("top_p", 0.95),
                    "do_sample": True,
                    "return_full_text": False,
                }
            }
            if "system_instruction" in context:
                payload["inputs"] = f"{context[system_instruction]}\n\n{prompt}"
            response = requests.post(self.api_url, headers=self.headers, json=payload, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    content = data[0].get("generated_text", "")
                else:
                    content = data.get("generated_text", "")
                return ProviderResponse(content=content, provider=self.provider_name, model=self.model_name)
            if response.status_code == 503:
                raise ProviderError(ProviderErrorType.SERVER_ERROR, "Model loading", self.provider_name, True)
            raise self._parse_error_response(response.status_code, response.json() if response.text else {})
        except requests.Timeout:
            raise ProviderError(ProviderErrorType.TIMEOUT, "Timeout", self.provider_name, True)
        except requests.ConnectionError:
            raise ProviderError(ProviderErrorType.CONNECTION, "Connection error", self.provider_name, True)
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError(ProviderErrorType.UNKNOWN, str(e), self.provider_name, True)

