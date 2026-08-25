import os


DEFAULT_GEMINI_MODEL = "gemini-3.6-flash"


def get_gemini_api_key() -> str:
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. "
            "Configure it in the shell environment."
        )

    return api_key


def get_gemini_model() -> str:
    return os.getenv(
        "GEMINI_MODEL",
        DEFAULT_GEMINI_MODEL,
    )


def get_agent_runtime_model() -> str:
    """
    Return the model used by the Agent Framework runtime.

    A dedicated setting allows runtime experiments without changing
    the legacy provider configuration.
    """
    return os.getenv(
        "AGENT_RUNTIME_MODEL",
        get_gemini_model(),
    )