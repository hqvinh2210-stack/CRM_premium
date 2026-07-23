"""Wire LangGraph / agents into POS domain events (P3-M4-T4)."""

from __future__ import annotations

import json
import os
from typing import Any


def agent_on_order_enabled() -> bool:
    return os.getenv("AGENT_ON_ORDER", "0") not in {"0", "false", "False"}


def build_order_task(event_type: str, payload: dict[str, Any]) -> str:
    order_id = payload.get("order_id") or "?"
    store_id = payload.get("store_id") or "?"
    total = payload.get("total") or "?"
    customer_id = payload.get("customer_id") or "guest"
    lines = payload.get("lines") or []
    line_hint = ""
    if isinstance(lines, list) and lines:
        line_hint = f" lines={len(lines)}"
    return (
        f"[{event_type}] SoftPOS order {order_id} store={store_id} "
        f"customer={customer_id} total={total}{line_hint}. "
        "Suggest: (1) follow-up CRM task, (2) upsell for next visit, "
        "(3) any stock/loyalty risk. Keep under 12 bullet lines."
    )


def run_agent_for_pos_event(
    event_type: str,
    payload: dict[str, Any],
    *,
    sync: bool | None = None,
) -> dict[str, Any]:
    """
    Invoke in-process LangGraph (preferred) or HTTP /run.
    Returns pipeline summary; never raises if soft mode.
    """
    strict = os.getenv("AGENT_ON_ORDER_STRICT", "0") == "1"
    task = build_order_task(event_type, payload)
    issue_id = str(payload.get("order_id") or event_type)

    try:
        # Prefer in-process graph (same container) — avoids nested HTTP timeouts
        from graph.graph import graph

        result = graph.invoke({"task": task, "logs": [], "issue_id": issue_id})
        summary = {
            "ok": True,
            "mode": "in_process",
            "status": result.get("status"),
            "run_id": result.get("run_id"),
            "agent_modes": result.get("agent_modes") or {},
            "plan_preview": (result.get("plan") or "")[:800],
            "review_preview": (result.get("review") or "")[:500],
        }
        _remember_agent_note(event_type, payload, summary)
        return summary
    except Exception as exc:  # noqa: BLE001
        if strict:
            raise
        return {"ok": False, "mode": "in_process", "error": str(exc)[:500]}


def _remember_agent_note(event_type: str, payload: dict, summary: dict) -> None:
    """Best-effort company memory so future runs stay consistent."""
    try:
        from memory.service import get_memory_service

        mem = get_memory_service()
        text = (
            f"POS {event_type} order={payload.get('order_id')} "
            f"status={summary.get('status')} "
            f"preview={(summary.get('plan_preview') or '')[:400]}"
        )
        mem.add(text, agent_id="pos_event", issue_id=str(payload.get("order_id") or ""))
    except Exception:
        pass


def queue_or_run_agent(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """
    If Celery enabled → async task; else sync in-process (with short soft fail).
    """
    if not agent_on_order_enabled():
        return {"ok": True, "skipped": True, "reason": "AGENT_ON_ORDER=0"}

    if os.getenv("CELERY_ENABLED", "0") == "1":
        try:
            from workers.tasks import run_pos_agent_event

            async_result = run_pos_agent_event.delay(event_type, payload)
            return {
                "ok": True,
                "queued": True,
                "task_id": async_result.id,
                "event_type": event_type,
            }
        except Exception as exc:  # noqa: BLE001
            # fall through to sync
            fallback = {"celery_error": str(exc)[:200]}
            out = run_agent_for_pos_event(event_type, payload)
            out.update(fallback)
            return out

    return run_agent_for_pos_event(event_type, payload)
