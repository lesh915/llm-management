"""Celery application — async comparison task execution."""
import os

from celery import Celery

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "comparison_engine",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,   # one task at a time per worker
    result_expires=86400,           # 24h
)

# ── Celery task ───────────────────────────────────────────────────────────────

@celery_app.task(bind=True, name="comparison_engine.run_task")
def run_comparison_task_celery(self, task_id: str) -> dict:
    """
    Entry point for Celery workers.
    Bridges sync Celery ↔ async runner via asyncio.run().
    """
    import asyncio
    from .runner import execute_task

    try:
        result = asyncio.run(execute_task(task_id))
        return {"status": "completed", "task_id": task_id, "results": result}
    except Exception as exc:
        self.update_state(state="FAILURE", meta={"error": str(exc)})
        raise
