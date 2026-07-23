"""Individual pipeline stages."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class StageResult:
    name: str
    ok: bool
    duration_s: float
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _run_cmd(cmd: list[str], *, cwd: Path | None = None, timeout: int = 600) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd or ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        shell=False,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out


def stage_code(task: str | None = None) -> StageResult:
    """
    CODE stage: run LangGraph multi-agent (Ava→Rex→Kai) on a task description.
    If no task, skip agent codegen and only snapshot git status.
    """
    t0 = time.time()
    details: dict[str, Any] = {}
    if task:
        try:
            from graph.graph import graph

            result = graph.invoke({"task": task, "logs": []})
            details = {
                "status": result.get("status"),
                "logs": result.get("logs"),
                "plan_preview": (result.get("plan") or "")[:500],
                "review_preview": (result.get("review") or "")[:500],
            }
            ok = result.get("status") == "reviewed"
            msg = f"Agents finished status={result.get('status')}"
        except Exception as exc:
            return StageResult(
                "code", False, time.time() - t0, f"Agent code failed: {exc}", details
            )
    else:
        code, out = _run_cmd(["git", "status", "--short"], timeout=30)
        details["git_status"] = out.strip()
        ok = True
        msg = "No --task; code stage = working tree snapshot"
    return StageResult("code", ok, time.time() - t0, msg, details)


def stage_review() -> StageResult:
    """
    REVIEW stage: Kai-style static checklist + optional pytest collect.
    Fail if critical paths missing.
    """
    t0 = time.time()
    required = [
        ROOT / "pos" / "routers" / "orders.py",
        ROOT / "pos" / "services" / "orders.py",
        ROOT / "app" / "main.py",
        ROOT / "tests" / "test_pos_phase1.py",
    ]
    missing = [str(p.relative_to(ROOT)) for p in required if not p.exists()]
    if missing:
        return StageResult(
            "review",
            False,
            time.time() - t0,
            f"Missing critical files: {missing}",
            {"missing": missing},
        )

    # lightweight review of pay + refund path
    pay_src = (ROOT / "pos" / "services" / "orders.py").read_text(encoding="utf-8")
    events_src = (ROOT / "pos" / "services" / "events.py").read_text(encoding="utf-8")
    checks = {
        "has_atomic_pay": "def atomic_pay" in pay_src,
        "decrements_stock": "stock.qty -=" in pay_src or "stock.qty-=" in pay_src,
        "status_paid": "OrderStatus.paid" in pay_src,
        "has_atomic_refund": "def atomic_refund" in pay_src,
        "restores_stock": "stock.qty +=" in pay_src or "stock.qty+=" in pay_src,
        "outbox_dead_letter": "dead_letter" in events_src,
    }
    ok = all(checks.values())
    msg = "Review checks passed" if ok else f"Review failed: {checks}"
    return StageResult("review", ok, time.time() - t0, msg, {"checks": checks})


def stage_test(extra_args: list[str] | None = None) -> StageResult:
    """TEST stage: pytest."""
    t0 = time.time()
    cmd = [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=line"]
    if extra_args:
        cmd.extend(extra_args)
    code, out = _run_cmd(cmd, timeout=600)
    ok = code == 0
    # keep tail of output
    tail = "\n".join(out.strip().splitlines()[-40:])
    return StageResult(
        "test",
        ok,
        time.time() - t0,
        "pytest passed" if ok else "pytest failed",
        {"exit_code": code, "output_tail": tail},
    )


def stage_deploy(mode: str = "local") -> StageResult:
    """
    DEPLOY stage:
      - local: ensure .data, write deploy marker, verify import app
      - (future) docker / remote
    """
    t0 = time.time()
    try:
        data = ROOT / ".data"
        data.mkdir(exist_ok=True)
        marker = {
            "deployed_at": datetime.now(UTC).isoformat(),
            "mode": mode,
            "git_sha": _git_sha(),
            "version": "0.6.0",
        }
        (data / "deploy.json").write_text(json.dumps(marker, indent=2), encoding="utf-8")

        # smoke import
        code, out = _run_cmd(
            [
                sys.executable,
                "-c",
                "from app.main import app; from pos.bootstrap import bootstrap_pos; print('ok', app.title)",
            ],
            timeout=120,
        )
        if code != 0:
            return StageResult(
                "deploy",
                False,
                time.time() - t0,
                "Deploy smoke import failed",
                {"output": out[-2000:]},
            )
        return StageResult(
            "deploy",
            True,
            time.time() - t0,
            f"Deployed ({mode}) marker written",
            marker,
        )
    except Exception as exc:
        return StageResult("deploy", False, time.time() - t0, str(exc))


def stage_monitor(base_url: str | None = None) -> StageResult:
    """Monitor production/local health endpoint."""
    t0 = time.time()
    url = (base_url or os.getenv("PROD_HEALTH_URL") or "http://127.0.0.1:8001/health").rstrip(
        "/"
    )
    if not url.endswith("/health"):
        # allow base URL
        health_url = url if url.endswith("health") else f"{url}/health"
    else:
        health_url = url
    try:
        import httpx

        r = httpx.get(health_url, timeout=10.0)
        ok = r.status_code == 200 and (r.json().get("ok") is True or "status" in r.json())
        return StageResult(
            "monitor",
            ok,
            time.time() - t0,
            f"health {r.status_code}" if ok else f"unhealthy {r.status_code}",
            {"url": health_url, "body": r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text[:500]},
        )
    except Exception as exc:
        return StageResult(
            "monitor",
            False,
            time.time() - t0,
            f"monitor error: {exc}",
            {"url": health_url},
        )


def _git_sha() -> str:
    code, out = _run_cmd(["git", "rev-parse", "--short", "HEAD"], timeout=15)
    return out.strip() if code == 0 else "unknown"
