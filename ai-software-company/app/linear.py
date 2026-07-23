"""Linear webhook → LangGraph bridge (+ shared memory)."""

from __future__ import annotations

from typing import Any

from graph.graph import graph


def extract_task(payload: dict[str, Any]) -> str | None:
    data = payload.get("data") or {}
    title = (data.get("title") or "").strip()
    if not title:
        return None

    identifier = (data.get("identifier") or "").strip()
    description = (data.get("description") or "").strip()

    parts = []
    if identifier:
        parts.append(f"[{identifier}] {title}")
    else:
        parts.append(title)

    if description:
        desc = description[:1500]
        parts.append(f"\n\nDescription:\n{desc}")

    return "".join(parts)


def is_issue_create(payload: dict[str, Any]) -> bool:
    event_type = (payload.get("type") or "").lower()
    action = (payload.get("action") or "").lower()
    return event_type == "issue" and action == "create"


def run_graph_for_task(task: str, issue_id: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"task": task, "logs": []}
    if issue_id:
        payload["issue_id"] = str(issue_id)
    result = graph.invoke(payload)
    return {
        "task": result.get("task", task),
        "plan": result.get("plan", ""),
        "code": result.get("code", ""),
        "review": result.get("review", ""),
        "status": result.get("status", ""),
        "logs": result.get("logs", []),
        "agent_modes": result.get("agent_modes") or {},
        "run_id": result.get("run_id"),
        "memory_hits": result.get("memory_hits") or [],
        "memory_context": result.get("memory_context") or "",
    }


def handle_linear_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    event_type = payload.get("type")
    action = payload.get("action")
    data = payload.get("data") or {}
    issue_id = data.get("identifier") or data.get("id")

    print("=" * 60)
    print(f"Linear webhook: type={event_type} action={action} issue={issue_id}")
    print("=" * 60)

    if not is_issue_create(payload):
        return {
            "ok": True,
            "handled": False,
            "reason": f"ignored event type={event_type} action={action}",
            "issue": issue_id,
        }

    task = extract_task(payload)
    if not task:
        return {
            "ok": False,
            "handled": False,
            "reason": "missing issue title",
            "issue": issue_id,
        }

    print(f"→ Running LangGraph + memory for task: {task[:120]!r}...")
    pipeline = run_graph_for_task(task, issue_id=str(issue_id) if issue_id else None)
    print(f"→ Pipeline status: {pipeline.get('status')}")
    print(f"→ Memory hits: {len(pipeline.get('memory_hits') or [])}")
    print(f"→ Logs: {pipeline.get('logs')}")

    return {
        "ok": True,
        "handled": True,
        "issue": issue_id,
        "pipeline": pipeline,
    }
