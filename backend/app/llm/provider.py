"""
LLM provider abstraction.
All LLM interactions go through this module.
The provider is selected via LLM_PROVIDER environment variable.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import structlog
from langchain_core.language_models import BaseChatModel

from app.core.config import settings

logger = structlog.get_logger(__name__)


class LLMProvider(ABC):
    """Abstract base for LLM providers."""

    @abstractmethod
    def get_primary_model(self) -> BaseChatModel:
        """Return the primary (more capable) model for complex reasoning."""

    @abstractmethod
    def get_fast_model(self) -> BaseChatModel:
        """Return the fast (cheaper) model for classification and routing."""

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the provider name string."""


class OpenAIProvider(LLMProvider):
    """OpenAI / OpenAI-compatible API provider."""

    def get_primary_model(self) -> BaseChatModel:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.LLM_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
            timeout=settings.LLM_TIMEOUT_SECONDS,
            api_key=settings.OPENAI_API_KEY or None,
            base_url=settings.OPENAI_BASE_URL or None,
        )

    def get_fast_model(self) -> BaseChatModel:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.LLM_FAST_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=2048,
            timeout=60,
            api_key=settings.OPENAI_API_KEY or None,
            base_url=settings.OPENAI_BASE_URL or None,
        )

    def get_provider_name(self) -> str:
        return "openai"


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""

    def get_primary_model(self) -> BaseChatModel:
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model_name=settings.LLM_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
            timeout=settings.LLM_TIMEOUT_SECONDS,
            api_key=settings.ANTHROPIC_API_KEY or None,
        )

    def get_fast_model(self) -> BaseChatModel:
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model_name=settings.LLM_FAST_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=2048,
            timeout=60,
            api_key=settings.ANTHROPIC_API_KEY or None,
        )

    def get_provider_name(self) -> str:
        return "anthropic"


class GeminiProvider(LLMProvider):
    """Google Gemini provider."""

    def get_primary_model(self) -> BaseChatModel:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=settings.LLM_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            max_output_tokens=settings.LLM_MAX_TOKENS,
            timeout=settings.LLM_TIMEOUT_SECONDS,
            google_api_key=settings.GEMINI_API_KEY or None,
        )

    def get_fast_model(self) -> BaseChatModel:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=settings.LLM_FAST_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            max_output_tokens=2048,
            timeout=60,
            google_api_key=settings.GEMINI_API_KEY or None,
        )

    def get_provider_name(self) -> str:
        return "gemini"


class OllamaProvider(LLMProvider):
    """Local Ollama provider."""

    def get_primary_model(self) -> BaseChatModel:
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=settings.LLM_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            base_url=settings.OLLAMA_BASE_URL,
            num_predict=settings.LLM_MAX_TOKENS,
        )

    def get_fast_model(self) -> BaseChatModel:
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=settings.LLM_FAST_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            base_url=settings.OLLAMA_BASE_URL,
            num_predict=2048,
        )

    def get_provider_name(self) -> str:
        return "ollama"
