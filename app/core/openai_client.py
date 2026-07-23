from functools import lru_cache

from openai import AsyncOpenAI

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_openai_client() -> AsyncOpenAI:
    """Create and cache the asynchronous OpenAI client."""

    settings = get_settings()

    if not settings.has_openai_key():
        raise RuntimeError(
            "OPENAI_API_KEY is missing. "
            "Copy .env.example to .env and add a valid key."
        )

    return AsyncOpenAI(
        api_key=settings.openai_api_key.get_secret_value(),
        timeout=settings.openai_timeout_seconds,
        max_retries=settings.openai_max_retries,
    )