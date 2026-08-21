"""
LLM factory — returns the correct provider based on configuration.
"""
from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

import structlog
from langchain_core.language_models import BaseChatModel

from app.core.config import settings
from app.llm.provider import (
    AnthropicProvider,
    GeminiProvider,
    LLMProvider,
    OllamaProvider,
    OpenAIProvider,
)

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)

_PROVIDERS: dict[str, type[LLMProvider]] = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
    "ollama": OllamaProvider,
}


@lru_cache(maxsize=1)
def get_provider() -> LLMProvider:
    """Return the configured LLM provider instance (cached)."""
    provider_cls = _PROVIDERS.get(settings.LLM_PROVIDER)
    if not provider_cls:
        raise ValueError(
            f"Unknown LLM_PROVIDER: {settings.LLM_PROVIDER!r}. "
            f"Supported: {list(_PROVIDERS)}"
        )
    provider = provider_cls()
    logger.info(
        "LLM provider initialized",
        provider=settings.LLM_PROVIDER,
        model=settings.LLM_MODEL,
        fast_model=settings.LLM_FAST_MODEL,
    )
    return provider


def _with_usage_tracking(model: BaseChatModel) -> BaseChatModel:
    """
    Attach the token-accounting callback so every call is metered.

    Set on the model itself rather than via with_config(): agents call
    .with_structured_output(), which rebuilds the runnable and would drop a
    config-level callback — and those are the calls that burn the tokens.
    """
    from app.llm.usage import TokenUsageCallback

    try:
        existing = list(model.callbacks or [])  # type: ignore[union-attr]
    except (AttributeError, TypeError):
        existing = []

    if any(isinstance(cb, TokenUsageCallback) for cb in existing):
        return model

    try:
        model.callbacks = [*existing, TokenUsageCallback()]  # type: ignore[union-attr]
        return model
    except (AttributeError, ValueError):
        # Model does not accept callbacks; fall back to config-level.
        return model.with_config(callbacks=[TokenUsageCallback()])


def get_primary_llm() -> BaseChatModel:
    """Return the primary (capable) LLM for complex reasoning tasks."""
    return _with_usage_tracking(get_provider().get_primary_model())


def get_fast_llm() -> BaseChatModel:
    """Return the fast LLM for classification and routing tasks."""
    return _with_usage_tracking(get_provider().get_fast_model())


def get_provider_name() -> str:
    """Return the active provider name string."""
    return get_provider().get_provider_name()
