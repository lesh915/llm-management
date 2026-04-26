"""Real-time progress broadcasting via Redis pub/sub (FR-C2).

Channel naming:  task:{task_id}:progress
Message schema:
    {
        "task_id":    str,
        "model_id":   str,
        "done":       int,   # cases completed for this model
        "total":      int,
        "pct":        float, # 0-100
        "latency_ms": float  # last call latency
    }
"""
from __future__ import annotations

import json
import os

import redis.asyncio as aioredis

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

_redis_client: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


async def publish_progress(
    task_id: str,
    model_id: str,
    done: int,
    total: int,
    latency_ms: float = 0.0,
) -> None:
    """Publish a progress event to the task channel."""
    payload = json.dumps({
        "task_id":    task_id,
        "model_id":   model_id,
        "done":       done,
        "total":      total,
        "pct":        round(done / total * 100, 1) if total else 0.0,
        "latency_ms": round(latency_ms, 1),
    })
    try:
        await _get_redis().publish(f"task:{task_id}:progress", payload)
    except Exception:
        pass   # non-critical; don't fail the eval


async def subscribe_progress(task_id: str):
    """
    Async generator that yields progress dicts for a task.
    Terminates when a "done" message is received or on timeout.
    """
    r = aioredis.from_url(REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe(f"task:{task_id}:progress")

    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                data = json.loads(message["data"])
                yield data
                if data.get("done") == data.get("total") and data.get("total", 0) > 0:
                    break
            except Exception:
                continue
    finally:
        await pubsub.unsubscribe()
        await r.aclose()
