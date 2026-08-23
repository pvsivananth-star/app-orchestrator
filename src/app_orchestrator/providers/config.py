# src/app_orchestrator/configuration/config.py
import os

API_KEYS = {
    "deepseek": os.getenv("DEEPSEEK_API_KEY"),
    "groq": os.getenv("GROQ_API_KEY"),
    "huggingface": os.getenv("HUGGINGFACE_API_KEY"),
    "openrouter": os.getenv("OPENROUTER_API_KEY"),
    "gemini": os.getenv("GEMINI_API_KEY"),
}

def get_api_key(provider: str) -> str:
    key = API_KEYS.get(provider)
    if not key:
        raise RuntimeError(f"Missing API key for {provider}")
    return key
