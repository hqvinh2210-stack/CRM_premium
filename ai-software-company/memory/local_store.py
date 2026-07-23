"""Local file memory — works offline, no API credits needed."""

from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class MemoryItem:
    id: str
    memory: str
    user_id: str
    agent_id: str | None = None
    run_id: str | None = None
    issue_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LocalMemoryStore:
    """JSONL memory with simple keyword ranking (shared across agents)."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    def _read_all(self) -> list[MemoryItem]:
        items: list[MemoryItem] = []
        text = self.path.read_text(encoding="utf-8").strip()
        if not text:
            return items
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
                items.append(
                    MemoryItem(
                        id=raw["id"],
                        memory=raw["memory"],
                        user_id=raw.get("user_id", "default"),
                        agent_id=raw.get("agent_id"),
                        run_id=raw.get("run_id"),
                        issue_id=raw.get("issue_id"),
                        metadata=raw.get("metadata") or {},
                        created_at=float(raw.get("created_at", time.time())),
                    )
                )
            except (json.JSONDecodeError, KeyError):
                continue
        return items

    def _append(self, item: MemoryItem) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(item.to_dict(), ensure_ascii=False) + "\n")

    def add(
        self,
        text: str,
        *,
        user_id: str,
        agent_id: str | None = None,
        run_id: str | None = None,
        issue_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryItem:
        item = MemoryItem(
            id=str(uuid.uuid4()),
            memory=text.strip(),
            user_id=user_id,
            agent_id=agent_id,
            run_id=run_id,
            issue_id=issue_id,
            metadata=metadata or {},
        )
        self._append(item)
        return item

    def get_all(self, *, user_id: str) -> list[MemoryItem]:
        return [i for i in self._read_all() if i.user_id == user_id]

    def search(
        self,
        query: str,
        *,
        user_id: str,
        top_k: int = 5,
        agent_id: str | None = None,
    ) -> list[dict[str, Any]]:
        tokens = set(re.findall(r"[a-zA-Z0-9_]+", query.lower()))
        scored: list[tuple[float, MemoryItem]] = []
        for item in self.get_all(user_id=user_id):
            if agent_id and item.agent_id and item.agent_id != agent_id:
                # still allow company-wide memories without agent_id
                pass
            text_l = item.memory.lower()
            score = 0.0
            if not tokens:
                score = item.created_at / 1e12
            else:
                hits = sum(1 for t in tokens if t in text_l)
                score = hits / max(len(tokens), 1)
                # recency boost
                score += min(item.created_at / 1e15, 0.1)
            if score > 0:
                scored.append((score, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, item in scored[:top_k]:
            results.append(
                {
                    "id": item.id,
                    "memory": item.memory,
                    "score": round(score, 4),
                    "agent_id": item.agent_id,
                    "run_id": item.run_id,
                    "issue_id": item.issue_id,
                    "metadata": item.metadata,
                    "created_at": item.created_at,
                    "source": "local",
                }
            )
        return results

    def clear(self, *, user_id: str | None = None) -> int:
        items = self._read_all()
        if user_id is None:
            self.path.write_text("", encoding="utf-8")
            return len(items)
        kept = [i for i in items if i.user_id != user_id]
        removed = len(items) - len(kept)
        with self.path.open("w", encoding="utf-8") as f:
            for i in kept:
                f.write(json.dumps(i.to_dict(), ensure_ascii=False) + "\n")
        return removed
