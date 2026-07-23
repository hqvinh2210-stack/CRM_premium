"""Base agent: role + LLM (or offline) execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agents.llm import active_model_name, get_chat_model
from agents.roles import AgentRole
from config.settings import get_settings


@dataclass
class AgentResult:
    role_id: str
    agent_name: str
    content: str
    mode: str  # "llm" | "offline" | "llm_fallback"
    model: str | None = None


class BaseAgent:
    def __init__(self, role: AgentRole):
        self.role = role

    def run(self, user_message: str) -> AgentResult:
        settings = get_settings()
        llm = None if settings.force_offline else get_chat_model()

        if llm is not None:
            model = active_model_name()
            try:
                content = self._run_llm(llm, user_message)
                return AgentResult(
                    role_id=self.role.id,
                    agent_name=self.role.name,
                    content=content,
                    mode="llm",
                    model=model,
                )
            except Exception as exc:
                # No credits / network / model errors → offline fallback
                print(
                    f"[{self.role.id}] LLM failed ({type(exc).__name__}: {exc}); "
                    "falling back to offline role output"
                )
                if not settings.allow_offline:
                    raise
                content = self._run_offline(user_message)
                return AgentResult(
                    role_id=self.role.id,
                    agent_name=self.role.name,
                    content=content,
                    mode="llm_fallback",
                    model=model,
                )

        if not settings.allow_offline:
            raise RuntimeError(
                "No XAI_API_KEY set and ALLOW_OFFLINE_AGENTS=0. "
                "Add XAI_API_KEY to .env to enable LLM agents."
            )

        content = self._run_offline(user_message)
        return AgentResult(
            role_id=self.role.id,
            agent_name=self.role.name,
            content=content,
            mode="offline",
            model=None,
        )

    def _run_llm(self, llm: Any, user_message: str) -> str:
        from langchain_core.messages import HumanMessage, SystemMessage

        messages = [
            SystemMessage(content=self.role.system_prompt),
            HumanMessage(content=user_message),
        ]
        response = llm.invoke(messages)
        text = getattr(response, "content", None) or str(response)
        if isinstance(text, list):
            parts = []
            for block in text:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict) and "text" in block:
                    parts.append(block["text"])
                else:
                    parts.append(str(block))
            text = "".join(parts)
        return text.strip()

    def _run_offline(self, user_message: str) -> str:
        """Deterministic stub when no API key — still role-shaped."""
        raise NotImplementedError
