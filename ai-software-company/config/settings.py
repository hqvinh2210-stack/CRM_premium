"""Runtime settings loaded from environment / .env"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    # SpaceXAI / xAI (OpenAI-compatible) — agents optional
    xai_api_key: str | None
    xai_base_url: str
    xai_model: str

    # Google Gemini — Mem0 LLM + embeddings
    gemini_api_key: str | None
    gemini_model: str
    gemini_embed_model: str

    # When True and no key → deterministic offline agent replies
    allow_offline: bool
    # Skip LLM entirely (useful when key exists but no credits)
    force_offline: bool
    temperature: float

    # Memory / Mem0
    mem0_enabled: bool
    mem0_use_remote: bool
    mem0_provider: str  # gemini | xai
    mem0_data_dir: str
    memory_user_id: str
    memory_top_k: int

    @property
    def llm_enabled(self) -> bool:
        return bool(self.xai_api_key or self.gemini_api_key)

    @property
    def mem0_api_key(self) -> str | None:
        if self.mem0_provider == "gemini":
            return self.gemini_api_key
        return self.xai_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings(
        xai_api_key=os.getenv("XAI_API_KEY") or os.getenv("OPENAI_API_KEY"),
        xai_base_url=os.getenv("XAI_BASE_URL", "https://api.x.ai/v1"),
        xai_model=os.getenv("XAI_MODEL", "grok-4.5"),
        gemini_api_key=os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or os.getenv("GOOGLE_GENAI_API_KEY"),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite"),
        gemini_embed_model=os.getenv(
            "GEMINI_EMBED_MODEL", "models/gemini-embedding-001"
        ),
        allow_offline=os.getenv("ALLOW_OFFLINE_AGENTS", "1")
        not in {"0", "false", "False"},
        force_offline=os.getenv("AGENT_FORCE_OFFLINE", "0")
        not in {"0", "false", "False"},
        temperature=float(os.getenv("AGENT_TEMPERATURE", "0.2")),
        mem0_enabled=os.getenv("MEM0_ENABLED", "1") not in {"0", "false", "False"},
        mem0_use_remote=os.getenv("MEM0_USE_REMOTE", "0")
        not in {"0", "false", "False"},
        mem0_provider=os.getenv("MEM0_PROVIDER", "gemini").lower(),
        mem0_data_dir=os.getenv("MEM0_DATA_DIR", ".mem0"),
        memory_user_id=os.getenv("MEMORY_USER_ID", "crm_company"),
        memory_top_k=int(os.getenv("MEMORY_TOP_K", "5")),
    )
