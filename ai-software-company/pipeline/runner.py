"""Orchestrate Code → Review → Test → Deploy → Monitor; failures → Linear."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from pipeline.linear_ops import report_pipeline_failure
from pipeline.stages import (
    StageResult,
    stage_code,
    stage_deploy,
    stage_monitor,
    stage_review,
    stage_test,
)

ROOT = Path(__file__).resolve().parent.parent
REPORT_DIR = ROOT / ".data" / "pipeline_runs"


@dataclass
class PipelineRun:
    started_at: str
    finished_at: str | None = None
    ok: bool = False
    stages: list[dict[str, Any]] = field(default_factory=list)
    linear_issue: dict[str, Any] | None = None
    task: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


STAGES_ORDER = ["code", "review", "test", "deploy", "monitor"]


def run_pipeline(
    *,
    task: str | None = None,
    start_from: str = "code",
    stop_after: str | None = None,
    skip_monitor: bool = False,
    open_linear_on_fail: bool = True,
    deploy_mode: str = "local",
    health_url: str | None = None,
) -> PipelineRun:
    """
    Full delivery loop.

    start_from: code|review|test|deploy|monitor
    """
    run = PipelineRun(
        started_at=datetime.now(UTC).isoformat(),
        task=task,
    )
    order = list(STAGES_ORDER)
    if start_from in order:
        order = order[order.index(start_from) :]
    if skip_monitor and "monitor" in order:
        order.remove("monitor")

    handlers: dict[str, Callable[[], StageResult]] = {
        "code": lambda: stage_code(task),
        "review": stage_review,
        "test": stage_test,
        "deploy": lambda: stage_deploy(deploy_mode),
        "monitor": lambda: stage_monitor(health_url),
    }

    failed: StageResult | None = None
    for name in order:
        print(f"\n=== STAGE: {name.upper()} ===")
        result = handlers[name]()
        run.stages.append(result.to_dict())
        status = "OK" if result.ok else "FAIL"
        print(f"[{status}] {result.message} ({result.duration_s:.1f}s)")
        if not result.ok:
            failed = result
            break
        if stop_after == name:
            break

    run.ok = failed is None
    run.finished_at = datetime.now(UTC).isoformat()

    if failed and open_linear_on_fail:
        issue = report_pipeline_failure(
            stage=failed.name,
            summary=failed.message,
            detail=json.dumps(failed.details, indent=2, ensure_ascii=False)[:8000],
            source="pipeline.runner",
        )
        run.linear_issue = issue

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = REPORT_DIR / f"run_{stamp}.json"
    path.write_text(json.dumps(run.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nReport: {path}")
    print(f"Pipeline overall: {'SUCCESS' if run.ok else 'FAILED'}")
    return run
