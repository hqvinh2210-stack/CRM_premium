"""
Linear webhook entry (ngrok → :8000).

Issue Created → POST pipeline at ai-software-company (:8001 /run)
→ LangGraph planner → coding → review
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import FastAPI, Request

app = FastAPI(title="CRM Linear Orchestrator")

PIPELINE_URL = os.getenv("PIPELINE_URL", "http://127.0.0.1:8001/run")

_last_result: dict[str, Any] | None = None


def _is_issue_create(payload: dict[str, Any]) -> bool:
    return (payload.get("type") or "").lower() == "issue" and (
        payload.get("action") or ""
    ).lower() == "create"


def _extract_task(payload: dict[str, Any]) -> str | None:
    data = payload.get("data") or {}
    title = (data.get("title") or "").strip()
    if not title:
        return None
    identifier = (data.get("identifier") or "").strip()
    description = (data.get("description") or "").strip()
    head = f"[{identifier}] {title}" if identifier else title
    if description:
        return f"{head}\n\nDescription:\n{description[:1500]}"
    return head


async def _run_pipeline(task: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(PIPELINE_URL, json={"task": task})
        resp.raise_for_status()
        data = resp.json()
        data["_via"] = "http"
        data["_url"] = PIPELINE_URL
        return data


@app.get("/")
async def health():
    return {
        "status": "ok",
        "service": "orchestrator",
        "pipeline_url": PIPELINE_URL,
        "flow": "Linear → POST /linear → LangGraph (planner→coding→review)",
    }


@app.get("/linear/last")
async def last_result():
    if _last_result is None:
        return {"ok": True, "result": None, "message": "no issue handled yet"}
    return {"ok": True, "result": _last_result}


@app.post("/linear")
async def webhook(data: dict):
    """Receive Linear webhook; run LangGraph on Issue Created."""
    global _last_result

    event_type = data.get("type")
    action = data.get("action")
    issue_data = data.get("data") or {}
    issue_id = issue_data.get("identifier") or issue_data.get("id")

    print("=" * 60)
    print(f"Linear webhook: type={event_type} action={action} issue={issue_id}")
    print("=" * 60)

    if not _is_issue_create(data):
        print("Ignored (only Issue create runs pipeline)")
        return {
            "ok": True,
            "handled": False,
            "reason": f"ignored type={event_type} action={action}",
            "issue": issue_id,
        }

    task = _extract_task(data)
    if not task:
        return {
            "ok": False,
            "handled": False,
            "reason": "missing issue title",
            "issue": issue_id,
        }

    print(f"→ Pipeline task: {task[:160]!r}")
    try:
        pipeline = await _run_pipeline(task)
    except Exception as exc:
        print(f"→ Pipeline ERROR: {exc}")
        return {
            "ok": False,
            "handled": False,
            "issue": issue_id,
            "error": str(exc),
            "hint": f"Is ai-software-company running at {PIPELINE_URL}?",
        }

    print(f"→ status={pipeline.get('status')} via={pipeline.get('_via')}")
    print(f"→ logs={pipeline.get('logs')}")

    result = {
        "ok": True,
        "handled": True,
        "issue": issue_id,
        "pipeline": pipeline,
    }
    _last_result = result
    return result


@app.post("/linear/raw")
async def webhook_raw(request: Request):
    body = await request.json()
    print("Linear raw webhook:", body)
    return {"ok": True, "keys": list(body.keys()) if isinstance(body, dict) else None}
