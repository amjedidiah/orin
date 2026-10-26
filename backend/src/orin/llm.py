"""Shared clients for the model providers Orin calls."""

from functools import lru_cache

from openai import AsyncOpenAI

from orin.config import get_settings


class NotConfiguredError(RuntimeError):
    """Raised when a provider is used without its API key."""


@lru_cache
def get_meta_client() -> AsyncOpenAI:
    """One client for the Meta Model API, reused for every call."""
    settings = get_settings()
    if settings.model_api_key is None:
        raise NotConfiguredError("MODEL_API_KEY is not set")
    return AsyncOpenAI(
        base_url=settings.meta_api_base_url,
        api_key=settings.model_api_key.get_secret_value(),
    )
