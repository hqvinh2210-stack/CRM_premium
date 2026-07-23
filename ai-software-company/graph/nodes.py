"""LangGraph nodes — agents + shared company memory."""

from __future__ import annotations

import uuid

from agents.coder import coder_agent
from agents.planner import planner_agent
from agents.reviewer import reviewer_agent
from config.settings import get_settings
from graph.state import ProjectState
from memory.service import get_memory_service


def _merge_modes(state: ProjectState, role_id: str, mode: str) -> dict:
    modes = dict(state.get("agent_modes") or {})
    modes[role_id] = mode
    return modes


def _ensure_run_id(state: ProjectState) -> str:
    return state.get("run_id") or str(uuid.uuid4())


def memory_node(state: ProjectState) -> dict:
    """Recall shared memories before the agent pipeline starts."""
    task = state.get("task", "")
    settings = get_settings()
    mem = get_memory_service()
    hits = mem.recall(task, top_k=settings.memory_top_k)
    context = mem.format_context(hits)
    run_id = _ensure_run_id(state)
    print(f"[memory] backend={mem.backend} hits={len(hits)} run_id={run_id[:8]}")
    return {
        "run_id": run_id,
        "memory_hits": hits,
        "memory_context": context,
        "logs": [f"memory ({mem.backend}): recalled {len(hits)} items"],
    }


def planner_node(state: ProjectState) -> dict:
    task = state.get("task", "")
    memory_context = state.get("memory_context", "")
    run_id = _ensure_run_id(state)
    result = planner_agent.plan(task, memory_context=memory_context)
    print(f"[planner:{result.agent_name}] mode={result.mode} task={task[:80]!r}")

    mem = get_memory_service()
    mem.remember(
        f"[Ava/planner] For '{task[:120]}': {result.content[:500]}",
        agent_id="planner",
        run_id=run_id,
        issue_id=state.get("issue_id"),
        metadata={"kind": "plan_snippet"},
    )

    return {
        "plan": result.content,
        "status": "planned",
        "run_id": run_id,
        "agent_modes": _merge_modes(state, "planner", result.mode),
        "logs": [f"planner ({result.agent_name}/{result.mode}): planned task"],
    }


def coding_node(state: ProjectState) -> dict:
    task = state.get("task", "")
    plan = state.get("plan", "")
    memory_context = state.get("memory_context", "")
    run_id = _ensure_run_id(state)
    result = coder_agent.code(task=task, plan=plan, memory_context=memory_context)
    print(f"[coder:{result.agent_name}] mode={result.mode}")

    mem = get_memory_service()
    mem.remember(
        f"[Rex/coder] Implemented '{task[:120]}' with plan length={len(plan)}",
        agent_id="coder",
        run_id=run_id,
        issue_id=state.get("issue_id"),
        metadata={"kind": "code_note"},
    )

    return {
        "code": result.content,
        "status": "coded",
        "run_id": run_id,
        "agent_modes": _merge_modes(state, "coder", result.mode),
        "logs": [f"coder ({result.agent_name}/{result.mode}): implemented task"],
    }


def review_node(state: ProjectState) -> dict:
    task = state.get("task", "")
    plan = state.get("plan", "")
    code = state.get("code", "")
    memory_context = state.get("memory_context", "")
    run_id = _ensure_run_id(state)
    result = reviewer_agent.review(
        task=task, plan=plan, code=code, memory_context=memory_context
    )
    print(f"[reviewer:{result.agent_name}] mode={result.mode}")

    mem = get_memory_service()
    mem.remember(
        f"[Kai/reviewer] {result.content[:600]}",
        agent_id="reviewer",
        run_id=run_id,
        issue_id=state.get("issue_id"),
        metadata={"kind": "review"},
    )
    # full pipeline snapshot for future runs
    mem.remember_pipeline(
        task=task,
        plan=plan,
        code=code,
        review=result.content,
        run_id=run_id,
        issue_id=state.get("issue_id"),
    )

    return {
        "review": result.content,
        "status": "reviewed",
        "run_id": run_id,
        "agent_modes": _merge_modes(state, "reviewer", result.mode),
        "logs": [f"reviewer ({result.agent_name}/{result.mode}): finished review"],
    }
