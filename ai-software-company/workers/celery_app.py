"""
Celery app for CRM outbox processing.

Run worker + beat:
  uv run celery -A workers.celery_app.celery_app worker -l info -B

Requires REDIS_URL (default redis://127.0.0.1:6379/0).
"""

from __future__ import annotations

import os

from datetime import timedelta

from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")

celery_app = Celery(
    "crm_pos",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["workers.tasks"],
)

_outbox_every = float(os.getenv("CELERY_OUTBOX_INTERVAL", "15.0"))

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Ho_Chi_Minh",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "process-outbox-every-15s": {
            "task": "workers.tasks.process_outbox_batch",
            "schedule": timedelta(seconds=_outbox_every),
        },
        "expire-points-daily": {
            "task": "workers.tasks.expire_loyalty_points",
            "schedule": crontab(hour=2, minute=0),
        },
    },
)

# Eager mode for tests: CELERY_TASK_ALWAYS_EAGER=1
if os.getenv("CELERY_TASK_ALWAYS_EAGER", "0") == "1":
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
