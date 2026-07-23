"""Optional Mem0 backend — Gemini (default) or xAI OpenAI-compatible."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def build_mem0_client(
    *,
    provider: str,
    api_key: str,
    data_dir: Path,
    llm_model: str | None = None,
    embed_model: str | None = None,
    base_url: str | None = None,
) -> Any:
    """
    Create Mem0 Memory client.

    provider:
      - "gemini" → Google Gemini LLM + Gemini embeddings
      - "xai" / "openai" → OpenAI-compatible (SpaceXAI / xAI)
    """
    from mem0 import Memory

    data_dir.mkdir(parents=True, exist_ok=True)
    provider = (provider or "gemini").lower()

    if provider == "gemini":
        config = {
            "llm": {
                "provider": "gemini",
                "config": {
                    "model": llm_model or "gemini-2.5-flash-lite",
                    "api_key": api_key,
                    "temperature": 0.1,
                },
            },
            "embedder": {
                "provider": "gemini",
                "config": {
                    "model": embed_model or "models/gemini-embedding-001",
                    "api_key": api_key,
                    "embedding_dims": 768,
                },
            },
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "collection_name": "crm_memory_gemini",
                    "path": str(data_dir / "qdrant_gemini"),
                    "on_disk": True,
                    "embedding_model_dims": 768,
                },
            },
            "history_db_path": str(data_dir / "history_gemini.db"),
            "version": "v1.1",
        }
    else:
        # xAI / OpenAI-compatible
        config = {
            "llm": {
                "provider": "openai",
                "config": {
                    "model": llm_model or "grok-4.5",
                    "api_key": api_key,
                    "openai_base_url": base_url or "https://api.x.ai/v1",
                    "temperature": 0.1,
                },
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    "model": embed_model or "text-embedding-3-small",
                    "api_key": api_key,
                    "openai_base_url": base_url or "https://api.x.ai/v1",
                },
            },
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "collection_name": "crm_memory",
                    "path": str(data_dir / "qdrant"),
                    "on_disk": True,
                },
            },
            "history_db_path": str(data_dir / "history.db"),
            "version": "v1.1",
        }

    return Memory.from_config(config)


def mem0_add(client: Any, text: str, *, user_id: str, metadata: dict | None = None) -> Any:
    return client.add(text, user_id=user_id, metadata=metadata or {})


def mem0_search(client: Any, query: str, *, user_id: str, top_k: int = 5) -> list[dict]:
    raw = client.search(query, user_id=user_id, limit=top_k)
    if isinstance(raw, dict):
        rows = raw.get("results") or raw.get("memories") or []
    else:
        rows = raw or []
    out = []
    for row in rows:
        if isinstance(row, dict):
            mem = row.get("memory") or row.get("text") or str(row)
            out.append(
                {
                    "id": row.get("id"),
                    "memory": mem,
                    "score": row.get("score"),
                    "metadata": row.get("metadata") or {},
                    "source": "mem0",
                }
            )
        else:
            out.append({"memory": str(row), "source": "mem0"})
    return out
