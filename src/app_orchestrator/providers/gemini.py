from google import genai

from app_orchestrator.config import get_gemini_api_key, get_gemini_model


def create_gemini_client() -> genai.Client:
    return genai.Client(api_key=get_gemini_api_key())


def get_gemini_model_name() -> str:
    return get_gemini_model()
