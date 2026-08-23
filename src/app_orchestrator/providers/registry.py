
from typing import Dict, List, Optional, Any
import logging
import yaml
from pathlib import Path
from .base import BaseProvider
from .gemini import GeminiProvider
from .deepseek import DeepSeekProvider
from .groq import GroqProvider
from .openrouter import OpenRouterProvider
from .huggingface import HuggingFaceProvider
from .microsoft_groq import MicrosoftGroqProvider

logger = logging.getLogger(__name__)

class ProviderRegistry:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, "initialized"):
            self.providers: Dict[str, BaseProvider] = {}
            self.provider_configs: Dict[str, Dict] = {}
            self.agent_mapping: Dict[str, List[str]] = {}
            self.initialized = True
            self._load_default_config()
    
    def _load_default_config(self):
        self.provider_configs = {
            "gemini": {"name": "gemini", "model": "gemini-2.0-flash-exp", "timeout": 30, "max_retries": 5, "retry_delay": 1.0},
            "deepseek": {"name": "deepseek", "model": "deepseek-chat", "timeout": 30, "max_retries": 5, "retry_delay": 1.0},
            "groq": {"name": "groq", "model": "mixtral-8x7b-32768", "timeout": 30, "max_retries": 5, "retry_delay": 1.0},
            "openrouter": {"name": "openrouter", "model": "openai/gpt-3.5-turbo", "timeout": 30, "max_retries": 5, "retry_delay": 1.0},
            "huggingface": {"name": "huggingface", "model": "meta-llama/Llama-2-70b-chat-hf", "timeout": 60, "max_retries": 5, "retry_delay": 2.0},
            "microsoft_groq": {"name": "microsoft_groq", "model": "mixtral-8x7b-32768", "timeout": 30, "max_retries": 5, "retry_delay": 1.0},
        }
        self.agent_mapping = {
            "interaction": ["deepseek", "groq", "openrouter", "microsoft_groq", "FAIL"],
            "requirement_enhancer": ["deepseek", "groq", "openrouter", "microsoft_groq", "FAIL"],
            "business_analyst": ["deepseek", "groq", "openrouter", "microsoft_groq", "FAIL"],
            "repo_analyst": ["gemini", "deepseek", "groq", "microsoft_groq", "FAIL"],
            "dependency": ["huggingface", "deepseek", "groq", "microsoft_groq", "FAIL"],
            "implementation": ["deepseek", "groq", "openrouter", "microsoft_groq", "FAIL"],
            "verification": ["groq", "deepseek", "openrouter", "microsoft_groq", "FAIL"],
            "security": ["deepseek", "groq", "openrouter", "microsoft_groq", "FAIL"],
            "lint": ["groq", "deepseek", "openrouter", "microsoft_groq", "FAIL"],
            "test": ["deepseek", "groq", "openrouter", "microsoft_groq", "FAIL"],
            "doc": ["gemini", "deepseek", "groq", "microsoft_groq", "FAIL"],
            "commit": ["openrouter", "deepseek", "groq", "microsoft_groq", "FAIL"],
        }
    
    def get_provider(self, provider_name: str) -> BaseProvider:
        if provider_name in self.providers:
            return self.providers[provider_name]
        if provider_name not in self.provider_configs:
            raise ValueError(f"Unknown provider: {provider_name}")
        provider_map = {
            "gemini": GeminiProvider,
            "deepseek": DeepSeekProvider,
            "groq": GroqProvider,
            "openrouter": OpenRouterProvider,
            "huggingface": HuggingFaceProvider,
            "microsoft_groq": MicrosoftGroqProvider,
        }
        provider = provider_map[provider_name](self.provider_configs[provider_name])
        self.providers[provider_name] = provider
        return provider
    
    def get_agent_providers(self, agent_name: str) -> List[str]:
        return self.agent_mapping.get(agent_name, ["deepseek", "groq", "microsoft_groq", "FAIL"])

