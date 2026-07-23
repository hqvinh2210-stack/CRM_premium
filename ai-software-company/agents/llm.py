"""LLM factory — SpaceXAI / xAI via OpenAI-compatible API."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from config.settings import get_settings


@lru_cache
def get_chat_model() -> Any | None:
    """
    Return a LangChain chat model, or None if no API key (offline mode).

    SpaceXAI / xAI: base_url https://api.x.ai/v1 , env XAI_API_KEY
    """
    settings = get_settings()
    if not settings.llm_enabled:
        return None

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.xai_model,
        api_key=settings.xai_api_key,
        base_url=settings.xai_base_url,
        temperature=settings.temperature,
    )
