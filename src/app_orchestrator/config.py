import os


def get_gemini_api_key() -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Configure it in your shell environment."
        )
    return api_key


def get_gemini_model() -> str:
    return os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
