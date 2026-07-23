"""LLM factory — SpaceXAI / xAI preferred; Gemini OpenAI-compat fallback."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from config.settings import get_settings

# Google Generative Language OpenAI-compatible endpoint
_GEMINI_OPENAI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai/"


@lru_cache
def get_chat_model() -> Any | None:
    """
    Return a LangChain chat model, or None if no API key (offline mode).

    Priority:
      1) SpaceXAI / xAI — base_url https://api.x.ai/v1 , env XAI_API_KEY
      2) Gemini — OpenAI-compat API, env GEMINI_API_KEY / GOOGLE_API_KEY
    """
    settings = get_settings()
    if not settings.llm_enabled:
        return None

    from langchain_openai import ChatOpenAI

    if settings.xai_api_key:
        return ChatOpenAI(
            model=settings.xai_model,
            api_key=settings.xai_api_key,
            base_url=settings.xai_base_url,
            temperature=settings.temperature,
        )

    if settings.gemini_api_key:
        return ChatOpenAI(
            model=settings.gemini_model,
            api_key=settings.gemini_api_key,
            base_url=_GEMINI_OPENAI_BASE,
            temperature=settings.temperature,
        )

    return None


def active_model_name() -> str | None:
    """Model id reported in agent results / health."""
    settings = get_settings()
    if settings.xai_api_key:
        return settings.xai_model
    if settings.gemini_api_key:
        return settings.gemini_model
    return None
