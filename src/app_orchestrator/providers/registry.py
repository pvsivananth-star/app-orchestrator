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
    
    def load_config(self, config_path: Optional[Path] = None):
        """Load provider configuration from YAML file."""
        if config_path is None:
            config_path = Path(__file__).parent.parent / "models" / "mapping.yaml"
        
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    config = yaml.safe_load(f)
                self.provider_configs = config.get("providers", {})
                self.agent_mapping = config.get("agents", {})
                logger.info(f"Loaded config from {config_path}")
                return
            except Exception as e:
                logger.warning(f"Failed to load config: {e}. Using defaults.")
        # Fallback to defaults
        self._load_default_config()
    
    def _load_default_config(self):
        """Load default configuration if config file not found."""
        self.provider_configs = {
            "gemini": {
                "name": "gemini",
                "model": "gemini-3.6-flash",
                "timeout": 30,
                "max_retries": 5,
                "retry_delay": 1.0,
                "fallback_models": [
                    "gemini-3.5-flash-lite",
                    "gemini-3.1-flash-lite",
                    "gemini-3.6-flash",
                    "gemini-3.5-flash",
                ],
                "rate_limit_interval": 6.0,
                "env_vars": ["GEMINI_API_KEY"],
            },
            "deepseek": {
                "name": "deepseek",
                "model": "deepseek-chat",
                "timeout": 30,
                "max_retries": 5,
                "retry_delay": 1.0,
                "env_vars": ["DEEPSEEK_API_KEY"],
            },
            "groq": {
                "name": "groq",
                "model": "mixtral-8x7b-32768",
                "timeout": 30,
                "max_retries": 5,
                "retry_delay": 1.0,
                "env_vars": ["GROQ_API_KEY"],
            },
            "openrouter": {
                "name": "openrouter",
                "model": "openai/gpt-3.5-turbo",
                "timeout": 30,
                "max_retries": 5,
                "retry_delay": 1.0,
                "env_vars": ["OPENROUTER_API_KEY"],
            },
            "huggingface": {
                "name": "huggingface",
                "model": "meta-llama/Llama-2-70b-chat-hf",
                "timeout": 60,
                "max_retries": 5,
                "retry_delay": 2.0,
                "env_vars": ["HUGGINGFACE_API_KEY"],
            },
            "microsoft_groq": {
                "name": "microsoft_groq",
                "model": "mixtral-8x7b-32768",
                "timeout": 30,
                "max_retries": 5,
                "retry_delay": 1.0,
                "env_vars": ["GROQ_API_KEY"],
            },
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
        logger.info("Loaded default configuration")
    
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
        config = self.provider_configs[provider_name]
        provider = provider_map[provider_name](config)
        self.providers[provider_name] = provider
        return provider
    
    def get_agent_providers(self, agent_name: str) -> List[str]:
        return self.agent_mapping.get(agent_name, ["deepseek", "groq", "microsoft_groq", "FAIL"])
    
    def get_all_providers(self) -> List[str]:
        return list(self.provider_configs.keys())
    
    def is_provider_available(self, provider_name: str) -> bool:
        if provider_name not in self.provider_configs:
            return False
        config = self.provider_configs[provider_name]
        env_vars = config.get("env_vars", [])
        for var in env_vars:
            if not os.getenv(var):
                return False
        return True
