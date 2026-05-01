"""WebSocket endpoint for real-time task progress (FR-C2)."""
from __future__ import annotations

import asyncio

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..progress import REDIS_URL

router = APIRouter()


@router.websocket("/ws/tasks/{task_id}/progress")
async def task_progress_ws(websocket: WebSocket, task_id: str):
    """
    Subscribe to real-time progress events for a comparison task.

    Protocol:
        1. Server sends {"type": "ready"} once the Redis subscription is open.
        2. Client may then safely start the task.
        3. Server streams progress events until done.
    """
    await websocket.accept()

    r = aioredis.from_url(REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe(f"task:{task_id}:progress")

    # Signal to the client that the subscription is live
    try:
        await websocket.send_json({"type": "ready", "task_id": task_id})
    except Exception:
        await r.aclose()
        return

    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                import json
                event = json.loads(message["data"])
                # Task fully done → close
                if event.get("type") == "task_done":
                    await websocket.send_json({"type": "done", "task_id": task_id})
                    break
                # Progress update → forward to client
                await websocket.send_json(event)
            except Exception:
                continue
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await websocket.send_json({"type": "error", "detail": str(exc)})
        except Exception:
            pass
    finally:
        try:
            await pubsub.unsubscribe()
            await r.aclose()
        except Exception:
            pass
        try:
            await websocket.close()
        except Exception:
            pass
