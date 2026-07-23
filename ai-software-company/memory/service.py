"""Company memory facade — shared brain for all agents.

Priority:
1. Always write/read **local** store (reliable, offline).
2. If Mem0 enabled + credits OK, also write/search Mem0 and merge results.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from config.settings import get_settings
from memory.local_store import LocalMemoryStore
from memory.mem0_store import build_mem0_client, mem0_add, mem0_search


@dataclass
class MemoryService:
    user_id: str
    local: LocalMemoryStore
    mem0: Any | None
    mem0_enabled: bool

    @property
    def backend(self) -> str:
        if self.mem0 is not None and self.mem0_enabled:
            return "hybrid"
        return "local"

    def remember(
        self,
        text: str,
        *,
        agent_id: str | None = None,
        run_id: str | None = None,
        issue_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        text = (text or "").strip()
        if not text:
            return {"ok": False, "reason": "empty"}

        meta = dict(metadata or {})
        if agent_id:
            meta.setdefault("agent_id", agent_id)
        if run_id:
            meta.setdefault("run_id", run_id)
        if issue_id:
            meta.setdefault("issue_id", issue_id)

        local_item = self.local.add(
            text,
            user_id=self.user_id,
            agent_id=agent_id,
            run_id=run_id,
            issue_id=issue_id,
            metadata=meta,
        )
        mem0_result = None
        mem0_error = None
        if self.mem0 is not None and self.mem0_enabled:
            try:
                mem0_result = mem0_add(
                    self.mem0, text, user_id=self.user_id, metadata=meta
                )
            except Exception as exc:  # credits / embedder / network
                mem0_error = str(exc)

        return {
            "ok": True,
            "local_id": local_item.id,
            "backend": self.backend,
            "mem0": mem0_result,
            "mem0_error": mem0_error,
        }

    def recall(
        self,
        query: str,
        *,
        top_k: int = 5,
        agent_id: str | None = None,
    ) -> list[dict[str, Any]]:
        local_hits = self.local.search(
            query, user_id=self.user_id, top_k=top_k, agent_id=agent_id
        )
        hits = list(local_hits)

        if self.mem0 is not None and self.mem0_enabled:
            try:
                remote = mem0_search(
                    self.mem0, query, user_id=self.user_id, top_k=top_k
                )
                # de-dupe by memory text
                seen = {h["memory"] for h in hits}
                for h in remote:
                    if h.get("memory") and h["memory"] not in seen:
                        hits.append(h)
                        seen.add(h["memory"])
            except Exception:
                pass

        return hits[:top_k]

    def format_context(self, hits: list[dict[str, Any]]) -> str:
        if not hits:
            return ""
        lines = ["## Shared company memory (from previous runs / agents)"]
        for i, h in enumerate(hits, 1):
            agent = h.get("agent_id") or h.get("metadata", {}).get("agent_id") or "?"
            src = h.get("source", "?")
            lines.append(f"{i}. [{agent}/{src}] {h.get('memory', '')}")
        lines.append(
            "Use these memories when relevant so agents stay consistent with past decisions."
        )
        return "\n".join(lines)

    def remember_pipeline(
        self,
        *,
        task: str,
        plan: str,
        code: str,
        review: str,
        run_id: str | None = None,
        issue_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Persist handoff facts so the next issue/run can recall them."""
        facts = [
            (
                "planner",
                f"Plan for task: {task[:200]}\n{plan[:800]}",
            ),
            (
                "coder",
                f"Code approach for task: {task[:200]}\n{code[:800]}",
            ),
            (
                "reviewer",
                f"Review for task: {task[:200]}\n{review[:800]}",
            ),
            (
                "company",
                f"Completed pipeline for: {task[:300]}. Status: reviewed.",
            ),
        ]
        results = []
        for agent_id, text in facts:
            results.append(
                self.remember(
                    text,
                    agent_id=agent_id,
                    run_id=run_id,
                    issue_id=issue_id,
                    metadata={"kind": "pipeline", "task": task[:200]},
                )
            )
        return results

    def list_all(self) -> list[dict[str, Any]]:
        return [i.to_dict() for i in self.local.get_all(user_id=self.user_id)]

    def clear(self) -> int:
        return self.local.clear(user_id=self.user_id)


@lru_cache
def get_memory_service() -> MemoryService:
    settings = get_settings()
    root = Path(__file__).resolve().parent.parent
    data_dir = root / settings.mem0_data_dir
    local_path = data_dir / "local_memories.jsonl"

    # Mem0 remote: Gemini (recommended) or xAI — needs valid API key.
    use_remote = (
        settings.mem0_enabled
        and settings.mem0_use_remote
        and bool(settings.mem0_api_key)
    )
    mem0_client = None
    if use_remote:
        try:
            provider = settings.mem0_provider
            if provider == "gemini":
                mem0_client = build_mem0_client(
                    provider="gemini",
                    api_key=settings.mem0_api_key or "",
                    data_dir=data_dir,
                    llm_model=settings.gemini_model,
                    embed_model=settings.gemini_embed_model,
                )
            else:
                mem0_client = build_mem0_client(
                    provider="xai",
                    api_key=settings.mem0_api_key or "",
                    data_dir=data_dir,
                    llm_model=settings.xai_model,
                    base_url=settings.xai_base_url,
                )
            print(f"[memory] Mem0 remote ready provider={provider}")
        except Exception as exc:
            print(f"[memory] Mem0 init failed, local-only: {exc}")

    return MemoryService(
        user_id=settings.memory_user_id,
        local=LocalMemoryStore(local_path),
        mem0=mem0_client,
        mem0_enabled=bool(mem0_client),
    )


def reset_memory_service() -> None:
    get_memory_service.cache_clear()
