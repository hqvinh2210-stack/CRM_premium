"""CLI: uv run python -m pipeline run|monitor|report-error"""

from __future__ import annotations

import argparse
import json
import sys
import time

from pipeline.linear_ops import report_pipeline_failure
from pipeline.runner import run_pipeline
from pipeline.stages import stage_monitor


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Delivery loop: Code → Review → Test → Deploy → Monitor → Linear"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="Run full or partial pipeline")
    p_run.add_argument("--task", default=None, help="Task for CODE agent stage")
    p_run.add_argument(
        "--from",
        dest="start_from",
        default="review",
        choices=["code", "review", "test", "deploy", "monitor"],
        help="Start stage (default: review — skip agents unless you need codegen)",
    )
    p_run.add_argument("--stop-after", default=None)
    p_run.add_argument("--skip-monitor", action="store_true")
    p_run.add_argument("--no-linear", action="store_true", help="Do not open Linear on fail")
    p_run.add_argument("--health-url", default=None)
    p_run.add_argument("--deploy-mode", default="local")

    p_mon = sub.add_parser("monitor", help="Watch health; create Linear issue on failure")
    p_mon.add_argument("--url", default=None, help="Health URL")
    p_mon.add_argument("--interval", type=int, default=60, help="Seconds between checks")
    p_mon.add_argument("--once", action="store_true")
    p_mon.add_argument("--no-linear", action="store_true")

    p_err = sub.add_parser("report-error", help="Manually open Linear bug for agents")
    p_err.add_argument("--stage", default="production")
    p_err.add_argument("--summary", required=True)
    p_err.add_argument("--detail", default="")

    args = parser.parse_args(argv)

    if args.cmd == "run":
        run = run_pipeline(
            task=args.task,
            start_from=args.start_from,
            stop_after=args.stop_after,
            skip_monitor=args.skip_monitor,
            open_linear_on_fail=not args.no_linear,
            deploy_mode=args.deploy_mode,
            health_url=args.health_url,
        )
        return 0 if run.ok else 1

    if args.cmd == "monitor":
        while True:
            result = stage_monitor(args.url)
            print(f"[{'OK' if result.ok else 'FAIL'}] {result.message}")
            if not result.ok and not args.no_linear:
                report_pipeline_failure(
                    stage="production",
                    summary=result.message,
                    detail=json.dumps(result.details, indent=2)[:8000],
                    source="pipeline.monitor",
                )
            if args.once:
                return 0 if result.ok else 1
            time.sleep(max(args.interval, 5))

    if args.cmd == "report-error":
        issue = report_pipeline_failure(
            stage=args.stage,
            summary=args.summary,
            detail=args.detail or args.summary,
            source="manual",
        )
        print(json.dumps(issue, indent=2) if issue else "failed")
        return 0 if issue else 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
